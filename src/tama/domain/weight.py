"""Whether a pet's weight is healthy for its stage (SPEC §2.7)."""

from enum import StrEnum

from tama.domain.balance import Balance
from tama.domain.pet import Pet
from tama.domain.stage import LifeStage


class WeightStatus(StrEnum):
    """Where a pet's weight sits against its stage's healthy band."""

    UNDER = "underweight"
    HEALTHY = "healthy"
    OVER = "overweight"


def weight_status_at(weight: int, stage: LifeStage, balance: Balance) -> WeightStatus:
    """How ``weight`` compares with the healthy band at ``stage`` (eggs and the dead: healthy)."""
    if stage in (LifeStage.EGG, LifeStage.DEAD):
        return WeightStatus.HEALTHY
    low, high = balance.weight_band(stage)
    if weight < low:
        return WeightStatus.UNDER
    if weight > high:
        return WeightStatus.OVER
    return WeightStatus.HEALTHY


def weight_status(pet: Pet, balance: Balance) -> WeightStatus:
    """How the pet's weight compares with the healthy band for its current stage."""
    return weight_status_at(pet.weight, pet.stage, balance)
