from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError
from tools.sprites import generate

from tama.domain.animation import AnimationKey
from tama.domain.pet import DEFAULT_SPECIES
from tama.domain.stage import LifeStage, Variant
from tama.ui import sprites
from tama.ui.colours import LOOKS, Look, Mode
from tama.ui.sprites import (
    MAX_HEIGHT,
    MAX_WIDTH,
    PLACEHOLDER,
    BaseFile,
    Cell,
    PaletteEntry,
    Shade,
    Sprite,
    SpriteFile,
    UiColour,
    clear_caches,
    hstack,
    load_base,
    load_overlay,
    load_sprite,
    overlay_content,
    render_cells,
    species_of,
    to_content,
)
from tests.factories import make_pet

DARK = Look(Mode.DARK, color=True)
LIGHT = Look(Mode.LIGHT, color=True)
DARK_MONO = Look(Mode.DARK, color=False)
LIGHT_MONO = Look(Mode.LIGHT, color=False)

INK = PaletteEntry(dark="#112233", light="#112233")  # dark in both modes
RED = PaletteEntry(dark="#ff0000", light="#cc0000")
CRIMSON = PaletteEntry(dark="#ff0000", light="#cc0000")  # same colours, different key
FUZZ = PaletteEntry(dark="#00ff00", light="#008800", shade=Shade.MEDIUM)
PAPER = PaletteEntry(dark="#f0f0f0", light="#f0f0f0")  # light in both modes
PALETTE = {"k": INK, "r": RED, "c": CRIMSON, "f": FUZZ, "p": PAPER}
OVERLAY_NAMES = ("zzz", "sick", "poop", "meal", "snack")


@pytest.fixture(autouse=True)
def fresh_caches() -> Iterator[None]:
    clear_caches()
    yield
    clear_caches()


def cell(top: str, bottom: str, look: Look = DARK) -> Cell:
    return render_cells([top, bottom], PALETTE, look)[0][0]


# --- Rendering ----------------------------------------------------------------------------------


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


def test_light_mode_uses_light_colours() -> None:
    assert cell("k", "r", LIGHT) == Cell("▀", fg="#112233", bg="#cc0000")
    assert cell("f", "f", LIGHT) == Cell("▒", fg="#008800")


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
def test_monochrome_on_dark_draws_light_pixels(top: str, bottom: str, expected: Cell) -> None:
    assert cell(top, bottom, DARK_MONO) == expected


@pytest.mark.parametrize(
    ("top", "bottom", "expected"),
    [
        ("k", "k", Cell("█")),
        ("p", "p", Cell(" ")),
        ("k", "p", Cell("▀")),
        ("p", "k", Cell("▄")),
    ],
)
def test_monochrome_on_light_draws_dark_pixels(top: str, bottom: str, expected: Cell) -> None:
    assert cell(top, bottom, LIGHT_MONO) == expected


@pytest.mark.parametrize(
    ("shade", "glyph"), [(Shade.LIGHT, "░"), (Shade.MEDIUM, "▒"), (Shade.DARK, "▓")]
)
def test_shade_levels(shade: Shade, glyph: str) -> None:
    palette = {"s": PaletteEntry(dark="#abcdef", light="#abcdef", shade=shade)}

    assert render_cells(["s", "s"], palette, DARK)[0][0].glyph == glyph


def test_rows_pair_into_terminal_lines() -> None:
    cells = render_cells(["k.", ".k", "kk", ".."], PALETTE, DARK)

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


# --- Colour values ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "dark", "light"),
    [
        ("#123456", "#123456", "#123456"),
        ({"dark": "#111111", "light": "#eeeeee"}, "#111111", "#eeeeee"),
        ({"color": "#222222"}, "#222222", "#222222"),
        ({"color": "#222222", "light": "#dddddd"}, "#222222", "#dddddd"),
    ],
)
def test_palette_entry_shorthands(raw: object, dark: str, light: str) -> None:
    entry = PaletteEntry.model_validate(raw)

    assert (entry.colour(Mode.DARK), entry.colour(Mode.LIGHT)) == (dark, light)


@pytest.mark.parametrize("raw", ["black", {"dark": "#111111"}, {"color": "#111111", "glow": 1}])
def test_invalid_palette_entries(raw: object) -> None:
    with pytest.raises(ValidationError):
        PaletteEntry.model_validate(raw)


@pytest.mark.parametrize(
    ("colour", "mode", "luminance"),
    [("#000000", Mode.DARK, 0.0), ("#ffffff", Mode.DARK, 1.0), ("#00ff00", Mode.LIGHT, 0.7152)],
)
def test_luminance(colour: str, mode: Mode, luminance: float) -> None:
    assert PaletteEntry.model_validate(colour).luminance(mode) == pytest.approx(luminance)


def test_ui_colours_may_refer_to_theme_variables() -> None:
    colour = UiColour.model_validate({"dark": "$panel", "light": "#eeeeee"})

    assert colour.colour(Mode.DARK) == "$panel"
    assert colour.colour(Mode.LIGHT) == "#eeeeee"
    with pytest.raises(ValidationError):
        UiColour.model_validate("panel")


# --- File validation ----------------------------------------------------------------------------


def test_base_file_with_palette_and_ui() -> None:
    base = BaseFile.model_validate(
        {"palette": {"k": "#000000"}, "ui": {"accent": {"dark": "#111111", "light": "#222222"}}}
    )

    assert base.palette["k"] == PaletteEntry(dark="#000000", light="#000000")
    assert base.ui["accent"].colour(Mode.LIGHT) == "#222222"


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ({"palette": {"k": "#000000"}, "ui": {"sky": "#000000"}}, "unknown UI colours"),
        ({"palette": {"kk": "#000000"}}, "single character"),
        ({"palette": {".": "#000000"}}, "transparent"),
        ({"palette": "k=#000"}, "dictionary"),
        ({}, "palette"),
    ],
)
def test_invalid_base_files(raw: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        BaseFile.model_validate(raw)


GOOD = {"frames": [{"pixels": "k.\n.k\n"}]}


def sprite_file(**changes: object) -> SpriteFile:
    return SpriteFile.model_validate({**GOOD, **changes})


def test_minimal_sprite_file_is_valid() -> None:
    parsed = sprite_file()

    assert parsed.fps == 2
    assert parsed.loop is True
    assert parsed.palette == {}
    assert parsed.frames[0].rows == ("k.", ".k")


def test_sprite_files_may_override_palette_entries() -> None:
    parsed = sprite_file(palette={"k": {"dark": "#010101", "light": "#020202"}})

    assert parsed.palette["k"].colour(Mode.LIGHT) == "#020202"


def test_missing_colours_are_reported_against_a_palette() -> None:
    parsed = sprite_file(frames=[{"pixels": "kx\n.k"}])

    assert parsed.missing_colours({"k": INK}) == {"x"}
    assert parsed.missing_colours({"k": INK, "x": INK}) == set()


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"palette": {"k": "black"}}, "pattern"),
        ({"palette": {"kk": "#000000"}}, "single character"),
        ({"frames": []}, "at least 1"),
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
        "long-key",
        "no-frames",
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


# --- Shipped assets -----------------------------------------------------------------------------

ROOT = Path(str(sprites.sprite_root()))
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
    AnimationKey.LOOK_LEFT,
    AnimationKey.LOOK_RIGHT,
    AnimationKey.MISBEHAVE,
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
"""Every animation SPEC §5.2 needs, per stage, for every species."""
LOOPING = {
    AnimationKey.IDLE,
    AnimationKey.SLEEP,
    AnimationKey.SICK,
    AnimationKey.WOBBLE,
    AnimationKey.LOOK_LEFT,
    AnimationKey.LOOK_RIGHT,
    AnimationKey.MISBEHAVE,
}


def species_dirs() -> list[str]:
    return sorted(p.name for p in ROOT.iterdir() if p.is_dir() and p.name != sprites.OVERLAYS)


def test_there_is_a_default_species() -> None:
    assert DEFAULT_SPECIES in species_dirs()


@pytest.mark.parametrize("collection", [*species_dirs(), sprites.OVERLAYS])
def test_every_collection_has_a_valid_base_palette(collection: str) -> None:
    assert load_base(collection) is not None


@pytest.mark.parametrize(
    "path",
    sorted(p for p in ROOT.rglob("*.toml") if p.name != "base.toml"),
    ids=lambda p: "/".join(p.relative_to(ROOT).parts),
)
def test_every_shipped_sprite_has_all_its_colours(path: Path) -> None:
    collection = path.relative_to(ROOT).parts[0]
    parsed = SpriteFile.parse(path.read_text(encoding="utf-8"))
    base = load_base(collection)
    assert base is not None

    assert parsed.missing_colours({**base.palette, **parsed.palette}) == set()


@pytest.mark.parametrize(
    ("species", "variant", "stage", "animation"),
    [
        (species, Variant.DEFAULT, stage, animation)
        for species in species_dirs()
        for stage, animations in REQUIRED.items()
        for animation in animations
    ]
    + [
        (DEFAULT_SPECIES, variant, stage, animation)
        for variant in (Variant.GOOD, Variant.SCRUFFY)
        for stage in (LifeStage.ADULT, LifeStage.ELDER)
        for animation in REQUIRED[stage]
    ],
    ids=str,
)
def test_every_required_animation_has_its_own_file(
    species: str, variant: Variant, stage: LifeStage, animation: AnimationKey
) -> None:
    assert (ROOT / species / variant / stage / f"{animation}.toml").is_file()


def parse_shipped(species: str, variant: Variant, stage: LifeStage, name: str) -> SpriteFile:
    """A shipped animation file, parsed but not rendered (rendering every look is slow)."""
    path = ROOT / species / variant / stage / f"{name}.toml"
    return SpriteFile.parse(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("species", species_dirs())
def test_reactions_are_one_shot_and_loops_loop(species: str) -> None:
    for stage, animations in REQUIRED.items():
        for animation in animations:
            parsed = parse_shipped(species, Variant.DEFAULT, stage, animation)
            assert parsed.loop is (animation in LOOPING), (stage, animation)


@pytest.mark.parametrize("species", species_dirs())
def test_animations_of_a_stage_share_one_canvas(species: str) -> None:
    for stage, animations in REQUIRED.items():
        sizes = {
            (len(frame.rows), len(frame.rows[0]))
            for animation in animations
            for frame in parse_shipped(species, Variant.DEFAULT, stage, animation).frames
        }
        assert len(sizes) == 1, (stage, sizes)


def test_generated_art_is_up_to_date() -> None:
    """Committed sprites must match tools/sprites (run `python -m tools.sprites.generate`)."""
    expected = generate.sprite_set()
    on_disk = {
        p.relative_to(ROOT): p.read_text(encoding="utf-8")
        for name in generate.generated_collections()
        for p in (ROOT / name).rglob("*.toml")
    }

    assert on_disk == expected


@pytest.mark.parametrize("stage", list(LifeStage))
def test_every_stage_renders_in_every_look(stage: LifeStage) -> None:
    sprite = load_sprite(DEFAULT_SPECIES, Variant.DEFAULT, stage, AnimationKey.IDLE)

    assert sprite is not PLACEHOLDER
    assert {len(sprite.frames(look)) for look in LOOKS} == {len(sprite.frames(DARK))}


def test_every_shipped_sprite_draws_something_in_every_look() -> None:
    """Catches colours that vanish in monochrome (e.g. a dark sprite on a dark theme)."""
    for path in ROOT.rglob("*.toml"):
        if path.name == "base.toml":
            continue
        base = load_base(path.relative_to(ROOT).parts[0])
        assert base is not None
        parsed = SpriteFile.parse(path.read_text(encoding="utf-8"))
        palette = {**base.palette, **parsed.palette}
        for frame in parsed.frames:
            # Whether a frame shows anything depends only on which pixels it uses, so render
            # each distinct pixel once (whole frames in every look make this test slow).
            used = "".join(sorted(set("".join(frame.rows)) - {"."}))
            for look in LOOKS:
                (cells,) = render_cells((used, "." * len(used)), palette, look)
                assert any(c.glyph != " " for c in cells), (path, look)


def test_sprite_cells_match_frames() -> None:
    sprite = load_sprite(DEFAULT_SPECIES, Variant.DEFAULT, LifeStage.CHILD, AnimationKey.IDLE)

    for look in LOOKS:
        assert to_content(sprite.cells(look)[0]) == sprite.frames(look)[0]


# --- Loading & fallbacks (against a temporary sprite root) --------------------------------------

TINY = '[[frames]]\npixels = "kk\\nkk"\n'


@pytest.fixture
def art(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty sprite root with a ``critter`` species whose palette defines ``k``."""
    monkeypatch.setattr(sprites, "sprite_root", lambda: tmp_path)
    (tmp_path / "critter").mkdir()
    (tmp_path / "critter" / "base.toml").write_text(
        '[palette]\nk = { dark = "#111111", light = "#eeeeee" }\n', encoding="utf-8"
    )
    return tmp_path


def draw(root: Path, variant: str, stage: str, animation: str, text: str = TINY) -> None:
    path = root / "critter" / variant / stage / f"{animation}.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load(variant: Variant, stage: LifeStage, animation: AnimationKey) -> Sprite:
    return load_sprite("critter", variant, stage, animation)


def test_species_palette_is_used_per_mode(art: Path) -> None:
    draw(art, "default", "child", "idle")
    sprite = load(Variant.DEFAULT, LifeStage.CHILD, AnimationKey.IDLE)

    assert sprite.cells(DARK)[0][0][0] == Cell("█", fg="#111111")
    assert sprite.cells(LIGHT)[0][0][0] == Cell("█", fg="#eeeeee")


def test_animation_palette_overrides_the_species_palette(art: Path) -> None:
    draw(art, "default", "child", "sick", '[palette]\nk = "#00aa00"\n' + TINY)

    sprite = load(Variant.DEFAULT, LifeStage.CHILD, AnimationKey.SICK)

    assert sprite.cells(DARK)[0][0][0].fg == "#00aa00"


def test_missing_variant_falls_back_to_default(art: Path) -> None:
    draw(art, "default", "adult", "idle")

    assert load(Variant.GOOD, LifeStage.ADULT, AnimationKey.IDLE) is load(
        Variant.DEFAULT, LifeStage.ADULT, AnimationKey.IDLE
    )


def test_missing_animation_falls_back_to_idle(art: Path) -> None:
    draw(art, "default", "child", "idle")

    assert load(Variant.DEFAULT, LifeStage.CHILD, AnimationKey.EAT) is load(
        Variant.DEFAULT, LifeStage.CHILD, AnimationKey.IDLE
    )


def test_default_variant_animation_is_used_for_a_missing_variant_animation(art: Path) -> None:
    draw(art, "default", "adult", "eat")

    assert load(Variant.GOOD, LifeStage.ADULT, AnimationKey.EAT) is load(
        Variant.DEFAULT, LifeStage.ADULT, AnimationKey.EAT
    )


def test_variant_idle_is_preferred_over_a_missing_default_animation(art: Path) -> None:
    draw(art, "good", "adult", "idle")

    sprite = load(Variant.GOOD, LifeStage.ADULT, AnimationKey.EAT)

    assert sprite is load(Variant.GOOD, LifeStage.ADULT, AnimationKey.IDLE)
    assert sprite.frames(DARK)[0].plain == "██"


def test_no_art_at_all_is_a_placeholder(art: Path) -> None:
    assert load(Variant.GOOD, LifeStage.TEEN, AnimationKey.EAT) is PLACEHOLDER


def test_undefined_colours_make_a_placeholder(art: Path, caplog: pytest.LogCaptureFixture) -> None:
    draw(art, "default", "child", "idle", '[[frames]]\npixels = "zz\\nzz"\n')

    assert load(Variant.DEFAULT, LifeStage.CHILD, AnimationKey.IDLE) is PLACEHOLDER
    assert "['z']" in caplog.text


def test_broken_art_uses_a_placeholder_and_logs(
    art: Path, caplog: pytest.LogCaptureFixture
) -> None:
    draw(art, "default", "child", "idle", "fps = ")

    assert load(Variant.DEFAULT, LifeStage.CHILD, AnimationKey.IDLE) is PLACEHOLDER
    assert "idle.toml" in caplog.text


def test_missing_base_palette_is_logged(art: Path, caplog: pytest.LogCaptureFixture) -> None:
    assert load_base("nobody") is None
    assert "base.toml" in caplog.text


def test_broken_base_palette_is_logged(art: Path, caplog: pytest.LogCaptureFixture) -> None:
    (art / "critter" / "base.toml").write_text("[palette]\nk = 3\n", encoding="utf-8")

    assert load_base("critter") is None
    assert "Invalid palette" in caplog.text


def test_placeholder_renders_something() -> None:
    assert all(PLACEHOLDER.frames(look)[0].plain == "?" for look in LOOKS)


# --- Overlays -----------------------------------------------------------------------------------


@pytest.mark.parametrize("name", OVERLAY_NAMES)
def test_every_overlay_exists(name: str) -> None:
    assert load_overlay(name) is not PLACEHOLDER


def test_missing_overlay_is_a_placeholder(art: Path, caplog: pytest.LogCaptureFixture) -> None:
    assert load_overlay("nope") is PLACEHOLDER
    assert "nope.toml" in caplog.text


def test_overlay_content_places_overlays_side_by_side() -> None:
    one = overlay_content(["poop"], DARK)
    two = overlay_content(["poop", "poop"], DARK)

    one_width = len(one.plain.split("\n")[0])
    assert len(two.plain.split("\n")[0]) == 2 * one_width + 2


def test_available_species_lists_directories_with_a_palette(art: Path) -> None:
    (art / "overlays").mkdir()
    (art / "overlays" / "base.toml").write_text('[palette]\nk = "#000000"\n', encoding="utf-8")
    (art / "sketch").mkdir()  # no base.toml: not a usable species
    (art / "notes.txt").write_text("", encoding="utf-8")

    assert sprites.available_species() == ("critter",)


def test_shipped_species() -> None:
    assert sprites.available_species() == ("bear", "owl", DEFAULT_SPECIES)


def test_pets_are_drawn_as_their_own_species() -> None:
    assert species_of(make_pet(species="owl")) == "owl"
