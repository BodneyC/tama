"""Pixel-art sprites: loading, validation and rendering to block characters (ADR 0003).

Files live at ``tama/assets/sprites/<variant>/<stage>/<animation>.toml`` and hold a pixel grid
per frame plus a palette. Each terminal cell shows two vertically stacked pixels using
``▀``/``▄``/``█``/space with foreground and background colours; a cell whose two pixels share a
shaded palette entry is drawn with ``░``/``▒``/``▓``.

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
from tama.domain.stage import LifeStage, Variant

logger = logging.getLogger(__name__)

TRANSPARENT = "."
MONO_INK_THRESHOLD = 0.45
"""In monochrome, pixels darker than this (relative luminance) become gaps."""
MAX_WIDTH = 32
MAX_HEIGHT = 16
_HEX_COLOUR = r"^#[0-9a-fA-F]{6}$"


class Shade(StrEnum):
    """Texture for a palette entry, drawn with a shade glyph."""

    LIGHT = "light"
    MEDIUM = "medium"
    DARK = "dark"


SHADE_GLYPHS = {Shade.LIGHT: "░", Shade.MEDIUM: "▒", Shade.DARK: "▓"}


# --- File format ------------------------------------------------------------------------------


class PaletteEntry(BaseModel):
    """A palette colour, optionally textured with a shade glyph."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    color: str = Field(pattern=_HEX_COLOUR, description="hex colour like #f4b860")
    shade: Shade | None = None

    @property
    def luminance(self) -> float:
        """Relative luminance (0 = black, 1 = white), ignoring gamma for simplicity."""
        r, g, b = (int(self.color[i : i + 2], 16) / 255 for i in (1, 3, 5))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b


class FrameModel(BaseModel):
    """One frame: a rectangular grid of palette characters."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pixels: str

    @property
    def rows(self) -> tuple[str, ...]:
        """The pixel rows, without blank leading/trailing lines."""
        return tuple(self.pixels.strip("\n").split("\n"))


class SpriteFile(BaseModel):
    """A whole ``.toml`` sprite file."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fps: PositiveFloat = 2
    loop: bool = True
    palette: dict[str, PaletteEntry]
    frames: list[FrameModel] = Field(min_length=1)

    @field_validator("palette", mode="before")
    @classmethod
    def _expand_palette(cls, value: Any) -> Any:  # noqa: ANN401 - raw TOML before validation
        if not isinstance(value, dict):
            return value
        expanded: dict[str, Any] = {}
        for key, entry in value.items():
            if not isinstance(key, str) or len(key) != 1:
                raise ValueError(f"palette keys must be a single character, got {key!r}")
            if key == TRANSPARENT:
                raise ValueError(f"{TRANSPARENT!r} is reserved for transparent pixels")
            expanded[key] = {"color": entry} if isinstance(entry, str) else entry
        return expanded

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
            unknown = {p for row in rows for p in row} - set(self.palette) - {TRANSPARENT}
            if unknown:
                raise ValueError(f"frame {number}: pixels {sorted(unknown)} are not in the palette")
            if size is not None and (width, height) != size:
                raise ValueError(f"frame {number}: all frames must be the same size as frame 1")
            size = (width, height)
        return self

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


def _cell(top: PaletteEntry | None, bottom: PaletteEntry | None, *, color: bool) -> Cell:
    def fg(entry: PaletteEntry) -> str | None:
        return entry.color if color else None

    match top, bottom:
        case None, None:
            return Cell(" ")
        case PaletteEntry() as t, None:
            return Cell("▀", fg=fg(t))
        case None, PaletteEntry() as b:
            return Cell("▄", fg=fg(b))
        case PaletteEntry() as t, PaletteEntry() as b if t == b and t.shade is not None:
            return Cell(SHADE_GLYPHS[t.shade], fg=fg(t))
        case PaletteEntry() as t, PaletteEntry() as b if t.color == b.color or not color:
            return Cell("█", fg=fg(t))
        case PaletteEntry() as t, PaletteEntry() as b:
            return Cell("▀", fg=t.color, bg=b.color)
    raise AssertionError("unreachable")  # pragma: no cover - the cases above are exhaustive


def render_cells(
    rows: Sequence[str], palette: Mapping[str, PaletteEntry], *, color: bool
) -> list[list[Cell]]:
    """Turn pixel rows (even count) into terminal cells, two pixels per cell.

    With ``color=False`` nothing is coloured: light pixels are drawn and dark ones (outline,
    eyes, mouth) become gaps, so features still show as holes in the shape.
    """

    def entry(pixel: str) -> PaletteEntry | None:
        if pixel == TRANSPARENT:
            return None
        found = palette[pixel]
        if not color and found.luminance < MONO_INK_THRESHOLD:
            return None
        return found

    return [
        [_cell(entry(t), entry(b), color=color) for t, b in zip(top, bottom, strict=True)]
        for top, bottom in zip(rows[0::2], rows[1::2], strict=True)
    ]


def _style(cell: Cell) -> str:
    if cell.fg and cell.bg:
        return f"{cell.fg} on {cell.bg}"
    return cell.fg or ""


def to_content(cells: Sequence[Sequence[Cell]]) -> Content:
    """Assemble rendered cells into styled Textual content, one line per row."""
    lines = [Content.assemble(*[(c.glyph, _style(c)) for c in row]) for row in cells]
    return Content("\n").join(lines)


# --- Loading ----------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Sprite:
    """A loaded animation, pre-rendered in colour and monochrome."""

    fps: float
    loop: bool
    color_frames: tuple[Content, ...]
    mono_frames: tuple[Content, ...]

    def frames(self, *, color: bool) -> tuple[Content, ...]:
        """The rendered frames, in colour or monochrome (for ``NO_COLOR``)."""
        return self.color_frames if color else self.mono_frames

    @classmethod
    def from_file(cls, parsed: SpriteFile) -> Self:
        """Render every frame of a parsed sprite file."""

        def render(*, color: bool) -> tuple[Content, ...]:
            return tuple(
                to_content(render_cells(f.rows, parsed.palette, color=color)) for f in parsed.frames
            )

        return cls(parsed.fps, parsed.loop, render(color=True), render(color=False))


PLACEHOLDER = Sprite(fps=1, loop=True, color_frames=(Content("?"),), mono_frames=(Content("?"),))


def sprite_root() -> Traversable:
    """The directory holding all sprite files."""
    return files("tama.assets") / "sprites"


def _resource(variant: Variant, stage: LifeStage, animation: AnimationKey) -> Traversable:
    return sprite_root() / variant / stage / f"{animation}.toml"


@cache
def load_sprite(variant: Variant, stage: LifeStage, animation: AnimationKey) -> Sprite:
    """Load (and cache) a sprite.

    Fallback order: this variant's animation, the default variant's animation, this variant's
    idle, the default variant's idle, then a placeholder. Broken files are logged and treated
    as a placeholder.
    """
    resource = _resource(variant, stage, animation)
    if resource.is_file():
        try:
            return Sprite.from_file(SpriteFile.parse(resource.read_text(encoding="utf-8")))
        except (tomllib.TOMLDecodeError, ValidationError):
            logger.exception("Invalid sprite file %s", resource)
            return PLACEHOLDER
    if variant is not Variant.DEFAULT and _resource(Variant.DEFAULT, stage, animation).is_file():
        return load_sprite(Variant.DEFAULT, stage, animation)
    if animation is not AnimationKey.IDLE:
        return load_sprite(variant, stage, AnimationKey.IDLE)
    if variant is not Variant.DEFAULT:
        return load_sprite(Variant.DEFAULT, stage, AnimationKey.IDLE)
    return PLACEHOLDER
