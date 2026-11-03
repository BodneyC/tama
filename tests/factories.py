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
from tama.domain.pet import Pet, new_egg
from tama.domain.stage import LifeStage
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

    The pet's age is set to the entry age of ``stage`` unless ``age`` is overridden, so it
    won't immediately evolve on the next step.
    """
    pet = new_egg("Mochi", FIXED_NOW, Random(0))
    age = DEFAULT_BALANCE.stage_age(stage) if stage is not LifeStage.DEAD else timedelta(days=15)
    fields: dict[str, Any] = {"stage": stage, "age": age, "stats": stats or Stats()}
    fields.update(overrides)
    return replace(pet, **fields)
