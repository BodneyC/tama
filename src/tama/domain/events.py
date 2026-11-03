"""Things that happen to the pet.

Domain functions return events alongside the new state; the UI decides how to present them
(animations, toasts, the "while you were away" summary). Every event records the pet's
``age`` when it happened.
"""

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from tama.domain.minigames import GameResult
from tama.domain.pet import Pet
from tama.domain.stage import DeathCause, LifeStage, Variant
from tama.domain.stats import Stat


class Action(StrEnum):
    """Player verbs that change the pet (see SPEC §3)."""

    MEAL = "meal"
    SNACK = "snack"
    PLAY = "play"
    CLEAN = "clean"
    MEDICINE = "medicine"
    LIGHTS = "lights"
    DISCIPLINE = "discipline"


class RefusalReason(StrEnum):
    """Why an action was refused."""

    DEAD = "dead"
    EGG = "egg"
    ASLEEP = "asleep"
    NOT_HUNGRY = "not_hungry"
    TOO_TIRED = "too_tired"
    NOT_SICK = "not_sick"


class MistakeReason(StrEnum):
    """What a care mistake was for."""

    HUNGER = "hunger"
    HAPPINESS = "happiness"
    HYGIENE = "hygiene"
    LIGHTS = "lights"


@dataclass(frozen=True, slots=True)
class Event:
    """Base class for all events."""

    age: timedelta


# --- Simulation events ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Evolved(Event):
    """The pet moved to a new life stage (EGG -> BABY is hatching)."""

    from_stage: LifeStage
    to_stage: LifeStage
    variant: Variant


@dataclass(frozen=True, slots=True)
class Died(Event):
    """The pet died."""

    cause: DeathCause


@dataclass(frozen=True, slots=True)
class FellAsleep(Event):
    """The pet went to sleep."""


@dataclass(frozen=True, slots=True)
class WokeUp(Event):
    """The pet woke up."""


@dataclass(frozen=True, slots=True)
class Pooped(Event):
    """The pet pooped; ``count`` is the number of poops now on screen."""

    count: int


@dataclass(frozen=True, slots=True)
class GotSick(Event):
    """The pet fell ill and needs ``doses`` of medicine."""

    doses: int


@dataclass(frozen=True, slots=True)
class NeedLow(Event):
    """A need dropped below the attention threshold."""

    stat: Stat


@dataclass(frozen=True, slots=True)
class CareMistake(Event):
    """The player neglected the pet."""

    reason: MistakeReason


@dataclass(frozen=True, slots=True)
class Misbehaved(Event):
    """The pet is calling for attention without a real need."""


@dataclass(frozen=True, slots=True)
class MisbehaviourIgnored(Event):
    """Misbehaviour went undisciplined for too long."""


# --- Action events ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Ate(Event):
    """The pet ate a meal or a snack."""

    food: Action


@dataclass(frozen=True, slots=True)
class Played(Event):
    """A mini-game finished, with ``result`` from the player's side."""

    result: GameResult


@dataclass(frozen=True, slots=True)
class Cleaned(Event):
    """The player cleaned up."""

    poops_removed: int


@dataclass(frozen=True, slots=True)
class MedicineGiven(Event):
    """A dose of medicine was given; ``cured`` if it was the last one needed."""

    cured: bool


@dataclass(frozen=True, slots=True)
class LightsToggled(Event):
    """The lights were switched."""

    on: bool


@dataclass(frozen=True, slots=True)
class Disciplined(Event):
    """The pet was disciplined; ``effective`` if it was actually misbehaving."""

    effective: bool


@dataclass(frozen=True, slots=True)
class Refused(Event):
    """An action was refused and had no effect."""

    action: Action
    reason: RefusalReason


# --- Results ----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Outcome:
    """The result of a domain operation: the new pet plus what happened, in order."""

    pet: Pet
    events: tuple[Event, ...] = ()

    @property
    def refusal(self) -> RefusalReason | None:
        """The refusal reason if this outcome is a refused action, else ``None``."""
        match self.events:
            case (Refused(reason=reason),):
                return reason
            case _:
                return None
