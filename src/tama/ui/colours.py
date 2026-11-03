"""Colours that differ between dark and light themes (ADR 0004).

A colour value in any tama TOML file is either a single string (the same in both modes) or a
table ``{ dark = "...", light = "..." }``. ``color = "..."`` inside a table sets both modes and
can be combined with either key to override one of them.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

HEX_COLOUR = r"^#[0-9a-fA-F]{6}$"
HEX_OR_THEME_COLOUR = r"^(#[0-9a-fA-F]{6}|\$[a-z][a-z0-9-]*)$"


class Mode(StrEnum):
    """Which kind of theme is active."""

    DARK = "dark"
    LIGHT = "light"

    @classmethod
    def of(cls, *, dark: bool) -> "Mode":
        """The mode for a theme whose ``dark`` flag is ``dark``."""
        return cls.DARK if dark else cls.LIGHT


@dataclass(frozen=True, slots=True)
class Look:
    """How a sprite is drawn: for which mode, and whether in colour (``NO_COLOR`` → False)."""

    mode: Mode = Mode.DARK
    color: bool = True


LOOKS: tuple[Look, ...] = tuple(Look(mode, color) for mode in Mode for color in (True, False))


def expand_mode_colour(value: Any) -> Any:  # noqa: ANN401 - raw TOML, validated by the caller
    """Normalise the colour shorthands to a ``{"dark": ..., "light": ...}`` mapping."""
    if isinstance(value, str):
        return {"dark": value, "light": value}
    if isinstance(value, dict) and "color" in value:
        expanded = {k: v for k, v in value.items() if k != "color"}
        expanded.setdefault("dark", value["color"])
        expanded.setdefault("light", value["color"])
        return expanded
    return value
