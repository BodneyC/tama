"""UI colours: defaults per theme mode, overridable per species (ADR 0004).

``assets/ui.toml`` holds the defaults; a species' ``base.toml`` may override any of them in its
``[ui]`` table. ``css_variables`` turns the result into ``$tama-<name>`` CSS variables for the
active theme, resolving ``$theme-variable`` references against that theme's colours.
"""

import logging
import tomllib
from collections.abc import Mapping
from functools import cache
from importlib.resources import files
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from tama.ui.colours import Mode
from tama.ui.sprites import UI_KEYS, UiColour, load_base

logger = logging.getLogger(__name__)

CSS_PREFIX = "tama-"
FALLBACK_COLOUR = "#ff00ff"
"""Used (and logged) if a colour refers to a theme variable that doesn't exist."""


class UiFile(BaseModel):
    """``assets/ui.toml``: a value for every UI colour."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ui: dict[str, UiColour]

    @model_validator(mode="after")
    def _complete(self) -> Self:
        if set(self.ui) != UI_KEYS:
            missing, extra = sorted(UI_KEYS - set(self.ui)), sorted(set(self.ui) - UI_KEYS)
            raise ValueError(
                f"ui.toml must define exactly the UI colours; missing {missing}, unknown {extra}"
            )
        return self


@cache
def default_ui() -> dict[str, UiColour]:
    """The default UI colours shipped in ``assets/ui.toml``."""
    text = (files("tama.assets") / "ui.toml").read_text(encoding="utf-8")
    return UiFile.model_validate(tomllib.loads(text)).ui


def ui_palette(species: str) -> dict[str, UiColour]:
    """The UI colours for ``species``: defaults, overridden by its ``base.toml``."""
    base = load_base(species)
    return {**default_ui(), **(base.ui if base else {})}


def css_variables(
    palette: Mapping[str, UiColour], *, mode: Mode, theme_colours: Mapping[str, str]
) -> dict[str, str]:
    """``$tama-*`` CSS variables for ``mode``, with ``$name`` values looked up in the theme."""
    variables: dict[str, str] = {}
    for name, colour in palette.items():
        value = colour.colour(mode)
        if value.startswith("$"):
            reference = value[1:]
            if reference not in theme_colours:
                logger.warning("UI colour %s refers to unknown theme colour %s", name, value)
            value = theme_colours.get(reference, FALLBACK_COLOUR)
        variables[CSS_PREFIX + name] = value
    return variables
