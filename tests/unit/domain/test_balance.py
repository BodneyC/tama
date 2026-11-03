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
