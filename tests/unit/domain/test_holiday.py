from dataclasses import replace
from datetime import timedelta
from typing import Any

import pytest
from hypothesis import given, settings

from tama.domain.actions import apply, apply_game_outcome, refusal
from tama.domain.animation import AnimationKey, looping_animation
from tama.domain.attention import attention_reasons
from tama.domain.balance import DEFAULT_BALANCE
from tama.domain.events import (
    Action,
    PausedForHoliday,
    PauseRefused,
    RefusalReason,
    ResumedFromHoliday,
)
from tama.domain.holiday import PauseBlocker, pause, pause_blockers, resume
from tama.domain.minigames import GameResult
from tama.domain.pet import Pet
from tama.domain.simulation import advance
from tama.domain.stage import DeathCause, LifeStage
from tama.domain.stats import Stats
from tama.errors import InvalidArgumentError
from tests.factories import FIXED_NOW, make_ctx, make_pet
from tests.strategies import durations, pets

WEEK = timedelta(days=7)


def settled(**overrides: Any) -> Pet:
    return make_pet(**overrides)


def on_holiday(**overrides: Any) -> Pet:
    return replace(settled(**overrides), paused_since=FIXED_NOW)


# --- Pausing ------------------------------------------------------------------------------


def test_a_settled_pet_can_go_on_holiday() -> None:
    pet = settled()

    out = pause(pet, DEFAULT_BALANCE)

    assert out.pet == replace(pet, paused_since=pet.updated_at)
    assert out.pet.on_holiday
    assert out.events == (PausedForHoliday(pet.age),)


@pytest.mark.parametrize(
    ("overrides", "blockers"),
    [
        ({"stats": Stats(hunger=10)}, {PauseBlocker.HUNGRY}),
        ({"stats": Stats(happiness=10, hygiene=10)}, {PauseBlocker.UNHAPPY, PauseBlocker.DIRTY}),
        ({"sickness_doses": 1}, {PauseBlocker.SICK}),
        ({"poop_count": 1}, {PauseBlocker.POOP}),
        ({"misbehaving": True}, {PauseBlocker.MISBEHAVING}),
        ({"is_asleep": True, "lights_on": True}, {PauseBlocker.LIGHTS}),
        ({"stage": LifeStage.EGG}, {PauseBlocker.EGG}),
        (
            {"stage": LifeStage.DEAD, "cause_of_death": DeathCause.OLD_AGE},
            {PauseBlocker.DEAD},
        ),
    ],
)
def test_an_unsettled_pet_cannot_go_on_holiday(
    overrides: dict[str, Any], blockers: set[PauseBlocker]
) -> None:
    pet = settled(**overrides)

    out = pause(pet, DEFAULT_BALANCE)

    assert set(pause_blockers(pet, DEFAULT_BALANCE)) == blockers
    assert out.pet == pet
    assert out.events == (PauseRefused(pet.age, tuple(sorted(blockers))),)


def test_a_sleeping_pet_with_the_lights_off_can_go_on_holiday() -> None:
    pet = settled(is_asleep=True, lights_on=False)

    assert pause(pet, DEFAULT_BALANCE).pet.on_holiday


def test_a_pet_already_on_holiday_cannot_be_paused_again() -> None:
    pet = on_holiday()

    assert pause_blockers(pet, DEFAULT_BALANCE) == (PauseBlocker.ON_HOLIDAY,)
    assert pause(pet, DEFAULT_BALANCE).pet == pet


# --- Resuming -----------------------------------------------------------------------------


def test_resuming_continues_from_now_and_reports_the_length() -> None:
    pet = on_holiday()
    later = FIXED_NOW + timedelta(days=3, hours=2)

    out = resume(pet, later)

    assert out.pet == replace(pet, paused_since=None, updated_at=later)
    assert out.events == (ResumedFromHoliday(pet.age, timedelta(days=3, hours=2)),)


def test_resuming_a_pet_that_is_not_on_holiday_does_nothing() -> None:
    pet = settled()

    assert resume(pet, FIXED_NOW).pet == pet
    assert resume(pet, FIXED_NOW).events == ()


def test_holiday_start_must_be_timezone_aware() -> None:
    with pytest.raises(InvalidArgumentError, match="timezone"):
        replace(settled(), paused_since=FIXED_NOW.replace(tzinfo=None))


# --- Frozen in time -----------------------------------------------------------------------


def test_a_week_on_holiday_changes_nothing_but_the_clock() -> None:
    pet = on_holiday(stats=Stats(hunger=30, happiness=30, energy=30, hygiene=30))
    rng_before = make_ctx(1).rng.getstate()
    ctx = make_ctx(1)

    out = advance(pet, WEEK, ctx)

    assert out.events == ()
    assert out.pet == replace(pet, updated_at=pet.updated_at + WEEK)
    assert ctx.rng.getstate() == rng_before


def test_pause_wait_resume_equals_not_waiting() -> None:
    pet = settled()
    paused = pause(pet, DEFAULT_BALANCE).pet
    back = resume(advance(paused, WEEK, make_ctx()).pet, pet.updated_at + WEEK).pet

    later = advance(back, timedelta(hours=5), make_ctx(3)).pet
    without_holiday = advance(pet, timedelta(hours=5), make_ctx(3)).pet

    assert later == replace(without_holiday, updated_at=without_holiday.updated_at + WEEK)


@settings(deadline=None)
@given(pets(), durations(timedelta(days=30)))
def test_any_paused_duration_only_moves_the_clock(pet: Pet, elapsed: timedelta) -> None:
    paused = replace(pet, paused_since=pet.updated_at)

    out = advance(paused, elapsed, make_ctx())

    assert out.events == ()
    assert out.pet == replace(paused, updated_at=paused.updated_at + elapsed)


# --- Everything else stops ----------------------------------------------------------------


@pytest.mark.parametrize("action", list(Action))
def test_care_actions_are_refused_on_holiday(action: Action) -> None:
    pet = on_holiday()

    assert refusal(pet, action, DEFAULT_BALANCE) is RefusalReason.ON_HOLIDAY
    assert apply(pet, action, make_ctx()).pet == pet


def test_game_results_are_refused_on_holiday() -> None:
    pet = on_holiday()

    assert apply_game_outcome(pet, GameResult.WIN, ctx=make_ctx()).refusal is (
        RefusalReason.ON_HOLIDAY
    )


def test_a_pet_on_holiday_never_calls_for_attention() -> None:
    pet = on_holiday(stats=Stats(hunger=0), poop_count=2, sickness_doses=1)

    assert attention_reasons(pet, DEFAULT_BALANCE) == frozenset()


def test_a_pet_on_holiday_is_shown_asleep() -> None:
    assert looping_animation(on_holiday()) is AnimationKey.SLEEP


@pytest.mark.parametrize("weight", [1, 200], ids=["underweight", "overweight"])
def test_a_weight_call_does_not_stop_a_holiday(weight: int) -> None:
    pet = make_pet(weight=weight)
    assert attention_reasons(pet, DEFAULT_BALANCE)  # it is calling about its weight

    assert pause_blockers(pet, DEFAULT_BALANCE) == ()
