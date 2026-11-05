from datetime import timedelta
from typing import Any

import pytest

from tama.domain.animation import (
    AnimationKey,
    looping_animation,
    reaction_animation,
    select_animation,
)
from tama.domain.events import (
    Action,
    Ate,
    Cleaned,
    Died,
    Disciplined,
    Event,
    Evolved,
    FellAsleep,
    MedicineGiven,
    Played,
    PlayedWith,
    RefusalReason,
    Refused,
    Visited,
)
from tama.domain.minigames import GameKind, GameResult
from tama.domain.stage import DeathCause, LifeStage, Variant
from tests.factories import make_pet

AGE = timedelta(hours=2)


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({}, AnimationKey.IDLE),
        ({"stage": LifeStage.EGG}, AnimationKey.WOBBLE),
        ({"stage": LifeStage.DEAD, "cause_of_death": DeathCause.OLD_AGE}, AnimationKey.DEAD),
        ({"is_asleep": True}, AnimationKey.SLEEP),
        ({"is_asleep": True, "sickness_doses": 1}, AnimationKey.SLEEP),
        ({"sickness_doses": 1}, AnimationKey.SICK),
        ({"misbehaving": True}, AnimationKey.MISBEHAVE),
        ({"misbehaving": True, "sickness_doses": 1}, AnimationKey.SICK),
        ({"misbehaving": True, "is_asleep": True}, AnimationKey.SLEEP),
    ],
)
def test_looping_animation_reflects_state(
    overrides: dict[str, Any], expected: AnimationKey
) -> None:
    assert looping_animation(make_pet(**overrides)) is expected


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        (Evolved(AGE, LifeStage.EGG, LifeStage.BABY, Variant.DEFAULT), AnimationKey.HATCH),
        (Evolved(AGE, LifeStage.BABY, LifeStage.CHILD, Variant.DEFAULT), AnimationKey.EVOLVE),
        (Ate(AGE, Action.MEAL), AnimationKey.EAT),
        (Ate(AGE, Action.SNACK), AnimationKey.EAT),
        (Played(AGE, GameResult.WIN, GameKind.LEFT_RIGHT), AnimationKey.HAPPY),
        (Played(AGE, GameResult.DRAW, GameKind.LEFT_RIGHT), AnimationKey.PLAY),
        (Played(AGE, GameResult.LOSS, GameKind.LEFT_RIGHT), AnimationKey.PLAY),
        (Cleaned(AGE, poops_removed=1), AnimationKey.CLEAN),
        (MedicineGiven(AGE, cured=True), AnimationKey.HAPPY),
        (MedicineGiven(AGE, cured=False), None),
        (Refused(AGE, Action.PLAY, RefusalReason.TOO_TIRED), AnimationKey.REFUSE),
        (Disciplined(AGE, effective=False), AnimationKey.REFUSE),
        (Disciplined(AGE, effective=True), None),
        (FellAsleep(AGE), None),
        (Died(AGE, DeathCause.OLD_AGE), None),
        (Visited(AGE, "Pip", cheered=False), AnimationKey.HAPPY),
        (PlayedWith(AGE, "Pip", GameKind.TIC_TAC_TOE, GameResult.WIN), AnimationKey.HAPPY),
        (PlayedWith(AGE, "Pip", GameKind.TIC_TAC_TOE, GameResult.DRAW), AnimationKey.PLAY),
        (PlayedWith(AGE, "Pip", GameKind.TIC_TAC_TOE, GameResult.LOSS), AnimationKey.PLAY),
    ],
)
def test_reaction_animation_for_events(event: Event, expected: AnimationKey | None) -> None:
    assert reaction_animation(event) is expected


def test_select_prefers_reaction_over_loop() -> None:
    pet = make_pet()

    assert select_animation(pet, Ate(AGE, Action.MEAL)) is AnimationKey.EAT


def test_select_falls_back_to_loop() -> None:
    pet = make_pet(sickness_doses=1)

    assert select_animation(pet) is AnimationKey.SICK
    assert select_animation(pet, FellAsleep(AGE)) is AnimationKey.SICK
