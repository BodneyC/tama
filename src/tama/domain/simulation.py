"""The passage of time.

``advance`` is the single entry point. It simulates in fixed steps of ``Balance.step``;
elapsed time shorter than a step is carried over on the pet, and stat drift keeps its
fractional remainder. Random rolls only happen on whole hours of the pet's age. Together
these make ``advance(a + b)`` exactly equal to ``advance(a)`` followed by ``advance(b)``,
so live ticking and offline catch-up share one code path and one result.
"""

import math
from dataclasses import replace
from datetime import datetime, timedelta
from fractions import Fraction

from tama.domain import lifecycle
from tama.domain.balance import HOUR, Balance
from tama.domain.context import Context
from tama.domain.events import (
    CareMistake,
    Event,
    FellAsleep,
    GotSick,
    Misbehaved,
    MisbehaviourIgnored,
    MistakeReason,
    NeedLow,
    Outcome,
    Pooped,
    WokeUp,
)
from tama.domain.pet import ZERO, Pet
from tama.domain.stage import DeathCause, LifeStage
from tama.domain.stats import NEEDS, STAT_MAX, Stat
from tama.errors import InvalidArgumentError

_MICROSECOND = timedelta(microseconds=1)


def advance(pet: Pet, elapsed: timedelta, ctx: Context) -> Outcome:
    """Simulate ``elapsed`` time passing for ``pet``.

    Args:
        pet: The pet to advance.
        elapsed: Non-negative wall-clock time to simulate.
        ctx: RNG, balance and time zone.

    Returns:
        The advanced pet and the events that occurred, in order.

    Raises:
        InvalidArgumentError: If ``elapsed`` is negative.
    """
    if elapsed < ZERO:
        raise InvalidArgumentError(f"elapsed must not be negative, got {elapsed}")
    step = ctx.balance.step
    steps, carry = divmod(pet.carry + elapsed, step)
    last_step_at = pet.updated_at - pet.carry
    events: list[Event] = []
    current = pet
    for i in range(1, steps + 1):
        if not current.is_alive:
            break
        current = _step(current, last_step_at + step * i, ctx, events)
    advanced = replace(current, carry=carry, updated_at=pet.updated_at + elapsed)
    return Outcome(advanced, tuple(events))


def is_night(when: datetime, ctx: Context) -> bool:
    """Whether ``when`` falls in the night window, in the player's time zone."""
    local = when.astimezone(ctx.tz).time()
    start, end = ctx.balance.night_start, ctx.balance.night_end
    if start <= end:
        return start <= local < end
    return local >= start or local < end


def sickness_chance(pet: Pet, balance: Balance) -> float:
    """The probability the pet falls ill at the next hourly roll."""
    chance = balance.sickness_base_chance + balance.sickness_per_poop_chance * pet.poop_count
    if pet.stats.hygiene < balance.sickness_risk_threshold:
        chance += balance.sickness_dirty_chance
    if pet.stats.hunger < balance.sickness_risk_threshold:
        chance += balance.sickness_hungry_chance
    return min(chance, 1.0)


def _step(pet: Pet, now: datetime, ctx: Context, events: list[Event]) -> Pet:
    balance = ctx.balance
    pet = lifecycle.progress(replace(pet, age=pet.age + balance.step), balance, events)
    if pet.stage in (LifeStage.EGG, LifeStage.DEAD):
        return pet
    pet = _update_sleep(pet, now, ctx, events)
    pet = _apply_drift(pet, balance, events)
    if pet.stats.health == 0:
        return lifecycle.die(pet, DeathCause.POOR_HEALTH, events)
    pet = _update_poop(pet, balance, events)
    if pet.age % HOUR == ZERO:
        pet = _hourly_rolls(pet, ctx, events)
    return _update_timers(pet, balance, events)


def _per_step(balance: Balance, period: timedelta) -> Fraction:
    """Points gained per step for a rate of one point per ``period`` (exact)."""
    return Fraction(balance.step // _MICROSECOND, period // _MICROSECOND)


def _update_sleep(pet: Pet, now: datetime, ctx: Context, events: list[Event]) -> Pet:
    night = is_night(now, ctx)
    if pet.is_asleep:
        if night or pet.stats.energy < STAT_MAX:
            return pet
        events.append(WokeUp(pet.age))
        return replace(pet, is_asleep=False)
    if not night and pet.stats.energy >= ctx.balance.sleepy_energy:
        return pet
    events.append(FellAsleep(pet.age))
    return replace(pet, is_asleep=True)


def _drift_rates(pet: Pet, b: Balance) -> dict[Stat, Fraction]:
    if pet.is_asleep:
        hunger = -_per_step(b, b.hunger_asleep)
        happiness = -_per_step(b, b.happiness_asleep)
        energy = _per_step(b, b.energy_asleep_regen)
        hygiene = -_per_step(b, b.hygiene_asleep)
    else:
        multiplier = b.decay_multiplier(pet.stage)
        hunger = -_per_step(b, b.hunger_awake) * multiplier
        happiness = -_per_step(b, b.happiness_awake) * multiplier
        energy = -_per_step(b, b.energy_awake) * multiplier
        hygiene = -_per_step(b, b.hygiene_awake) * multiplier
    if pet.is_sick:
        happiness *= b.sick_happiness_multiplier
    hygiene -= _per_step(b, b.hygiene_per_poop) * pet.poop_count
    return {
        Stat.HUNGER: hunger,
        Stat.HAPPINESS: happiness,
        Stat.ENERGY: energy,
        Stat.HYGIENE: hygiene,
        Stat.HEALTH: _health_rate(pet, b),
    }


def _health_rate(pet: Pet, b: Balance) -> Fraction:
    neglected = any(pet.stats[need] == 0 for need in NEEDS)
    if not pet.is_sick and not neglected:
        return _per_step(b, b.health_regen)
    rate = Fraction(0)
    if pet.is_sick:
        rate -= _per_step(b, b.sick_health)
    if neglected:
        rate -= _per_step(b, b.neglect_health)
    return rate


def _apply_drift(pet: Pet, b: Balance, events: list[Event]) -> Pet:
    stats, drift = pet.stats, pet.drift
    for stat, rate in _drift_rates(pet, b).items():
        pending = drift[stat] + rate
        whole = math.trunc(pending)
        before = stats[stat]
        stats = stats.adjust(stat, whole)
        drift = drift.with_value(stat, pending - whole)
        if stat in NEEDS and stats[stat] < b.attention_threshold <= before:
            events.append(NeedLow(pet.age, stat))
    return replace(pet, stats=stats, drift=drift)


def _update_poop(pet: Pet, b: Balance, events: list[Event]) -> Pet:
    if pet.is_asleep:
        return pet
    progress = pet.poop_progress + _per_step(b, b.poop_interval) * b.decay_multiplier(pet.stage)
    if progress < 1:
        return replace(pet, poop_progress=progress)
    progress -= 1
    if pet.poop_count >= b.max_poops:
        return replace(pet, poop_progress=progress)
    count = pet.poop_count + 1
    events.append(Pooped(pet.age, count))
    return replace(pet, poop_progress=progress, poop_count=count)


def _hourly_rolls(pet: Pet, ctx: Context, events: list[Event]) -> Pet:
    b = ctx.balance
    # Always draw both numbers so RNG consumption doesn't depend on the pet's state.
    sick_roll, misbehave_roll = ctx.rng.random(), ctx.rng.random()
    if not pet.is_sick and sick_roll < sickness_chance(pet, b):
        doses = ctx.rng.randint(b.sickness_min_doses, b.sickness_max_doses)
        events.append(GotSick(pet.age, doses))
        pet = replace(pet, sickness_doses=doses)
    can_misbehave = (
        not pet.misbehaving
        and not pet.is_asleep
        and not pet.is_sick
        and pet.stage.order >= b.misbehave_min_stage.order
    )
    if can_misbehave and misbehave_roll < b.misbehave_chance:
        events.append(Misbehaved(pet.age))
        pet = replace(pet, misbehaving=True)
    return pet


def _update_timers(pet: Pet, b: Balance, events: list[Event]) -> Pet:
    timers, mistakes = pet.timers, pet.care_mistakes
    for need in NEEDS:
        before = timers.neglect(need)
        after = before + b.step if pet.stats[need] == 0 else ZERO
        if before <= b.neglect_grace < after:
            mistakes += 1
            events.append(CareMistake(pet.age, MistakeReason(need.value)))
        timers = timers.with_neglect(need, after)

    before = timers.lights_on_asleep
    after = before + b.step if pet.is_asleep and pet.lights_on else ZERO
    if before <= b.lights_on_asleep_grace < after:
        mistakes += 1
        events.append(CareMistake(pet.age, MistakeReason.LIGHTS))
    timers = replace(timers, lights_on_asleep=after)

    stats, misbehaving = pet.stats, pet.misbehaving
    ignored_for = timers.misbehaving + b.step if misbehaving else ZERO
    if ignored_for > b.misbehave_ignore_grace:
        events.append(MisbehaviourIgnored(pet.age))
        stats = stats.adjust(Stat.DISCIPLINE, b.misbehave_ignored_discipline)
        misbehaving, ignored_for = False, ZERO
    timers = replace(timers, misbehaving=ignored_for)

    return replace(pet, timers=timers, care_mistakes=mistakes, stats=stats, misbehaving=misbehaving)
