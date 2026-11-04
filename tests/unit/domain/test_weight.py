import pytest

from tama.domain.balance import DEFAULT_BALANCE, Balance
from tama.domain.stage import DeathCause, LifeStage
from tama.domain.weight import WeightStatus, weight_status, weight_status_at
from tests.factories import make_pet

BALANCE = Balance(child_weight=(8, 18))


@pytest.mark.parametrize(
    ("weight", "expected"),
    [
        (7, WeightStatus.UNDER),
        (8, WeightStatus.HEALTHY),
        (18, WeightStatus.HEALTHY),
        (19, WeightStatus.OVER),
    ],
)
def test_status_against_the_stage_band(weight: int, expected: WeightStatus) -> None:
    pet = make_pet(stage=LifeStage.CHILD, weight=weight)

    assert weight_status(pet, BALANCE) is expected


def test_status_at_another_stage_uses_that_stage_band() -> None:
    teen_band = DEFAULT_BALANCE.weight_band(LifeStage.TEEN)

    assert weight_status_at(teen_band[1] + 1, LifeStage.TEEN, DEFAULT_BALANCE) is WeightStatus.OVER


def test_eggs_are_always_healthy() -> None:
    assert weight_status(make_pet(stage=LifeStage.EGG, weight=200), BALANCE) is WeightStatus.HEALTHY


def test_dead_pets_are_always_healthy() -> None:
    pet = make_pet(stage=LifeStage.DEAD, weight=200, cause_of_death=DeathCause.OLD_AGE)

    assert weight_status(pet, BALANCE) is WeightStatus.HEALTHY
