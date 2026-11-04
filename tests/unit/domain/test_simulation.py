from dataclasses import replace
from datetime import UTC, datetime, time, timedelta, timezone, tzinfo
from fractions import Fraction
from typing import Any

import pytest

from tama.domain.balance import DEFAULT_BALANCE, Balance
from tama.domain.events import (
    CareMistake,
    Died,
    Evolved,
    FellAsleep,
    GotSick,
    LaidEgg,
    Misbehaved,
    MisbehaviourIgnored,
    MistakeReason,
    NeedLow,
    Outcome,
    Pooped,
    WeightLeftBand,
    WokeUp,
)
from tama.domain.pet import Pet, Timers
from tama.domain.simulation import advance, is_night, sickness_chance, skip_to
from tama.domain.stage import DeathCause, LifeStage, Variant
from tama.domain.stats import Stat, Stats
from tama.domain.weight import WeightStatus
from tama.errors import InvalidArgumentError
from tests.factories import FIXED_NOW, make_ctx, make_pet

NIGHT = datetime(2026, 1, 1, 23, 0, tzinfo=UTC)
MIN = timedelta(minutes=1)
HOUR = timedelta(hours=1)

NO_RANDOM_EVENTS = Balance(sickness_base_chance=0, misbehave_chance=0)
"""Balance for tests that must not be disturbed by hourly sickness/misbehaviour rolls."""


def run(
    pet: Pet,
    elapsed: timedelta,
    *,
    balance: Balance = NO_RANDOM_EVENTS,
    seed: int = 0,
    tz: tzinfo = UTC,
) -> Outcome:
    return advance(pet, elapsed, make_ctx(seed, balance=balance, tz=tz))


# --- Time bookkeeping ---------------------------------------------------------------------


def test_negative_elapsed_is_rejected() -> None:
    with pytest.raises(InvalidArgumentError, match="elapsed"):
        run(make_pet(), timedelta(seconds=-1))


def test_less_than_a_step_only_accumulates_carry() -> None:
    pet = make_pet()

    out = run(pet, timedelta(seconds=30))

    assert out.events == ()
    assert out.pet == replace(
        pet, carry=timedelta(seconds=30), updated_at=FIXED_NOW + timedelta(seconds=30)
    )


def test_carry_completes_a_step_across_calls() -> None:
    pet = make_pet()
    half = timedelta(seconds=30)

    out = run(run(pet, half).pet, half)

    assert out.pet.age == pet.age + MIN
    assert out.pet.carry == timedelta(0)
    assert out.pet.updated_at == FIXED_NOW + MIN


def test_zero_elapsed_is_a_no_op() -> None:
    pet = make_pet()

    assert run(pet, timedelta(0)).pet == pet


# --- Egg ----------------------------------------------------------------------------------


def test_egg_does_not_drift_before_hatching() -> None:
    egg = make_pet(stage=LifeStage.EGG, stats=Stats(hunger=50))
    balance = replace(NO_RANDOM_EVENTS, hatch_age=timedelta(minutes=10))

    out = run(egg, timedelta(minutes=9), balance=balance)

    assert out.pet.stats == egg.stats
    assert out.pet.stage is LifeStage.EGG
    assert out.pet.age == timedelta(minutes=9)


def test_egg_hatches_after_one_minute() -> None:
    egg = make_pet(stage=LifeStage.EGG)

    out = run(egg, MIN)

    assert out.pet.stage is LifeStage.BABY
    assert out.events == (Evolved(MIN, LifeStage.EGG, LifeStage.BABY, Variant.DEFAULT),)


# --- Drift --------------------------------------------------------------------------------


def test_hunger_drops_one_per_five_minutes_when_awake() -> None:
    out = run(make_pet(), timedelta(minutes=15))

    assert out.pet.stats.hunger == 97


def test_drift_remainder_is_kept_between_steps() -> None:
    out = run(make_pet(), timedelta(minutes=7))

    assert out.pet.stats.hunger == 99
    assert out.pet.drift[Stat.HUNGER] == pytest.approx(-2 / 5)


def test_hunger_drops_slower_when_asleep() -> None:
    pet = make_pet(is_asleep=True, lights_on=False, updated_at=NIGHT)

    out = run(pet, timedelta(minutes=30))

    assert out.pet.stats.hunger == 97


def test_babies_decay_one_and_a_half_times_faster() -> None:
    pet = make_pet(stage=LifeStage.BABY)

    assert run(pet, timedelta(minutes=10)).pet.stats.hunger == 97


def test_elders_decay_slower() -> None:
    pet = make_pet(stage=LifeStage.ELDER)

    assert run(pet, timedelta(minutes=20)).pet.stats.hunger == 97


def test_happiness_decays_one_and_a_half_times_as_fast_when_sick() -> None:
    pet = make_pet(sickness_doses=1)

    assert run(pet, timedelta(minutes=12)).pet.stats.happiness == 97


def test_energy_decays_awake_and_recovers_asleep() -> None:
    awake = make_pet(stats=Stats(energy=50))
    asleep = make_pet(stats=Stats(energy=50), is_asleep=True, lights_on=False, updated_at=NIGHT)

    assert run(awake, timedelta(minutes=10)).pet.stats.energy == 48
    assert run(asleep, timedelta(minutes=10)).pet.stats.energy == 60


def test_uncleaned_poop_makes_pet_dirty_faster() -> None:
    pet = make_pet(poop_count=2)

    out = run(pet, HOUR)

    assert out.pet.stats.hygiene == 100 - 10 - 2 * 15


def test_hygiene_drops_slower_when_asleep() -> None:
    pet = make_pet(is_asleep=True, lights_on=False, updated_at=NIGHT)

    assert run(pet, timedelta(minutes=30)).pet.stats.hygiene == 98


def test_need_low_event_when_crossing_attention_threshold() -> None:
    pet = make_pet(stats=Stats(hunger=25))

    out = run(pet, timedelta(minutes=5))

    assert out.pet.stats.hunger == 24
    assert NeedLow(pet.age + 5 * MIN, Stat.HUNGER) in out.events


# --- Health & death -----------------------------------------------------------------------


def test_sickness_damages_health() -> None:
    pet = make_pet(sickness_doses=1)

    assert run(pet, timedelta(minutes=50)).pet.stats.health == 95


def test_a_need_at_zero_damages_health() -> None:
    pet = make_pet(stats=Stats(hunger=0))

    assert run(pet, timedelta(minutes=40)).pet.stats.health == 95


def test_health_regenerates_when_well_cared_for() -> None:
    pet = make_pet(stats=Stats(health=50))

    assert run(pet, timedelta(minutes=20)).pet.stats.health == 52


def test_pet_dies_when_health_reaches_zero() -> None:
    pet = make_pet(stats=Stats(hunger=0, health=3))

    out = run(pet, timedelta(minutes=30))

    assert out.pet.stage is LifeStage.DEAD
    assert out.pet.cause_of_death is DeathCause.POOR_HEALTH
    assert out.pet.age == pet.age + 24 * MIN
    assert out.events[-1] == Died(pet.age + 24 * MIN, DeathCause.POOR_HEALTH)


def test_dead_pets_do_not_change() -> None:
    pet = make_pet(stage=LifeStage.DEAD, cause_of_death=DeathCause.OLD_AGE)

    out = run(pet, timedelta(days=2))

    assert out.events == ()
    assert replace(out.pet, updated_at=pet.updated_at) == pet


def test_dying_wakes_the_pet() -> None:
    pet = make_pet(stats=Stats(hunger=0, health=1), is_asleep=True, updated_at=NIGHT)

    out = run(pet, timedelta(minutes=8))

    assert out.pet.stage is LifeStage.DEAD
    assert not out.pet.is_asleep


def test_dying_ends_a_woken_tantrum() -> None:
    pet = make_pet(
        stats=Stats(hunger=0, health=1), misbehaving=True, woken_tantrum=True, stay_awake=HOUR
    )

    out = run(pet, timedelta(minutes=8))

    assert out.pet.stage is LifeStage.DEAD
    assert not out.pet.misbehaving
    assert not out.pet.woken_tantrum
    assert out.pet.stay_awake == timedelta(0)


# --- Care mistakes ------------------------------------------------------------------------


@pytest.mark.parametrize(("minutes", "mistakes"), [(15, 0), (16, 1), (60, 1)])
def test_need_at_zero_too_long_is_one_care_mistake_per_episode(minutes: int, mistakes: int) -> None:
    pet = make_pet(stats=Stats(hunger=0))

    out = run(pet, timedelta(minutes=minutes))

    assert out.pet.care_mistakes == mistakes
    assert out.events.count(CareMistake(pet.age + 16 * MIN, MistakeReason.HUNGER)) == mistakes


def test_neglect_timer_resets_when_need_recovers() -> None:
    pet = make_pet(stats=Stats(hygiene=50), timers=Timers(hygiene=timedelta(minutes=10)))

    assert run(pet, MIN).pet.timers.hygiene == timedelta(0)


def test_lights_left_on_while_asleep_is_a_care_mistake() -> None:
    pet = make_pet(is_asleep=True, lights_on=True, updated_at=NIGHT)

    out = run(pet, timedelta(minutes=31))

    assert out.pet.care_mistakes == 1
    assert CareMistake(pet.age + 31 * MIN, MistakeReason.LIGHTS) in out.events


def test_lights_off_while_asleep_is_fine() -> None:
    pet = make_pet(is_asleep=True, lights_on=False, updated_at=NIGHT)

    assert run(pet, HOUR).pet.care_mistakes == 0


# --- Sleep --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("hour", "night"),
    [(21, False), (22, True), (3, True), (6, True), (7, False), (12, False)],
)
def test_is_night_with_window_wrapping_midnight(hour: int, night: bool) -> None:
    when = datetime(2026, 1, 1, hour, tzinfo=UTC)

    assert is_night(when, make_ctx()) is night


@pytest.mark.parametrize(("hour", "night"), [(0, False), (1, True), (4, True), (5, False)])
def test_is_night_with_window_within_a_day(hour: int, night: bool) -> None:
    ctx = make_ctx(balance=Balance(night_start=time(1), night_end=time(5)))

    assert is_night(datetime(2026, 1, 1, hour, tzinfo=UTC), ctx) is night


def test_is_night_uses_local_time_zone() -> None:
    plus_two = timezone(timedelta(hours=2))
    utc_evening = datetime(2026, 1, 1, 20, 30, tzinfo=UTC)  # 22:30 at UTC+2

    assert is_night(utc_evening, make_ctx(tz=plus_two))
    assert not is_night(utc_evening, make_ctx(tz=UTC))


def test_pet_falls_asleep_at_night() -> None:
    pet = make_pet(updated_at=datetime(2026, 1, 1, 21, 59, tzinfo=UTC))

    out = run(pet, MIN)

    assert out.pet.is_asleep
    assert out.events == (FellAsleep(pet.age + MIN),)


def test_tired_pet_falls_asleep_during_the_day() -> None:
    pet = make_pet(stats=Stats(energy=19))

    out = run(pet, MIN)

    assert out.pet.is_asleep
    assert FellAsleep(pet.age + MIN) in out.events


def test_rested_pet_wakes_during_the_day() -> None:
    pet = make_pet(stats=Stats(energy=99), is_asleep=True, lights_on=False)

    out = run(pet, 2 * MIN)

    assert not out.pet.is_asleep
    assert out.events == (WokeUp(pet.age + 2 * MIN),)


def test_rested_pet_keeps_sleeping_at_night() -> None:
    pet = make_pet(is_asleep=True, lights_on=False, updated_at=NIGHT)

    assert run(pet, HOUR).pet.is_asleep


def test_a_woken_pet_stays_up_for_half_an_hour_at_night() -> None:
    pet = make_pet(updated_at=NIGHT, stay_awake=30 * MIN)

    out = run(pet, 30 * MIN)

    assert not out.pet.is_asleep
    assert out.pet.stay_awake == timedelta(0)
    assert out.events == ()


def test_a_woken_pet_falls_back_asleep_at_night_after_half_an_hour() -> None:
    pet = make_pet(updated_at=NIGHT, stay_awake=30 * MIN)

    out = run(pet, 31 * MIN)

    assert out.pet.is_asleep
    assert out.events == (FellAsleep(pet.age + 31 * MIN),)


def test_a_woken_pet_stays_up_however_tired_it_is() -> None:
    pet = make_pet(stats=Stats(energy=0), stay_awake=30 * MIN)

    assert not run(pet, 30 * MIN).pet.is_asleep


def test_a_rested_woken_pet_stays_up_by_day_once_the_half_hour_is_over() -> None:
    pet = make_pet(stats=Stats(energy=80), stay_awake=30 * MIN)

    out = run(pet, HOUR)

    assert not out.pet.is_asleep
    assert out.pet.stay_awake == timedelta(0)


def test_stay_awake_never_goes_negative() -> None:
    pet = make_pet(updated_at=NIGHT, stay_awake=timedelta(seconds=30))

    out = run(pet, MIN)

    assert out.pet.stay_awake == timedelta(0)
    assert not out.pet.is_asleep


# --- Poop ---------------------------------------------------------------------------------


def test_pet_poops_every_two_hours_awake() -> None:
    pet = make_pet()

    out = run(pet, 2 * HOUR)

    assert out.pet.poop_count == 1
    assert Pooped(pet.age + 2 * HOUR, 1) in out.events


def test_pet_does_not_poop_asleep() -> None:
    pet = make_pet(is_asleep=True, lights_on=False, updated_at=NIGHT)

    assert run(pet, 3 * HOUR).pet.poop_count == 0


def test_poop_is_capped() -> None:
    pet = make_pet(poop_count=DEFAULT_BALANCE.max_poops)

    out = run(pet, 2 * HOUR)

    assert out.pet.poop_count == DEFAULT_BALANCE.max_poops
    assert not any(isinstance(e, Pooped) for e in out.events)


# --- Hourly rolls -------------------------------------------------------------------------


def test_sickness_chance_formula() -> None:
    b = DEFAULT_BALANCE
    healthy = make_pet()
    worst = make_pet(stats=Stats(hunger=10, hygiene=10), poop_count=2)

    assert sickness_chance(healthy, b) == pytest.approx(0.01)
    assert sickness_chance(worst, b) == pytest.approx(0.01 + 2 * 0.05 + 0.10 + 0.10)


def test_sickness_is_rolled_on_the_hour() -> None:
    pet = make_pet()
    certain = Balance(sickness_base_chance=1, misbehave_chance=0)

    before_hour = run(pet, HOUR - MIN, balance=certain)
    on_hour = run(pet, HOUR, balance=certain)

    assert not before_hour.pet.is_sick
    assert on_hour.pet.is_sick
    assert 1 <= on_hour.pet.sickness_doses <= 2
    assert GotSick(pet.age + HOUR, on_hour.pet.sickness_doses) in on_hour.events


def test_sick_pet_is_not_rerolled() -> None:
    pet = make_pet(sickness_doses=2)
    certain = Balance(sickness_base_chance=1, misbehave_chance=0)

    out = run(pet, HOUR, balance=certain)

    assert out.pet.sickness_doses == 2
    assert not any(isinstance(e, GotSick) for e in out.events)


def test_pet_misbehaves_on_the_hour() -> None:
    pet = make_pet()
    certain = Balance(sickness_base_chance=0, misbehave_chance=1)

    out = run(pet, HOUR, balance=certain)

    assert out.pet.misbehaving
    assert Misbehaved(pet.age + HOUR) in out.events


@pytest.mark.parametrize(
    "overrides",
    [
        {"is_asleep": True, "lights_on": False, "updated_at": NIGHT},
        {"sickness_doses": 1},
    ],
)
def test_pet_does_not_start_misbehaving_when_ineligible(overrides: dict[str, Any]) -> None:
    pet = make_pet(**overrides)
    certain = Balance(sickness_base_chance=0, misbehave_chance=1)

    out = run(pet, HOUR - pet.age % HOUR, balance=certain)

    assert not any(isinstance(e, Misbehaved) for e in out.events)


def test_already_misbehaving_pet_is_not_rerolled() -> None:
    pet = make_pet(misbehaving=True, age=2 * HOUR - MIN)
    certain = Balance(sickness_base_chance=0, misbehave_chance=1)

    out = run(pet, MIN, balance=certain)

    assert out.pet.misbehaving
    assert out.events == ()


def test_young_pets_do_not_misbehave() -> None:
    pet = make_pet(stage=LifeStage.CHILD)
    certain = Balance(
        sickness_base_chance=0, misbehave_chance=1, misbehave_min_stage=LifeStage.TEEN
    )

    out = run(pet, HOUR, balance=certain)

    assert not out.pet.misbehaving


def test_misbehaviour_waits_half_an_hour_to_be_disciplined() -> None:
    pet = make_pet(stats=Stats(discipline=50), misbehaving=True)

    out = run(pet, 30 * MIN)

    assert out.pet.misbehaving
    assert out.pet.stats.discipline == 50


def test_ignored_misbehaviour_lowers_discipline() -> None:
    pet = make_pet(stats=Stats(discipline=50), misbehaving=True)

    out = run(pet, 31 * MIN)

    assert not out.pet.misbehaving
    assert out.pet.stats.discipline == 40
    assert out.pet.timers.misbehaving == timedelta(0)
    assert MisbehaviourIgnored(pet.age + 31 * MIN) in out.events


def test_an_ignored_woken_tantrum_lowers_discipline_and_ends() -> None:
    pet = make_pet(stats=Stats(discipline=50), misbehaving=True, woken_tantrum=True)

    out = run(pet, 31 * MIN)

    assert not out.pet.misbehaving
    assert not out.pet.woken_tantrum
    assert out.pet.stats.discipline == 40


def test_a_woken_tantrum_stays_woken_until_it_ends() -> None:
    pet = make_pet(misbehaving=True, woken_tantrum=True)

    assert run(pet, 10 * MIN).pet.woken_tantrum


def test_hourly_rolls_use_the_rng_deterministically() -> None:
    pet = make_pet()

    a = run(pet, 12 * HOUR, balance=DEFAULT_BALANCE, seed=42)
    b = run(pet, 12 * HOUR, balance=DEFAULT_BALANCE, seed=42)

    assert a == b


# --- Life stages --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("stage", "next_stage"),
    [
        (LifeStage.BABY, LifeStage.CHILD),
        (LifeStage.CHILD, LifeStage.TEEN),
        (LifeStage.ADULT, LifeStage.ELDER),
    ],
)
def test_pet_evolves_at_stage_age(stage: LifeStage, next_stage: LifeStage) -> None:
    pet = make_pet(stage=stage, age=DEFAULT_BALANCE.stage_age(next_stage) - MIN)

    out = run(pet, MIN)

    assert out.pet.stage is next_stage
    assert Evolved(out.pet.age, stage, next_stage, pet.variant) in out.events


@pytest.mark.parametrize(
    ("discipline", "mistakes", "variant"),
    [
        (60, 0, Variant.GOOD),
        (50, 3, Variant.GOOD),
        (60, 4, Variant.SCRUFFY),
        (49, 0, Variant.SCRUFFY),
    ],
)
def test_adult_variant_depends_on_care(discipline: int, mistakes: int, variant: Variant) -> None:
    pet = make_pet(
        stage=LifeStage.TEEN,
        age=DEFAULT_BALANCE.adult_age - MIN,
        stats=Stats(discipline=discipline),
        care_mistakes=mistakes,
    )

    out = run(pet, MIN)

    assert out.pet.stage is LifeStage.ADULT
    assert out.pet.variant is variant


@pytest.mark.parametrize(
    ("over_by", "variant"), [(0, Variant.GOOD), (1, Variant.CHUBBY)], ids=["at-limit", "over"]
)
def test_an_overweight_teen_grows_into_a_chubby_adult(over_by: int, variant: Variant) -> None:
    heaviest = DEFAULT_BALANCE.weight_band(LifeStage.ADULT)[1]
    pet = make_pet(
        stage=LifeStage.TEEN,
        age=DEFAULT_BALANCE.adult_age - MIN,
        stats=Stats(discipline=100),
        weight=heaviest + over_by,
    )

    out = run(pet, MIN, balance=replace(NO_RANDOM_EVENTS, weight_burn=Fraction(0)))

    assert out.pet.variant is variant


def test_a_chubby_adult_stays_chubby_as_an_elder() -> None:
    pet = make_pet(
        stage=LifeStage.ADULT, variant=Variant.CHUBBY, age=DEFAULT_BALANCE.elder_age - MIN
    )

    out = run(pet, MIN)

    assert (out.pet.stage, out.pet.variant) == (LifeStage.ELDER, Variant.CHUBBY)


def test_elder_dies_of_old_age_at_lifespan() -> None:
    pet = make_pet(stage=LifeStage.ELDER, lifespan=timedelta(days=15), age=timedelta(days=15) - MIN)

    out = run(pet, HOUR)

    assert out.pet.stage is LifeStage.DEAD
    assert out.pet.cause_of_death is DeathCause.OLD_AGE
    assert out.pet.age == timedelta(days=15)
    assert out.events[-2:] == (
        Died(timedelta(days=15), DeathCause.OLD_AGE),
        LaidEgg(timedelta(days=15)),
    )
    assert out.pet.egg_waiting


def test_a_pet_that_dies_of_poor_health_leaves_no_egg() -> None:
    out = run(make_pet(stats=Stats(hunger=0, health=1)), HOUR)

    assert out.pet.cause_of_death is DeathCause.POOR_HEALTH
    assert not any(isinstance(e, LaidEgg) for e in out.events)
    assert not out.pet.egg_waiting


# --- Skipping time ------------------------------------------------------------------------


@pytest.mark.parametrize("delta", [timedelta(hours=5), timedelta(hours=-3)])
def test_skip_to_moves_the_clock_without_simulating(delta: timedelta) -> None:
    pet = make_pet(carry=timedelta(seconds=20))

    skipped = skip_to(pet, pet.updated_at + delta)

    assert skipped == replace(pet, updated_at=pet.updated_at + delta)


def test_skip_to_requires_aware_time() -> None:
    with pytest.raises(InvalidArgumentError, match="timezone-aware"):
        skip_to(make_pet(), FIXED_NOW.replace(tzinfo=None))


# --- Weight (SPEC §2.7) ---------------------------------------------------------------------

WIDE = Balance(
    sickness_base_chance=0,
    misbehave_chance=0,
    weight_burn=Fraction(1, 64),
    baby_weight=(1, 200),
    child_weight=(1, 200),
)
"""Every weight is healthy, so only the burn itself is under test."""


def test_an_awake_pet_burns_its_share_of_weight_each_hour() -> None:
    pet = make_pet(weight=64)  # 64 g x 1/64 per hour = 1 g per hour

    assert run(pet, 59 * MIN, balance=WIDE).pet.weight == 64
    assert run(pet, HOUR, balance=WIDE).pet.weight == 63


def test_burning_keeps_the_fraction_of_a_gram_already_burned() -> None:
    pet = make_pet(weight=64, weight_progress=Fraction(1, 2))

    out = run(pet, 30 * MIN, balance=WIDE)

    assert out.pet.weight == 63
    assert out.pet.weight_progress == 0


def test_a_sleeping_pet_burns_nothing() -> None:
    pet = make_pet(weight=64, is_asleep=True, lights_on=False, updated_at=NIGHT)

    out = run(pet, HOUR, balance=WIDE)

    assert out.pet.weight == 64
    assert out.pet.weight_progress == 0


def test_babies_burn_faster() -> None:
    pet = make_pet(stage=LifeStage.BABY, weight=64)

    assert run(pet, 40 * MIN, balance=WIDE).pet.weight == 63  # x1.5


def test_burning_never_goes_below_the_minimum_weight() -> None:
    balance = replace(WIDE, weight_burn=Fraction(60))  # a whole gram every step
    pet = make_pet(weight=3)

    assert run(pet, 10 * MIN, balance=balance).pet.weight == DEFAULT_BALANCE.min_weight


def test_overweight_pets_tire_faster() -> None:
    balance = Balance(sickness_base_chance=0, misbehave_chance=0, child_weight=(4, 14))
    healthy, heavy = make_pet(weight=10), make_pet(weight=100)

    assert run(healthy, 20 * MIN, balance=balance).pet.stats.energy == 100 - 4
    assert run(heavy, 20 * MIN, balance=balance).pet.stats.energy == 100 - 5  # x1.25


def test_underweight_pets_do_not_regenerate_health() -> None:
    balance = Balance(sickness_base_chance=0, misbehave_chance=0, child_weight=(8, 14))
    stats = Stats(health=50)

    assert run(make_pet(weight=10, stats=stats), 10 * MIN, balance=balance).pet.stats.health == 51
    assert run(make_pet(weight=5, stats=stats), 10 * MIN, balance=balance).pet.stats.health == 50


def test_overweight_pets_fall_sick_more_often() -> None:
    b = Balance(child_weight=(4, 14))

    healthy = sickness_chance(make_pet(weight=14), b)

    assert sickness_chance(make_pet(weight=15), b) == pytest.approx(healthy + 0.05)


EPISODE = Balance(
    sickness_base_chance=0,
    misbehave_chance=0,
    weight_burn=Fraction(0),
    child_weight=(4, 14),
    weight_episode_grace=30 * MIN,
)


def weight_mistakes(out: Outcome) -> list[CareMistake]:
    return [e for e in out.events if e == CareMistake(e.age, MistakeReason.WEIGHT)]


@pytest.mark.parametrize("weight", [2, 30], ids=["underweight", "overweight"])
def test_leaving_the_band_is_announced_once(weight: int) -> None:
    out = run(make_pet(weight=weight), 10 * MIN, balance=EPISODE)

    status = WeightStatus.UNDER if weight == 2 else WeightStatus.OVER
    assert [e for e in out.events if isinstance(e, WeightLeftBand)] == [
        WeightLeftBand(make_pet().age + MIN, status)
    ]


@pytest.mark.parametrize("weight", [2, 30], ids=["underweight", "overweight"])
def test_too_long_outside_the_band_is_one_care_mistake(weight: int) -> None:
    pet = make_pet(weight=weight)

    assert weight_mistakes(run(pet, 30 * MIN, balance=EPISODE)) == []
    out = run(pet, 3 * HOUR, balance=EPISODE)
    assert weight_mistakes(out) == [CareMistake(pet.age + 31 * MIN, MistakeReason.WEIGHT)]
    assert out.pet.care_mistakes == 1
    assert out.pet.timers.weight == 3 * HOUR


def test_back_in_the_band_resets_the_episode() -> None:
    pet = make_pet(weight=30, timers=Timers(weight=20 * MIN))

    out = run(replace(pet, weight=10), MIN, balance=EPISODE)

    assert out.pet.timers.weight == timedelta(0)
    assert out.events == ()


def test_growing_into_a_heavier_band_can_leave_a_pet_underweight() -> None:
    balance = replace(EPISODE, teen_weight=(20, 30))
    pet = make_pet(weight=10, age=DEFAULT_BALANCE.teen_age - MIN)

    out = run(pet, MIN, balance=balance)

    assert WeightLeftBand(DEFAULT_BALANCE.teen_age, WeightStatus.UNDER) in out.events
