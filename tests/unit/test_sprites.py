from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError
from tools import generate_sprites

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
    hstack,
    load_overlay,
    load_sprite,
    overlay_content,
    render_cells,
    to_content,
)

OVERLAYS = ("zzz", "sick", "poop")

INK = PaletteEntry(color="#112233")  # dark: a gap in monochrome
RED = PaletteEntry(color="#ff0000")
CRIMSON = PaletteEntry(color="#ff0000")  # same colour, different palette key
FUZZ = PaletteEntry(color="#00ff00", shade=Shade.MEDIUM)
PAPER = PaletteEntry(color="#f0f0f0")
PALETTE = {"k": INK, "r": RED, "c": CRIMSON, "f": FUZZ, "p": PAPER}


@pytest.fixture(autouse=True)
def clear_cache() -> Iterator[None]:
    load_sprite.cache_clear()
    load_overlay.cache_clear()
    yield
    load_sprite.cache_clear()
    load_overlay.cache_clear()


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


LIVING = (
    AnimationKey.IDLE,
    AnimationKey.BLINK,
    AnimationKey.EAT,
    AnimationKey.PLAY,
    AnimationKey.HAPPY,
    AnimationKey.REFUSE,
    AnimationKey.SLEEP,
    AnimationKey.SICK,
    AnimationKey.CLEAN,
)
REQUIRED: dict[LifeStage, tuple[AnimationKey, ...]] = {
    LifeStage.EGG: (AnimationKey.IDLE, AnimationKey.WOBBLE),
    LifeStage.BABY: (*LIVING, AnimationKey.HATCH),
    LifeStage.CHILD: (*LIVING, AnimationKey.EVOLVE),
    LifeStage.TEEN: (*LIVING, AnimationKey.EVOLVE),
    LifeStage.ADULT: (*LIVING, AnimationKey.EVOLVE),
    LifeStage.ELDER: (*LIVING, AnimationKey.EVOLVE),
    LifeStage.DEAD: (AnimationKey.IDLE,),
}
"""Every animation SPEC §5.2 needs, per stage ("dead" uses the dead stage's idle)."""


@pytest.mark.parametrize(
    ("variant", "stage", "animation"),
    [(Variant.DEFAULT, s, a) for s, anims in REQUIRED.items() for a in anims]
    + [
        (v, s, a)
        for v in (Variant.GOOD, Variant.SCRUFFY)
        for s in (LifeStage.ADULT, LifeStage.ELDER)
        for a in REQUIRED[s]
    ],
    ids=str,
)
def test_every_required_animation_has_its_own_file(
    variant: Variant, stage: LifeStage, animation: AnimationKey
) -> None:
    path = Path(str(sprites.sprite_root())) / variant / stage / f"{animation}.toml"

    assert path.is_file()


def test_reactions_are_one_shot_and_loops_loop() -> None:
    for stage, animations in REQUIRED.items():
        for animation in animations:
            sprite = load_sprite(Variant.DEFAULT, stage, animation)
            looping = animation in {
                AnimationKey.IDLE,
                AnimationKey.SLEEP,
                AnimationKey.SICK,
                AnimationKey.WOBBLE,
            }
            assert sprite.loop is looping, (stage, animation)


def test_animations_of_a_stage_share_one_canvas() -> None:
    for stage, animations in REQUIRED.items():
        sizes = {
            (len(grid), len(grid[0]))
            for animation in animations
            for grid in load_sprite(Variant.DEFAULT, stage, animation).cells(color=True)
        }
        assert len(sizes) == 1, (stage, sizes)


def test_generated_art_is_up_to_date() -> None:
    """The committed sprites must match tools/generate_sprites.py (run it after editing)."""
    root = Path(str(sprites.sprite_root()))
    expected = generate_sprites.sprite_set()

    on_disk = {p.relative_to(root): p.read_text(encoding="utf-8") for p in root.rglob("*.toml")}

    assert on_disk == expected


@pytest.mark.parametrize("stage", list(LifeStage))
def test_every_stage_has_an_idle_sprite(stage: LifeStage) -> None:
    sprite = load_sprite(Variant.DEFAULT, stage, AnimationKey.IDLE)

    assert sprite is not PLACEHOLDER
    assert len(sprite.frames(color=True)) == len(sprite.frames(color=False)) >= 1


# --- Loading & fallbacks --------------------------------------------------------------------


TINY = '[palette]\nk = "#000000"\n[[frames]]\npixels = "kk\\nkk"\n'


@pytest.fixture
def art(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty sprite root to populate per test."""
    monkeypatch.setattr(sprites, "sprite_root", lambda: tmp_path)
    return tmp_path


def draw(root: Path, variant: str, stage: str, animation: str) -> None:
    path = root / variant / stage / f"{animation}.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(TINY, encoding="utf-8")


def test_missing_variant_falls_back_to_default(art: Path) -> None:
    draw(art, "default", "adult", "idle")

    assert load_sprite(Variant.GOOD, LifeStage.ADULT, AnimationKey.IDLE) is load_sprite(
        Variant.DEFAULT, LifeStage.ADULT, AnimationKey.IDLE
    )


def test_missing_animation_falls_back_to_idle(art: Path) -> None:
    draw(art, "default", "child", "idle")

    assert load_sprite(Variant.DEFAULT, LifeStage.CHILD, AnimationKey.EAT) is load_sprite(
        Variant.DEFAULT, LifeStage.CHILD, AnimationKey.IDLE
    )


def test_default_variant_animation_is_used_for_a_missing_variant_animation(art: Path) -> None:
    draw(art, "default", "adult", "eat")

    assert load_sprite(Variant.GOOD, LifeStage.ADULT, AnimationKey.EAT) is load_sprite(
        Variant.DEFAULT, LifeStage.ADULT, AnimationKey.EAT
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


# --- Composition & overlays -----------------------------------------------------------------


def test_hstack_bottom_aligns_with_a_gap() -> None:
    tall = ((Cell("a"),), (Cell("b"),))
    short = ((Cell("c"), Cell("d")),)

    stacked = hstack([tall, short], gap=1)

    assert [[c.glyph for c in row] for row in stacked] == [
        ["a", " ", " ", " "],
        ["b", " ", "c", "d"],
    ]


def test_hstack_of_nothing_is_empty() -> None:
    assert hstack([]) == ()


def test_sprite_cells_match_frames() -> None:
    sprite = load_sprite(Variant.DEFAULT, LifeStage.CHILD, AnimationKey.IDLE)

    assert to_content(sprite.cells(color=True)[0]) == sprite.frames(color=True)[0]
    assert to_content(sprite.cells(color=False)[0]) == sprite.frames(color=False)[0]


@pytest.mark.parametrize("name", OVERLAYS)
def test_every_overlay_exists(name: str) -> None:
    assert load_overlay(name) is not PLACEHOLDER


def test_missing_overlay_is_a_placeholder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(sprites, "sprite_root", lambda: tmp_path)

    assert load_overlay("nope") is PLACEHOLDER
    assert "nope.toml" in caplog.text


def test_overlay_content_places_overlays_side_by_side() -> None:
    one = overlay_content(["poop"], color=True)
    two = overlay_content(["poop", "poop"], color=True)

    one_width = len(one.plain.split("\n")[0])
    assert len(two.plain.split("\n")[0]) == 2 * one_width + 2
