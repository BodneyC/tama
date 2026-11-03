"""Pet stats and the single clamping helper every stat change goes through."""

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Self

from tama.errors import InvalidArgumentError

STAT_MIN = 0
STAT_MAX = 100


class Stat(StrEnum):
    """The pet's numeric stats, each in ``STAT_MIN..STAT_MAX``."""

    HUNGER = "hunger"
    HAPPINESS = "happiness"
    ENERGY = "energy"
    HYGIENE = "hygiene"
    HEALTH = "health"
    DISCIPLINE = "discipline"


NEEDS: tuple[Stat, ...] = (Stat.HUNGER, Stat.HAPPINESS, Stat.HYGIENE)
"""Stats whose neglect (sitting at zero) damages health and counts as a care mistake."""

DRIFTING: tuple[Stat, ...] = (Stat.HUNGER, Stat.HAPPINESS, Stat.ENERGY, Stat.HYGIENE, Stat.HEALTH)
"""Stats that change on their own over time."""


def clamp(value: int, low: int = STAT_MIN, high: int = STAT_MAX) -> int:
    """Clamp ``value`` into ``low..high`` (the stat range by default)."""
    return max(low, min(high, value))


@dataclass(frozen=True, slots=True)
class Stats:
    """An immutable set of stat values. A new egg starts full, with no discipline."""

    hunger: int = STAT_MAX
    happiness: int = STAT_MAX
    energy: int = STAT_MAX
    hygiene: int = STAT_MAX
    health: int = STAT_MAX
    discipline: int = STAT_MIN

    def __post_init__(self) -> None:
        """Reject out-of-range values; use ``with_value``/``adjust`` to clamp instead."""
        for stat in Stat:
            value = self[stat]
            if not STAT_MIN <= value <= STAT_MAX:
                raise InvalidArgumentError(f"{stat} must be in {STAT_MIN}..{STAT_MAX}, got {value}")

    def __getitem__(self, stat: Stat) -> int:
        """Return the value of ``stat``."""
        value: int = getattr(self, stat.value)
        return value

    def with_value(self, stat: Stat, value: int) -> Self:
        """Return a copy with ``stat`` set to ``value`` (clamped)."""
        return replace(self, **{stat.value: clamp(value)})

    def adjust(self, stat: Stat, delta: int) -> Self:
        """Return a copy with ``delta`` added to ``stat`` (clamped)."""
        return self.with_value(stat, self[stat] + delta)
