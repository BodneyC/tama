"""User configuration (SPEC §7).

Precedence: CLI flags (``Config.with_overrides``) > config file (``load_config``) > defaults.
"""

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import time, timedelta
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, NonNegativeFloat, StrictBool, ValidationError

from tama.errors import ConfigError


@dataclass(frozen=True, slots=True)
class Config:
    """Effective user settings.

    Attributes:
        bell: Ring the terminal bell on new attention calls.
        reduced_motion: Disable wandering and limit animations to key frames.
        night_start: Local time the pet's night begins.
        night_end: Local time the pet's night ends.
        offline_cap: Most offline time simulated on load; beyond it a "pet sitter" takes over.
        theme: Textual theme name, or ``None`` for the default.
    """

    bell: bool = False
    reduced_motion: bool = False
    night_start: time = time(22)
    night_end: time = time(7)
    offline_cap: timedelta = timedelta(hours=72)
    theme: str | None = None

    def with_overrides(
        self, *, bell: bool | None = None, reduced_motion: bool | None = None
    ) -> Self:
        """Apply CLI flags; ``None`` means the flag wasn't given and the setting is kept."""
        return replace(
            self,
            bell=self.bell if bell is None else bell,
            reduced_motion=self.reduced_motion if reduced_motion is None else reduced_motion,
        )


class _ConfigFile(BaseModel):
    """The TOML file's schema. Every key is optional."""

    model_config = ConfigDict(extra="forbid")

    bell: StrictBool | None = None
    reduced_motion: StrictBool | None = None
    night_start: time | None = None
    night_end: time | None = None
    offline_cap_hours: NonNegativeFloat | None = None
    theme: str | None = None


def load_config(path: Path) -> Config:
    """Read the config file at ``path``; a missing file means all defaults.

    Raises:
        ConfigError: If the file can't be read, isn't valid TOML, or has bad values.
    """
    try:
        with path.open("rb") as file:
            raw = tomllib.load(file)
    except FileNotFoundError:
        return Config()
    except OSError as exc:
        raise ConfigError(f"could not read config file {path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"config file {path} is not valid TOML: {exc}") from exc
    try:
        parsed = _ConfigFile.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"config file {path} has invalid settings: {exc}") from exc

    defaults = Config()
    return Config(
        bell=_pick(parsed.bell, defaults.bell),
        reduced_motion=_pick(parsed.reduced_motion, defaults.reduced_motion),
        night_start=_pick(parsed.night_start, defaults.night_start),
        night_end=_pick(parsed.night_end, defaults.night_end),
        offline_cap=(
            defaults.offline_cap
            if parsed.offline_cap_hours is None
            else timedelta(hours=parsed.offline_cap_hours)
        ),
        theme=_pick(parsed.theme, defaults.theme),
    )


def no_color_requested(env: Mapping[str, str] = os.environ) -> bool:
    """Whether the user asked for no colour (https://no-color.org: set and non-empty)."""
    return bool(env.get("NO_COLOR"))


def _pick[T](value: T | None, default: T) -> T:
    return default if value is None else value
