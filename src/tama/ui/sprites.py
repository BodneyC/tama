"""Pixel-art sprites: loading, validation and rendering to block characters (ADR 0003, 0004).

Layout under ``tama/assets/sprites/``::

    <species>/base.toml                          # palette shared by the species (+ UI overrides)
    <species>/<variant>/<stage>/<animation>.toml # frames, plus optional palette overrides
    overlays/base.toml, overlays/<name>.toml     # status indicators, same scheme

Every palette colour has a dark-theme and a light-theme value. Each terminal cell shows two
vertically stacked pixels using ``▀``/``▄``/``█``/space with foreground and background colours; a
cell whose two pixels share a shaded palette entry is drawn with ``░``/``▒``/``▓``.

Missing or broken art falls back to the default variant, then to ``idle``, then to a
placeholder, so it never crashes the game.
"""

import logging
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from importlib.resources import files
from importlib.resources.abc import Traversable
from typing import Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveFloat,
    ValidationError,
    field_validator,
    model_validator,
)
from textual.content import Content

from tama.domain.animation import AnimationKey
from tama.domain.pet import Pet
from tama.domain.stage import LifeStage, Variant
from tama.ui.colours import (
    HEX_COLOUR,
    HEX_OR_THEME_COLOUR,
    LOOKS,
    Look,
    Mode,
    expand_mode_colour,
)

logger = logging.getLogger(__name__)

OVERLAYS = "overlays"
TRANSPARENT = "."
MONO_INK_THRESHOLD = 0.45
"""In monochrome, pixels on the far side of this luminance from the background are drawn."""
MAX_WIDTH = 32
MAX_HEIGHT = 20


class Shade(StrEnum):
    """Texture for a palette entry, drawn with a shade glyph."""

    LIGHT = "light"
    MEDIUM = "medium"
    DARK = "dark"


SHADE_GLYPHS = {Shade.LIGHT: "░", Shade.MEDIUM: "▒", Shade.DARK: "▓"}


# --- File formats -----------------------------------------------------------------------------


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PaletteEntry(_Strict):
    """A palette colour for each theme mode, optionally textured with a shade glyph."""

    dark: str = Field(pattern=HEX_COLOUR, description="hex colour on dark themes")
    light: str = Field(pattern=HEX_COLOUR, description="hex colour on light themes")
    shade: Shade | None = None

    @model_validator(mode="before")
    @classmethod
    def _expand(cls, value: Any) -> Any:  # noqa: ANN401 - raw TOML before validation
        return expand_mode_colour(value)

    def colour(self, mode: Mode) -> str:
        """The hex colour for ``mode``."""
        return self.dark if mode is Mode.DARK else self.light

    def luminance(self, mode: Mode) -> float:
        """Relative luminance (0 = black, 1 = white) in ``mode``, ignoring gamma for simplicity."""
        hex_colour = self.colour(mode)
        r, g, b = (int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b


class UiColour(_Strict):
    """A UI colour per mode: hex, or a Textual theme variable like ``$panel``."""

    dark: str = Field(pattern=HEX_OR_THEME_COLOUR)
    light: str = Field(pattern=HEX_OR_THEME_COLOUR)

    @model_validator(mode="before")
    @classmethod
    def _expand(cls, value: Any) -> Any:  # noqa: ANN401 - raw TOML before validation
        return expand_mode_colour(value)

    def colour(self, mode: Mode) -> str:
        """The value for ``mode``."""
        return self.dark if mode is Mode.DARK else self.light


Palette = dict[str, PaletteEntry]

UI_KEYS = frozenset(
    {
        "header-background",
        "header-text",
        "stat-good",
        "stat-warning",
        "stat-bad",
        "attention",
        "accent",
        "lights-off",
    }
)
"""UI colours a species can override (each becomes the CSS variable ``$tama-<key>``)."""


def _check_palette_keys(value: Any) -> Any:  # noqa: ANN401 - raw TOML before validation
    if isinstance(value, dict):
        for key in value:
            if not isinstance(key, str) or len(key) != 1:
                raise ValueError(f"palette keys must be a single character, got {key!r}")
            if key == TRANSPARENT:
                raise ValueError(f"{TRANSPARENT!r} is reserved for transparent pixels")
    return value


class BaseFile(_Strict):
    """A species' ``base.toml``: its palette, and optional UI colour overrides."""

    palette: Palette
    ui: dict[str, UiColour] = Field(default_factory=dict)

    @field_validator("palette", mode="before")
    @classmethod
    def _palette_keys(cls, value: Any) -> Any:  # noqa: ANN401 - raw TOML before validation
        return _check_palette_keys(value)

    @field_validator("ui")
    @classmethod
    def _known_ui_keys(cls, value: dict[str, UiColour]) -> dict[str, UiColour]:
        unknown = set(value) - UI_KEYS
        if unknown:
            raise ValueError(
                f"unknown UI colours {sorted(unknown)}; expected some of {sorted(UI_KEYS)}"
            )
        return value

    @classmethod
    def parse(cls, text: str) -> Self:
        """Parse and validate TOML text."""
        return cls.model_validate(tomllib.loads(text))


class FrameModel(_Strict):
    """One frame: a rectangular grid of palette characters."""

    pixels: str

    @property
    def rows(self) -> tuple[str, ...]:
        """The pixel rows, without blank leading/trailing lines."""
        return tuple(self.pixels.strip("\n").split("\n"))


class SpriteFile(_Strict):
    """One animation file. Its ``[palette]`` only overrides or extends the species palette."""

    fps: PositiveFloat = 2
    loop: bool = True
    palette: Palette = Field(default_factory=dict)
    frames: list[FrameModel] = Field(min_length=1)

    @field_validator("palette", mode="before")
    @classmethod
    def _palette_keys(cls, value: Any) -> Any:  # noqa: ANN401 - raw TOML before validation
        return _check_palette_keys(value)

    @model_validator(mode="after")
    def _check_frames(self) -> Self:
        size: tuple[int, int] | None = None
        for number, frame in enumerate(self.frames, start=1):
            rows = frame.rows
            width, height = len(rows[0]), len(rows)
            if any(len(row) != width for row in rows):
                raise ValueError(f"frame {number}: every row must be the same length")
            if height % 2:
                raise ValueError(f"frame {number}: pixel height must be even, got {height}")
            if width > MAX_WIDTH:
                raise ValueError(f"frame {number}: {width} pixels is too wide (max {MAX_WIDTH})")
            if height > MAX_HEIGHT:
                raise ValueError(f"frame {number}: {height} pixels is too tall (max {MAX_HEIGHT})")
            if size is not None and (width, height) != size:
                raise ValueError(f"frame {number}: all frames must be the same size as frame 1")
            size = (width, height)
        return self

    def missing_colours(self, palette: Mapping[str, PaletteEntry]) -> set[str]:
        """Pixel characters used in the frames that ``palette`` doesn't define."""
        used = {p for frame in self.frames for row in frame.rows for p in row}
        return used - set(palette) - {TRANSPARENT}

    @classmethod
    def parse(cls, text: str) -> Self:
        """Parse and validate TOML text.

        Raises:
            tomllib.TOMLDecodeError: If the text is not TOML.
            pydantic.ValidationError: If it is not a valid sprite.
        """
        return cls.model_validate(tomllib.loads(text))


# --- Rendering --------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Cell:
    """One terminal cell of a rendered sprite."""

    glyph: str
    fg: str | None = None
    bg: str | None = None


CellGrid = tuple[tuple[Cell, ...], ...]
"""One rendered frame: rows of terminal cells."""


def _cell(top: PaletteEntry | None, bottom: PaletteEntry | None, look: Look) -> Cell:
    def fg(entry: PaletteEntry) -> str | None:
        return entry.colour(look.mode) if look.color else None

    match top, bottom:
        case None, None:
            return Cell(" ")
        case PaletteEntry() as t, None:
            return Cell("▀", fg=fg(t))
        case None, PaletteEntry() as b:
            return Cell("▄", fg=fg(b))
        case PaletteEntry() as t, PaletteEntry() as b if t == b and t.shade is not None:
            return Cell(SHADE_GLYPHS[t.shade], fg=fg(t))
        case PaletteEntry() as t, PaletteEntry() as b if (
            t.colour(look.mode) == b.colour(look.mode) or not look.color
        ):
            return Cell("█", fg=fg(t))
        case PaletteEntry() as t, PaletteEntry() as b:
            return Cell("▀", fg=t.colour(look.mode), bg=b.colour(look.mode))
    raise AssertionError("unreachable")  # pragma: no cover - the cases above are exhaustive


def _is_ink(entry: PaletteEntry, mode: Mode) -> bool:
    """In monochrome, whether a pixel contrasts with the background and so gets drawn."""
    light_pixel = entry.luminance(mode) >= MONO_INK_THRESHOLD
    return light_pixel if mode is Mode.DARK else not light_pixel


def render_cells(rows: Sequence[str], palette: Mapping[str, PaletteEntry], look: Look) -> CellGrid:
    """Turn pixel rows (even count) into terminal cells, two pixels per cell.

    In monochrome (``look.color`` False) nothing is coloured, and only pixels that contrast
    with the background are drawn: light pixels on dark themes, dark pixels (outline, eyes,
    mouth) on light themes, so the features always show.
    """

    def entry(pixel: str) -> PaletteEntry | None:
        if pixel == TRANSPARENT:
            return None
        found = palette[pixel]
        if not look.color and not _is_ink(found, look.mode):
            return None
        return found

    return tuple(
        tuple(_cell(entry(t), entry(b), look) for t, b in zip(top, bottom, strict=True))
        for top, bottom in zip(rows[0::2], rows[1::2], strict=True)
    )


def _style(cell: Cell) -> str:
    if cell.fg and cell.bg:
        return f"{cell.fg} on {cell.bg}"
    return cell.fg or ""


def to_content(cells: Sequence[Sequence[Cell]]) -> Content:
    """Assemble rendered cells into styled Textual content, one line per row."""
    lines = [Content.assemble(*[(c.glyph, _style(c)) for c in row]) for row in cells]
    return Content("\n").join(lines)


def hstack(grids: Sequence[CellGrid], gap: int = 1) -> CellGrid:
    """Place cell grids side by side, bottom-aligned, ``gap`` blank cells apart."""
    if not grids:
        return ()
    height = max(len(grid) for grid in grids)
    rows: list[list[Cell]] = [[] for _ in range(height)]
    for index, grid in enumerate(grids):
        width = max((len(row) for row in grid), default=0)
        padded = [(Cell(" "),) * width] * (height - len(grid)) + list(grid)
        for row, cells in zip(rows, padded, strict=True):
            if index:
                row.extend([Cell(" ")] * gap)
            row.extend(cells)
    return tuple(tuple(row) for row in rows)


# --- Sprites ----------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Sprite:
    """A loaded animation, pre-rendered for every look (dark/light × colour/monochrome)."""

    fps: float
    loop: bool
    renders: Mapping[Look, tuple[CellGrid, ...]]
    contents: Mapping[Look, tuple[Content, ...]]

    def cells(self, look: Look) -> tuple[CellGrid, ...]:
        """The frames as cell grids (for composing several sprites side by side)."""
        return self.renders[look]

    def frames(self, look: Look) -> tuple[Content, ...]:
        """The frames as styled content."""
        return self.contents[look]

    @classmethod
    def from_renders(
        cls, fps: float, renders: Mapping[Look, tuple[CellGrid, ...]], *, loop: bool
    ) -> Self:
        """Build a sprite from rendered cell grids."""
        contents = {look: tuple(map(to_content, grids)) for look, grids in renders.items()}
        return cls(fps, loop, renders, contents)

    @classmethod
    def from_file(cls, parsed: SpriteFile, palette: Mapping[str, PaletteEntry]) -> Self:
        """Render every frame of a parsed sprite file with ``palette``, for every look."""
        renders = {
            look: tuple(render_cells(f.rows, palette, look) for f in parsed.frames)
            for look in LOOKS
        }
        return cls.from_renders(parsed.fps, renders, loop=parsed.loop)


_PLACEHOLDER_GRID: CellGrid = ((Cell("?"),),)
PLACEHOLDER = Sprite.from_renders(1, dict.fromkeys(LOOKS, (_PLACEHOLDER_GRID,)), loop=True)


# --- Loading ----------------------------------------------------------------------------------


def sprite_root() -> Traversable:
    """The directory holding all sprite files."""
    return files("tama.assets") / "sprites"


@cache
def load_base(collection: str) -> BaseFile | None:
    """Load a species' (or the overlays') ``base.toml``; ``None`` if missing or invalid."""
    resource = sprite_root() / collection / "base.toml"
    if not resource.is_file():
        logger.warning("Missing palette %s", resource)
        return None
    try:
        return BaseFile.parse(resource.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, ValidationError):
        logger.exception("Invalid palette file %s", resource)
        return None


def _parse_resource(resource: Traversable, collection: str) -> Sprite:
    base = load_base(collection)
    try:
        parsed = SpriteFile.parse(resource.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, ValidationError):
        logger.exception("Invalid sprite file %s", resource)
        return PLACEHOLDER
    palette = {**(base.palette if base else {}), **parsed.palette}
    missing = parsed.missing_colours(palette)
    if missing:
        logger.error("Sprite %s uses colours %s that no palette defines", resource, sorted(missing))
        return PLACEHOLDER
    return Sprite.from_file(parsed, palette)


def _resource(
    species: str, variant: Variant, stage: LifeStage, animation: AnimationKey
) -> Traversable:
    return sprite_root() / species / variant / stage / f"{animation}.toml"


@cache
def load_sprite(
    species: str, variant: Variant, stage: LifeStage, animation: AnimationKey
) -> Sprite:
    """Load (and cache) a sprite.

    Fallback order: this variant's animation, the default variant's animation, this variant's
    idle, the default variant's idle, then a placeholder. Broken files are logged and treated
    as a placeholder.
    """
    resource = _resource(species, variant, stage, animation)
    if resource.is_file():
        return _parse_resource(resource, species)
    if (
        variant is not Variant.DEFAULT
        and _resource(species, Variant.DEFAULT, stage, animation).is_file()
    ):
        return load_sprite(species, Variant.DEFAULT, stage, animation)
    if animation is not AnimationKey.IDLE:
        return load_sprite(species, variant, stage, AnimationKey.IDLE)
    if variant is not Variant.DEFAULT:
        return load_sprite(species, Variant.DEFAULT, stage, AnimationKey.IDLE)
    return PLACEHOLDER


@cache
def load_overlay(name: str) -> Sprite:
    """Load (and cache) an overlay sprite from ``sprites/overlays/<name>.toml``."""
    resource = sprite_root() / OVERLAYS / f"{name}.toml"
    if not resource.is_file():
        logger.warning("Missing overlay sprite %s", resource)
        return PLACEHOLDER
    return _parse_resource(resource, OVERLAYS)


def overlay_content(names: Sequence[str], look: Look) -> Content:
    """Render overlay sprites (first frame of each) side by side."""
    grids = [load_overlay(name).cells(look)[0] for name in names]
    return to_content(hstack(grids, gap=2))


def species_of(pet: Pet) -> str:
    """Which species' art to draw ``pet`` with."""
    return pet.species


def available_species() -> tuple[str, ...]:
    """Species that have art (a directory with a ``base.toml``), sorted."""
    root = sprite_root()
    return tuple(
        sorted(
            entry.name
            for entry in root.iterdir()
            if entry.is_dir() and entry.name != OVERLAYS and (entry / "base.toml").is_file()
        )
    )


def clear_caches() -> None:
    """Forget loaded sprites and palettes (tests, or after regenerating art)."""
    load_base.cache_clear()
    load_sprite.cache_clear()
    load_overlay.cache_clear()
