"""The on-disk save format and its mapping to and from the domain.

The domain stays free of Pydantic: these models mirror the domain types and are converted at
the boundary. Durations are ISO 8601 strings, fractions are exact ``"n/d"`` strings, and
timestamps must carry a UTC offset, so a save round-trips exactly (see ADR 0002).
"""

from dataclasses import dataclass
from datetime import timedelta
from fractions import Fraction
from random import Random
from typing import Any, Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, NonNegativeInt, PositiveInt

from tama import __version__
from tama.domain.pet import Drift, Pet, Timers
from tama.domain.stage import DeathCause, LifeStage, Variant
from tama.domain.stats import Stats
from tama.errors import CorruptSaveError, InvalidArgumentError

CURRENT_SCHEMA_VERSION = 4

# typeshed types Random.getstate() as tuple[Any, ...]; in CPython it is
# (version: int, internal: tuple[int, ...] of length 625, gauss_next: float | None).
RngState = tuple[Any, ...]


@dataclass(frozen=True, slots=True)
class SaveGame:
    """Everything needed to resume a game exactly where it left off."""

    pet: Pet
    rng_state: RngState


def restore_rng(state: RngState) -> Random:
    """Return a ``Random`` continuing from ``state``."""
    rng = Random()
    rng.setstate(state)
    return rng


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class StatsModel(_Model):
    """Serialized ``Stats``."""

    hunger: int
    happiness: int
    energy: int
    hygiene: int
    health: int
    discipline: int


class DriftModel(_Model):
    """Serialized ``Drift``."""

    hunger: Fraction
    happiness: Fraction
    energy: Fraction
    hygiene: Fraction
    health: Fraction


class TimersModel(_Model):
    """Serialized ``Timers``."""

    hunger: timedelta
    happiness: timedelta
    hygiene: timedelta
    lights_on_asleep: timedelta
    misbehaving: timedelta


class PetModel(_Model):
    """Serialized ``Pet``. Field names match the domain one-to-one."""

    name: str
    born_at: AwareDatetime
    updated_at: AwareDatetime
    lifespan: timedelta
    species: str
    stage: LifeStage
    variant: Variant
    stats: StatsModel
    age: timedelta
    carry: timedelta
    weight: PositiveInt
    poop_count: NonNegativeInt
    poop_progress: Fraction
    sickness_doses: NonNegativeInt
    is_asleep: bool
    lights_on: bool
    misbehaving: bool
    care_mistakes: NonNegativeInt
    drift: DriftModel
    timers: TimersModel
    recent_snacks: tuple[timedelta, ...]
    cause_of_death: DeathCause | None
    paused_since: AwareDatetime | None
    stay_awake: timedelta
    woken_tantrum: bool


class RngStateModel(_Model):
    """Serialized ``random.Random`` state."""

    version: int
    internal: tuple[int, ...]
    gauss_next: float | None


class SaveFileV4(_Model):
    """Version 4 of the save file.

    v1 + the pet's species in v2 + holiday in v3 + being woken by the player in v4.
    """

    schema_version: Literal[4] = 4
    app_version: str = __version__
    pet: PetModel
    rng: RngStateModel

    @classmethod
    def from_domain(cls, game: SaveGame) -> Self:
        """Build the save model for ``game``."""
        pet = game.pet
        version, internal, gauss_next = game.rng_state
        return cls(
            pet=PetModel(
                name=pet.name,
                born_at=pet.born_at,
                updated_at=pet.updated_at,
                lifespan=pet.lifespan,
                species=pet.species,
                stage=pet.stage,
                variant=pet.variant,
                stats=StatsModel(**_fields(pet.stats)),
                age=pet.age,
                carry=pet.carry,
                weight=pet.weight,
                poop_count=pet.poop_count,
                poop_progress=pet.poop_progress,
                sickness_doses=pet.sickness_doses,
                is_asleep=pet.is_asleep,
                lights_on=pet.lights_on,
                misbehaving=pet.misbehaving,
                care_mistakes=pet.care_mistakes,
                drift=DriftModel(**_fields(pet.drift)),
                timers=TimersModel(**_fields(pet.timers)),
                recent_snacks=pet.recent_snacks,
                cause_of_death=pet.cause_of_death,
                paused_since=pet.paused_since,
                stay_awake=pet.stay_awake,
                woken_tantrum=pet.woken_tantrum,
            ),
            rng=RngStateModel(version=version, internal=internal, gauss_next=gauss_next),
        )

    def to_domain(self) -> SaveGame:
        """Convert back to domain objects.

        Raises:
            CorruptSaveError: If the data is well-formed JSON but violates a domain invariant
                (e.g. a stat out of range) or holds an invalid RNG state.
        """
        p = self.pet
        try:
            pet = Pet(
                name=p.name,
                born_at=p.born_at,
                updated_at=p.updated_at,
                lifespan=p.lifespan,
                species=p.species,
                stage=p.stage,
                variant=p.variant,
                stats=Stats(**_model_fields(p.stats)),
                age=p.age,
                carry=p.carry,
                weight=p.weight,
                poop_count=p.poop_count,
                poop_progress=p.poop_progress,
                sickness_doses=p.sickness_doses,
                is_asleep=p.is_asleep,
                lights_on=p.lights_on,
                misbehaving=p.misbehaving,
                care_mistakes=p.care_mistakes,
                drift=Drift(**_model_fields(p.drift)),
                timers=Timers(**_model_fields(p.timers)),
                recent_snacks=p.recent_snacks,
                cause_of_death=p.cause_of_death,
                paused_since=p.paused_since,
                stay_awake=p.stay_awake,
                woken_tantrum=p.woken_tantrum,
            )
        except InvalidArgumentError as exc:
            raise CorruptSaveError(f"invalid pet data: {exc}") from exc
        state: RngState = (self.rng.version, self.rng.internal, self.rng.gauss_next)
        try:
            restore_rng(state)
        except (ValueError, TypeError) as exc:
            raise CorruptSaveError(f"invalid RNG state: {exc}") from exc
        return SaveGame(pet, state)


def _fields(obj: Stats | Drift | Timers) -> dict[str, Any]:
    return {name: getattr(obj, name) for name in obj.__slots__}


def _model_fields(model: BaseModel) -> dict[str, Any]:
    # Not model_dump(): that serializes some types (e.g. Fraction -> str) even in Python mode.
    return {name: getattr(model, name) for name in type(model).model_fields}
