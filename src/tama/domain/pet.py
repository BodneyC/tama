"""The pet aggregate: an immutable snapshot of everything about the pet."""

import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from fractions import Fraction
from random import Random
from typing import Self

from tama.domain.balance import DEFAULT_BALANCE, Balance
from tama.domain.stage import DeathCause, LifeStage, Variant
from tama.domain.stats import Stat, Stats
from tama.errors import InvalidArgumentError

ZERO = timedelta(0)
MAX_NAME_LENGTH = 16
DEFAULT_SPECIES = "tama"
"""The original species; every pet saved before species existed is one."""
_SPECIES_NAME = re.compile(r"^[a-z][a-z0-9_-]*$")


@dataclass(frozen=True, slots=True)
class Drift:
    """Fractional progress towards the next whole-point change, per drifting stat.

    Keeping the remainder (rather than rounding each step) is what makes many small
    ``advance`` calls exactly equal to one large one. Values stay within ``(-1, 1)``.
    """

    hunger: Fraction = Fraction(0)
    happiness: Fraction = Fraction(0)
    energy: Fraction = Fraction(0)
    hygiene: Fraction = Fraction(0)
    health: Fraction = Fraction(0)

    def __getitem__(self, stat: Stat) -> Fraction:
        """Return the pending fraction for ``stat``."""
        value: Fraction = getattr(self, stat.value)
        return value

    def with_value(self, stat: Stat, value: Fraction) -> Self:
        """Return a copy with ``stat``'s pending fraction set to ``value``."""
        return replace(self, **{stat.value: value})


@dataclass(frozen=True, slots=True)
class Timers:
    """How long various conditions have persisted, for care-mistake and discipline rules."""

    hunger: timedelta = ZERO  # time spent at zero
    happiness: timedelta = ZERO
    hygiene: timedelta = ZERO
    lights_on_asleep: timedelta = ZERO
    misbehaving: timedelta = ZERO
    weight: timedelta = ZERO  # time spent outside the healthy weight band

    def neglect(self, need: Stat) -> timedelta:
        """Return how long ``need`` has been at zero."""
        value: timedelta = getattr(self, need.value)
        return value

    def with_neglect(self, need: Stat, value: timedelta) -> Self:
        """Return a copy with ``need``'s zero-duration set to ``value``."""
        return replace(self, **{need.value: value})


def _require_aware(when: datetime) -> None:
    if when.tzinfo is None or when.utcoffset() is None:
        raise InvalidArgumentError(f"datetime must be timezone-aware, got {when!r}")


@dataclass(frozen=True, slots=True)
class Pet:
    """A complete, immutable snapshot of a pet.

    Attributes:
        name: Display name (see ``validate_name``).
        born_at: When the egg was created.
        updated_at: The wall-clock time this snapshot corresponds to.
        lifespan: Age at which an elder dies of old age (seeded at birth).
        species: What kind of animal it is (see ``validate_species``); chosen at hatching.
        age: Simulated time lived, always a whole number of simulation steps.
        carry: Elapsed time not yet simulated because it is shorter than one step.
        sickness_doses: Medicine doses still needed; 0 means healthy.
        recent_snacks: Ages at which snacks were eaten within the last hour.
        poop_progress: Fraction of the way to the next poop.
        weight_progress: Fraction of the way to burning off the next gram (SPEC §2.7).
        paused_since: When the pet went on holiday (frozen in time), or ``None``.
        stay_awake: How much longer a pet the player woke stays up regardless of night or
            tiredness; zero once it's back to its normal sleep rules.
        woken_tantrum: Whether the current tantrum is from being woken, which earns no
            discipline when disciplined.
    """

    name: str
    born_at: datetime
    updated_at: datetime
    lifespan: timedelta
    species: str = DEFAULT_SPECIES
    stage: LifeStage = LifeStage.EGG
    variant: Variant = Variant.DEFAULT
    stats: Stats = field(default_factory=Stats)
    age: timedelta = ZERO
    carry: timedelta = ZERO
    weight: int = DEFAULT_BALANCE.start_weight
    poop_count: int = 0
    poop_progress: Fraction = Fraction(0)
    weight_progress: Fraction = Fraction(0)
    sickness_doses: int = 0
    is_asleep: bool = False
    lights_on: bool = True
    misbehaving: bool = False
    care_mistakes: int = 0
    drift: Drift = field(default_factory=Drift)
    timers: Timers = field(default_factory=Timers)
    recent_snacks: tuple[timedelta, ...] = ()
    cause_of_death: DeathCause | None = None
    paused_since: datetime | None = None
    stay_awake: timedelta = ZERO
    woken_tantrum: bool = False

    def __post_init__(self) -> None:
        """Validate invariants."""
        _require_aware(self.born_at)
        _require_aware(self.updated_at)
        if self.paused_since is not None:
            _require_aware(self.paused_since)
        validate_species(self.species)
        for name in ("poop_count", "sickness_doses", "care_mistakes"):
            if getattr(self, name) < 0:
                raise InvalidArgumentError(f"{name} must not be negative")
        if self.stay_awake < ZERO:
            raise InvalidArgumentError(f"stay_awake must not be negative, got {self.stay_awake}")
        if self.weight < 1:
            raise InvalidArgumentError(f"weight must be at least 1, got {self.weight}")

    @property
    def is_alive(self) -> bool:
        """Whether the pet is alive."""
        return self.stage is not LifeStage.DEAD

    @property
    def on_holiday(self) -> bool:
        """Whether the pet is paused: nothing happens to it until it is resumed."""
        return self.paused_since is not None

    @property
    def is_sick(self) -> bool:
        """Whether the pet needs medicine."""
        return self.sickness_doses > 0


def validate_name(name: str) -> str:
    """Return the normalised pet name, or raise ``InvalidArgumentError``.

    Names are stripped and must be 1-16 printable characters.
    """
    stripped = name.strip()
    if not stripped or len(stripped) > MAX_NAME_LENGTH or not stripped.isprintable():
        raise InvalidArgumentError(
            f"name must be 1-{MAX_NAME_LENGTH} printable characters, got {name!r}"
        )
    return stripped


def validate_species(species: str) -> str:
    """Return ``species`` if it is a valid species identifier, or raise ``InvalidArgumentError``.

    Species are lowercase identifiers (``tama``, ``owl``, ``polar-bear``). Which species have
    art is a UI concern; the domain only checks the name is well formed.
    """
    if not _SPECIES_NAME.match(species):
        raise InvalidArgumentError(
            f"species must be a lowercase name like 'owl' or 'polar-bear', got {species!r}"
        )
    return species


def new_egg(
    name: str,
    now: datetime,
    rng: Random,
    balance: Balance = DEFAULT_BALANCE,
    *,
    species: str = DEFAULT_SPECIES,
) -> Pet:
    """Create a fresh ``species`` egg called ``name`` at ``now``, lifespan drawn from ``rng``."""
    _require_aware(now)
    span_steps = (balance.lifespan_max - balance.lifespan_min) // balance.step
    lifespan = balance.lifespan_min + balance.step * rng.randint(0, span_steps)
    return Pet(
        name=validate_name(name),
        born_at=now,
        updated_at=now,
        lifespan=lifespan,
        species=validate_species(species),
        weight=balance.start_weight,
    )
