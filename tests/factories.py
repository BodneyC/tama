"""Shared test builders.

Tests should use these rather than hand-constructing full objects, so that adding a field to
a domain type only requires updating one place.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta, tzinfo
from random import Random
from typing import Any

from tama.domain.balance import DEFAULT_BALANCE, Balance
from tama.domain.context import Context
from tama.domain.events import (
    Action,
    Ate,
    CareMistake,
    Died,
    Disciplined,
    Event,
    Evolved,
    Misbehaved,
    MistakeReason,
    Played,
)
from tama.domain.journal import Journal, record
from tama.domain.minigames import GameKind, GameResult
from tama.domain.pet import Pet, new_egg
from tama.domain.stage import DeathCause, LifeStage, Variant
from tama.domain.stats import Stats
from tama.infra.clock import FakeClock

FIXED_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
"""A stable, timezone-aware 'now' (midday UTC, i.e. daytime) for deterministic tests."""


def make_clock(now: datetime = FIXED_NOW) -> FakeClock:
    """Return a ``FakeClock`` starting at ``now``."""
    return FakeClock(now)


def make_ctx(seed: int = 0, balance: Balance = DEFAULT_BALANCE, tz: tzinfo = UTC) -> Context:
    """Return a simulation context with a seeded RNG."""
    return Context(rng=Random(seed), balance=balance, tz=tz)


def make_pet(
    *,
    stage: LifeStage = LifeStage.CHILD,
    stats: Stats | None = None,
    **overrides: Any,
) -> Pet:
    """Return a live, awake, healthy pet (a CHILD by default) with optional overrides.

    Its weight is the starting weight, moved into its stage's healthy band if need be.

    The pet's age is set to the entry age of ``stage`` unless ``age`` is overridden, so it
    won't immediately evolve on the next step.
    """
    pet = new_egg("Mochi", FIXED_NOW, Random(0))
    age = DEFAULT_BALANCE.stage_age(stage) if stage is not LifeStage.DEAD else timedelta(days=15)
    fields: dict[str, Any] = {"stage": stage, "age": age, "stats": stats or Stats()}
    if stage not in (LifeStage.EGG, LifeStage.DEAD):  # a healthy weight for its stage
        low, high = DEFAULT_BALANCE.weight_band(stage)
        fields["weight"] = min(max(pet.weight, low), high)
    fields.update(overrides)
    return replace(pet, **fields)


def make_journal(pet: Pet | None = None, *, moments: int = 4) -> Journal:
    """A plausible journal for a pet that lived to old age, with ``moments`` caught tantrums."""
    born = pet or make_pet(stage=LifeStage.EGG, age=timedelta(0))
    born = replace(born, age=timedelta(0), carry=timedelta(0), updated_at=born.born_at)
    hour, day = timedelta(hours=1), timedelta(days=1)
    four = GameKind.FOUR_IN_A_ROW
    events: list[Event] = [
        Evolved(timedelta(minutes=1), LifeStage.EGG, LifeStage.BABY, Variant.DEFAULT),
        Ate(timedelta(minutes=20), Action.MEAL),
        Evolved(hour, LifeStage.BABY, LifeStage.CHILD, Variant.DEFAULT),
        Played(2 * hour, GameResult.WIN, four),
        Misbehaved(3 * hour),
        *(Disciplined(3 * hour + i * day / 2, effective=True) for i in range(moments)),
        Evolved(day, LifeStage.CHILD, LifeStage.TEEN, Variant.DEFAULT),
        CareMistake(day + 5 * hour, MistakeReason.HUNGER),
        Evolved(3 * day, LifeStage.TEEN, LifeStage.ADULT, Variant.GOOD),
        Evolved(10 * day, LifeStage.ADULT, LifeStage.ELDER, Variant.GOOD),
        Died(15 * day, DeathCause.OLD_AGE),
    ]
    return record(Journal(), sorted(events, key=lambda e: e.age), born)
