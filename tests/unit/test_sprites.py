from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from tama.domain.animation import AnimationKey
from tama.domain.stage import LifeStage, Variant
from tama.ui import sprites
from tama.ui.sprites import (
    MAX_HEIGHT,
    MAX_WIDTH,
    PLACEHOLDER,
    Cell,
    PaletteEntry,
    Shade,
    SpriteFile,
    load_sprite,
    render_cells,
    to_content,
)

INK = PaletteEntry(color="#112233")  # dark: a gap in monochrome
RED = PaletteEntry(color="#ff0000")
CRIMSON = PaletteEntry(color="#ff0000")  # same colour, different palette key
FUZZ = PaletteEntry(color="#00ff00", shade=Shade.MEDIUM)
PAPER = PaletteEntry(color="#f0f0f0")
PALETTE = {"k": INK, "r": RED, "c": CRIMSON, "f": FUZZ, "p": PAPER}


@pytest.fixture(autouse=True)
def clear_cache() -> Iterator[None]:
    load_sprite.cache_clear()
    yield
    load_sprite.cache_clear()


def cell(top: str, bottom: str, *, color: bool = True) -> Cell:
    return render_cells([top, bottom], PALETTE, color=color)[0][0]


# --- Rendering: two pixels per cell ---------------------------------------------------------


@pytest.mark.parametrize(
    ("top", "bottom", "expected"),
    [
        (".", ".", Cell(" ")),
        ("k", ".", Cell("▀", fg="#112233")),
        (".", "k", Cell("▄", fg="#112233")),
        ("k", "k", Cell("█", fg="#112233")),
        ("r", "c", Cell("█", fg="#ff0000")),
        ("k", "r", Cell("▀", fg="#112233", bg="#ff0000")),
        ("f", "f", Cell("▒", fg="#00ff00")),
        ("f", "k", Cell("▀", fg="#00ff00", bg="#112233")),
        ("f", ".", Cell("▀", fg="#00ff00")),
    ],
)
def test_cell_glyphs_and_colours(top: str, bottom: str, expected: Cell) -> None:
    assert cell(top, bottom) == expected


@pytest.mark.parametrize(
    ("top", "bottom", "expected"),
    [
        (".", ".", Cell(" ")),
        ("p", ".", Cell("▀")),
        (".", "p", Cell("▄")),
        ("p", "f", Cell("█")),
        ("f", "f", Cell("▒")),
        ("k", "k", Cell(" ")),
        ("k", "p", Cell("▄")),
    ],
)
def test_monochrome_draws_light_pixels_and_leaves_dark_ones_as_gaps(
    top: str, bottom: str, expected: Cell
) -> None:
    assert cell(top, bottom, color=False) == expected


@pytest.mark.parametrize(
    ("shade", "glyph"), [(Shade.LIGHT, "░"), (Shade.MEDIUM, "▒"), (Shade.DARK, "▓")]
)
def test_shade_levels(shade: Shade, glyph: str) -> None:
    palette = {"s": PaletteEntry(color="#abcdef", shade=shade)}

    assert render_cells(["s", "s"], palette, color=True)[0][0].glyph == glyph


@pytest.mark.parametrize(
    ("colour", "luminance"), [("#000000", 0.0), ("#ffffff", 1.0), ("#00ff00", 0.7152)]
)
def test_luminance(colour: str, luminance: float) -> None:
    assert PaletteEntry(color=colour).luminance == pytest.approx(luminance)


def test_rows_pair_into_terminal_lines() -> None:
    cells = render_cells(["k.", ".k", "kk", ".."], PALETTE, color=True)

    assert [[c.glyph for c in row] for row in cells] == [["▀", "▄"], ["▀", "▀"]]


def test_to_content_applies_styles_per_cell() -> None:
    content = to_content(
        [[Cell("▀", fg="#112233", bg="#ff0000"), Cell(" ")], [Cell("█", fg="#00ff00")]]
    )

    assert content.plain == "▀ \n█"
    assert [(s.start, s.end, s.style) for s in content.spans] == [
        (0, 1, "#112233 on #ff0000"),
        (3, 4, "#00ff00"),
    ]


# --- Validation -----------------------------------------------------------------------------

GOOD = {"palette": {"k": "#000000"}, "frames": [{"pixels": "k.\n.k\n"}]}


def sprite_file(**changes: object) -> SpriteFile:
    return SpriteFile.model_validate({**GOOD, **changes})


def test_minimal_sprite_file_is_valid() -> None:
    parsed = sprite_file()

    assert parsed.fps == 2
    assert parsed.loop is True
    assert parsed.frames[0].rows == ("k.", ".k")
    assert parsed.palette["k"] == PaletteEntry(color="#000000")


def test_palette_entries_may_be_tables_with_shade() -> None:
    parsed = sprite_file(palette={"k": {"color": "#000000", "shade": "dark"}})

    assert parsed.palette["k"] == PaletteEntry(color="#000000", shade=Shade.DARK)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"palette": {"k": "black"}}, "pattern"),
        ({"palette": "k=#000000"}, "dictionary"),
        ({"palette": {"k": "#000000", "kk": "#000000"}}, "single character"),
        ({"palette": {"k": "#000000", ".": "#000000"}}, "transparent"),
        ({"frames": []}, "at least 1"),
        ({"frames": [{"pixels": "kx\n.k\n"}]}, "not in the palette"),
        ({"frames": [{"pixels": "k.\n.k\nkk\n"}]}, "even"),
        ({"frames": [{"pixels": "k.\n.\n"}]}, "same length"),
        ({"frames": [{"pixels": "k" * (MAX_WIDTH + 1) + "\n" + "k" * (MAX_WIDTH + 1)}]}, "wide"),
        ({"frames": [{"pixels": "k\n" * (MAX_HEIGHT + 2)}]}, "tall"),
        ({"frames": [{"pixels": "k.\n.k"}, {"pixels": "kk\nkk\nkk\nkk"}]}, "same size"),
        ({"fps": 0}, "fps"),
        ({"colour": "#000000"}, "colour"),
    ],
    ids=[
        "bad-colour",
        "palette-not-table",
        "long-key",
        "dot-key",
        "no-frames",
        "unknown-pixel",
        "odd-height",
        "ragged",
        "too-wide",
        "too-tall",
        "frame-sizes",
        "zero-fps",
        "unknown-key",
    ],
)
def test_invalid_sprite_files_are_rejected(changes: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        sprite_file(**changes)


# --- Shipped assets -------------------------------------------------------------------------


def all_sprite_files() -> list[Path]:
    root = Path(str(sprites.sprite_root()))
    return sorted(root.rglob("*.toml"))


def test_there_are_sprite_files() -> None:
    assert all_sprite_files()


@pytest.mark.parametrize("path", all_sprite_files(), ids=lambda p: "/".join(p.parts[-3:]))
def test_every_shipped_sprite_is_valid(path: Path) -> None:
    SpriteFile.parse(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("stage", list(LifeStage))
def test_every_stage_has_an_idle_sprite(stage: LifeStage) -> None:
    sprite = load_sprite(Variant.DEFAULT, stage, AnimationKey.IDLE)

    assert sprite is not PLACEHOLDER
    assert len(sprite.frames(color=True)) == len(sprite.frames(color=False)) >= 1


# --- Loading & fallbacks --------------------------------------------------------------------


def test_missing_variant_falls_back_to_default() -> None:
    assert load_sprite(Variant.GOOD, LifeStage.ADULT, AnimationKey.IDLE) is load_sprite(
        Variant.DEFAULT, LifeStage.ADULT, AnimationKey.IDLE
    )


def test_missing_animation_falls_back_to_idle() -> None:
    assert load_sprite(Variant.DEFAULT, LifeStage.CHILD, AnimationKey.EAT) is load_sprite(
        Variant.DEFAULT, LifeStage.CHILD, AnimationKey.IDLE
    )


def test_missing_art_uses_a_placeholder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sprites, "sprite_root", lambda: tmp_path)

    assert load_sprite(Variant.DEFAULT, LifeStage.TEEN, AnimationKey.IDLE) is PLACEHOLDER


def test_a_variant_without_any_art_uses_a_placeholder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sprites, "sprite_root", lambda: tmp_path)

    assert load_sprite(Variant.GOOD, LifeStage.ADULT, AnimationKey.EAT) is PLACEHOLDER


def test_variant_idle_is_preferred_over_a_missing_default_animation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    good_idle = tmp_path / "good" / "adult" / "idle.toml"
    good_idle.parent.mkdir(parents=True)
    good_idle.write_text('[palette]\nk = "#000000"\n[[frames]]\npixels = "kk\\nkk"\n')
    monkeypatch.setattr(sprites, "sprite_root", lambda: tmp_path)

    sprite = load_sprite(Variant.GOOD, LifeStage.ADULT, AnimationKey.EAT)

    assert sprite is load_sprite(Variant.GOOD, LifeStage.ADULT, AnimationKey.IDLE)
    assert sprite.frames(color=True)[0].plain == "██"


def test_broken_art_uses_a_placeholder_and_logs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    broken = tmp_path / "default" / "child" / "idle.toml"
    broken.parent.mkdir(parents=True)
    broken.write_text("fps = ", encoding="utf-8")
    monkeypatch.setattr(sprites, "sprite_root", lambda: tmp_path)

    assert load_sprite(Variant.DEFAULT, LifeStage.CHILD, AnimationKey.IDLE) is PLACEHOLDER
    assert "idle.toml" in caplog.text


def test_placeholder_renders_something() -> None:
    assert PLACEHOLDER.frames(color=True)[0].plain == "?"
    assert PLACEHOLDER.frames(color=False)[0].plain == "?"
