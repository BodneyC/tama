"""Enumerations about the pet's life: its stage, form, death and the tricks it can learn."""

from enum import StrEnum


class LifeStage(StrEnum):
    """Where the pet is in its life. Declared in chronological order."""

    EGG = "egg"
    BABY = "baby"
    CHILD = "child"
    TEEN = "teen"
    ADULT = "adult"
    ELDER = "elder"
    DEAD = "dead"

    @property
    def order(self) -> int:
        """Position in the life cycle (EGG is 0), for "at least this stage" comparisons."""
        return list(LifeStage).index(self)


class Variant(StrEnum):
    """Appearance variant. Pets are DEFAULT until adulthood, when care decides the rest."""

    DEFAULT = "default"
    GOOD = "good"
    SCRUFFY = "scruffy"
    CHUBBY = "chubby"


class DeathCause(StrEnum):
    """Why a pet died."""

    POOR_HEALTH = "poor_health"
    OLD_AGE = "old_age"


class Trick(StrEnum):
    """A trick a disciplined pet can perform, just for show (SPEC §2.10)."""

    WAVE = "wave"
    SPIN = "spin"
    DANCE = "dance"
    BOW = "bow"
