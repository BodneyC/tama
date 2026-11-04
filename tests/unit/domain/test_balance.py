from datetime import time, timedelta
from fractions import Fraction

import pytest

from tama.domain.balance import DEFAULT_BALANCE, Balance
from tama.domain.stage import LifeStage
from tama.errors import InvalidArgumentError


def test_default_step_is_one_minute() -> None:
    assert DEFAULT_BALANCE.step == timedelta(minutes=1)


@pytest.mark.parametrize("step", [timedelta(0), timedelta(minutes=-1), timedelta(minutes=7)])
def test_step_must_be_positive_and_divide_an_hour(step: timedelta) -> None:
    with pytest.raises(InvalidArgumentError, match="step"):
        Balance(step=step)


@pytest.mark.parametrize(
    ("stage", "expected"),
    [
        (LifeStage.EGG, timedelta(0)),
        (LifeStage.BABY, timedelta(minutes=1)),
        (LifeStage.CHILD, timedelta(hours=1)),
        (LifeStage.TEEN, timedelta(days=1)),
        (LifeStage.ADULT, timedelta(days=3)),
        (LifeStage.ELDER, timedelta(days=10)),
    ],
)
def test_stage_ages_follow_spec(stage: LifeStage, expected: timedelta) -> None:
    assert DEFAULT_BALANCE.stage_age(stage) == expected


def test_dead_has_no_entry_age() -> None:
    with pytest.raises(InvalidArgumentError, match="dead"):
        DEFAULT_BALANCE.stage_age(LifeStage.DEAD)


@pytest.mark.parametrize(
    ("stage", "expected"),
    [
        (LifeStage.BABY, Fraction(3, 2)),
        (LifeStage.CHILD, Fraction(1)),
        (LifeStage.ADULT, Fraction(1)),
        (LifeStage.ELDER, Fraction(3, 4)),
    ],
)
def test_stage_decay_multiplier(stage: LifeStage, expected: Fraction) -> None:
    assert DEFAULT_BALANCE.decay_multiplier(stage) == expected


def test_default_night_window() -> None:
    assert DEFAULT_BALANCE.night_start == time(22)
    assert DEFAULT_BALANCE.night_end == time(7)


@pytest.mark.parametrize(
    ("stage", "expected"),
    [
        (LifeStage.BABY, 0.6),
        (LifeStage.CHILD, 0.4),
        (LifeStage.TEEN, 0.25),
        (LifeStage.ADULT, 0.15),
        (LifeStage.ELDER, 0.2),
    ],
)
def test_opponent_mistake_chance_per_stage(stage: LifeStage, expected: float) -> None:
    assert DEFAULT_BALANCE.opponent_mistake_chance(stage) == expected


@pytest.mark.parametrize("stage", [LifeStage.EGG, LifeStage.DEAD])
def test_eggs_and_dead_pets_never_play(stage: LifeStage) -> None:
    with pytest.raises(InvalidArgumentError, match="play"):
        DEFAULT_BALANCE.opponent_mistake_chance(stage)


@pytest.mark.parametrize(
    "stage", [LifeStage.BABY, LifeStage.CHILD, LifeStage.TEEN, LifeStage.ADULT, LifeStage.ELDER]
)
def test_every_living_stage_has_a_healthy_weight_band(stage: LifeStage) -> None:
    low, high = DEFAULT_BALANCE.weight_band(stage)

    assert DEFAULT_BALANCE.min_weight <= low <= high


def test_a_new_pet_starts_in_the_baby_band() -> None:
    low, high = DEFAULT_BALANCE.weight_band(LifeStage.BABY)

    assert low <= DEFAULT_BALANCE.start_weight <= high


def test_the_band_rises_from_baby_to_adult() -> None:
    stages = [LifeStage.BABY, LifeStage.CHILD, LifeStage.TEEN, LifeStage.ADULT]
    bands = [DEFAULT_BALANCE.weight_band(stage) for stage in stages]

    assert bands == sorted(bands)
    assert bands[0] != bands[-1]


@pytest.mark.parametrize("stage", [LifeStage.EGG, LifeStage.DEAD])
def test_eggs_and_dead_pets_have_no_weight_band(stage: LifeStage) -> None:
    with pytest.raises(InvalidArgumentError, match="weight"):
        DEFAULT_BALANCE.weight_band(stage)


@pytest.mark.parametrize(
    "band",
    [(10, 9), (0, 10)],
    ids=["upside-down", "below-min-weight"],
)
def test_weight_bands_must_make_sense(band: tuple[int, int]) -> None:
    with pytest.raises(InvalidArgumentError, match="weight band"):
        Balance(teen_weight=band)
