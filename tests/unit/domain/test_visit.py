from dataclasses import replace
from datetime import timedelta
from typing import Any

import pytest

from tama.domain.actions import apply_game_outcome
from tama.domain.balance import DEFAULT_BALANCE
from tama.domain.events import Played, PlayedWith, Refused, Visited
from tama.domain.minigames import GameKind, GameResult, Side
from tama.domain.stage import DeathCause, LifeStage
from tama.domain.stats import Stats
from tama.domain.visit import VisitRefusal, can_visit, start_visit, visit_refusals
from tama.errors import VisitRefusedError
from tests.factories import FIXED_NOW, make_ctx, make_pet

B = DEFAULT_BALANCE
FOUR = GameKind.FOUR_IN_A_ROW


# --- Who can visit ---------------------------------------------------------------------------


def test_an_awake_settled_pet_can_visit() -> None:
    pet = make_pet()

    assert visit_refusals(pet, B) == ()
    assert can_visit(pet, B)


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"stage": LifeStage.EGG}, VisitRefusal.EGG),
        ({"stage": LifeStage.DEAD, "cause_of_death": DeathCause.POOR_HEALTH}, VisitRefusal.DEAD),
        ({"paused_since": FIXED_NOW}, VisitRefusal.ON_HOLIDAY),
        ({"is_asleep": True}, VisitRefusal.ASLEEP),
        ({"sickness_doses": 1}, VisitRefusal.SICK),
        ({"misbehaving": True}, VisitRefusal.MISBEHAVING),
        ({"stats": Stats(energy=9)}, VisitRefusal.TOO_TIRED),
    ],
)
def test_a_pet_that_cant_visit_says_why(overrides: dict[str, Any], reason: VisitRefusal) -> None:
    pet = make_pet(**overrides)

    assert visit_refusals(pet, B) == (reason,)
    assert not can_visit(pet, B)


def test_every_reason_is_given_in_order() -> None:
    pet = make_pet(is_asleep=True, misbehaving=True, sickness_doses=2, stats=Stats(energy=0))

    assert visit_refusals(pet, B) == (
        VisitRefusal.ASLEEP,
        VisitRefusal.SICK,
        VisitRefusal.MISBEHAVING,
        VisitRefusal.TOO_TIRED,
    )


def test_an_egg_or_a_dead_pet_has_only_that_reason() -> None:
    egg = make_pet(stage=LifeStage.EGG, stats=Stats(energy=0))
    dead = make_pet(stage=LifeStage.DEAD, cause_of_death=DeathCause.OLD_AGE, is_asleep=True)
    away = make_pet(paused_since=FIXED_NOW, misbehaving=True)

    assert visit_refusals(egg, B) == (VisitRefusal.EGG,)
    assert visit_refusals(dead, B) == (VisitRefusal.DEAD,)
    assert visit_refusals(away, B) == (VisitRefusal.ON_HOLIDAY,)


def test_exactly_enough_energy_is_enough() -> None:
    assert can_visit(make_pet(stats=Stats(energy=B.play_min_energy)), B)


# --- Starting a visit ------------------------------------------------------------------------


def test_a_visit_cheers_the_pet_up_and_is_remembered() -> None:
    pet = make_pet(stats=Stats(happiness=50))

    outcome = start_visit(pet, "Pip", B)

    assert outcome.pet == replace(pet, stats=Stats(happiness=60), last_visit=pet.age)
    assert outcome.events == (Visited(pet.age, "Pip", cheered=True),)


def test_a_second_visit_within_the_cooldown_gives_no_happiness() -> None:
    pet = make_pet(stats=Stats(happiness=50))
    visited = start_visit(pet, "Pip", B).pet
    later = replace(visited, age=visited.age + B.visit_cooldown - B.step)

    outcome = start_visit(later, "Bo", B)

    assert outcome.pet.stats.happiness == 60
    assert outcome.pet.last_visit == later.age
    assert outcome.events == (Visited(later.age, "Bo", cheered=False),)


def test_after_the_cooldown_a_visit_cheers_again() -> None:
    pet = make_pet(stats=Stats(happiness=50))
    visited = start_visit(pet, "Pip", B).pet
    later = replace(visited, age=visited.age + B.visit_cooldown)

    assert start_visit(later, "Pip", B).pet.stats.happiness == 70


def test_happiness_is_capped() -> None:
    assert start_visit(make_pet(stats=Stats(happiness=95)), "Pip", B).pet.stats.happiness == 100


def test_a_pet_that_cant_visit_cant_start_one() -> None:
    pet = make_pet(is_asleep=True)

    with pytest.raises(VisitRefusedError, match="asleep"):
        start_visit(pet, "Pip", B)


# --- Games between pets ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("result", "side", "theirs"),
    [
        (GameResult.WIN, Side.PLAYER, GameResult.WIN),
        (GameResult.WIN, Side.PET, GameResult.LOSS),
        (GameResult.LOSS, Side.PET, GameResult.WIN),
        (GameResult.DRAW, Side.PET, GameResult.DRAW),
    ],
)
def test_each_pet_gets_the_result_from_its_own_side(
    result: GameResult, side: Side, theirs: GameResult
) -> None:
    pet = make_pet(stats=Stats(happiness=50, energy=50))

    outcome = apply_game_outcome(pet, result, game=FOUR, ctx=make_ctx(), side=side, friend="Pip")

    alone = apply_game_outcome(pet, theirs, game=FOUR, ctx=make_ctx())
    assert outcome.pet == alone.pet
    assert outcome.events == (PlayedWith(pet.age, "Pip", FOUR, theirs),)


def test_a_game_with_the_player_is_played_from_either_side_too() -> None:
    pet = make_pet()

    outcome = apply_game_outcome(pet, GameResult.WIN, game=FOUR, ctx=make_ctx(), side=Side.PET)

    assert outcome.events == (Played(pet.age, GameResult.LOSS, FOUR),)


def test_a_dead_guest_gets_no_result() -> None:
    pet = make_pet(stage=LifeStage.DEAD, cause_of_death=DeathCause.POOR_HEALTH)

    outcome = apply_game_outcome(
        pet, GameResult.LOSS, game=FOUR, ctx=make_ctx(), side=Side.PET, friend="Pip"
    )

    assert outcome.pet == pet
    assert isinstance(outcome.events[0], Refused)


@pytest.mark.parametrize(
    ("result", "mirrored"),
    [
        (GameResult.WIN, GameResult.LOSS),
        (GameResult.LOSS, GameResult.WIN),
        (GameResult.DRAW, GameResult.DRAW),
    ],
)
def test_results_mirror(result: GameResult, mirrored: GameResult) -> None:
    assert result.mirrored is mirrored
    assert result.for_side(Side.PLAYER) is result
    assert result.for_side(Side.PET) is mirrored


def test_the_cooldown_is_four_hours_and_the_bonus_ten() -> None:
    assert B.visit_cooldown == timedelta(hours=4)
    assert B.visit_happiness == 10
