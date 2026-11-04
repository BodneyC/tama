"""Attention calls: why the pet wants the player right now (SPEC §4)."""

from enum import StrEnum

from tama.domain.balance import Balance
from tama.domain.pet import Pet
from tama.domain.stage import LifeStage
from tama.domain.weight import WeightStatus, weight_status


class AttentionReason(StrEnum):
    """Something the player should deal with."""

    HUNGRY = "hungry"
    UNHAPPY = "unhappy"
    DIRTY = "dirty"
    SICK = "sick"
    POOP = "poop"
    MISBEHAVING = "misbehaving"
    LIGHTS = "lights"
    OVERWEIGHT = "overweight"
    UNDERWEIGHT = "underweight"


def attention_reasons(pet: Pet, balance: Balance) -> frozenset[AttentionReason]:
    """Return every current reason the pet is calling for attention.

    The UI shows an indicator while this is non-empty and can diff successive results to
    decide when to ring the bell.
    """
    if pet.stage in (LifeStage.EGG, LifeStage.DEAD) or pet.on_holiday:
        return frozenset()
    threshold = balance.attention_threshold
    weight = weight_status(pet, balance)
    checks = {
        AttentionReason.HUNGRY: pet.stats.hunger < threshold,
        AttentionReason.UNHAPPY: pet.stats.happiness < threshold,
        AttentionReason.DIRTY: pet.stats.hygiene < threshold,
        AttentionReason.SICK: pet.is_sick,
        AttentionReason.POOP: pet.poop_count > 0,
        AttentionReason.MISBEHAVING: pet.misbehaving,
        AttentionReason.LIGHTS: pet.is_asleep and pet.lights_on,
        AttentionReason.OVERWEIGHT: weight is WeightStatus.OVER,
        AttentionReason.UNDERWEIGHT: weight is WeightStatus.UNDER,
    }
    return frozenset(reason for reason, active in checks.items() if active)


def new_attention_calls(
    previous: frozenset[AttentionReason], current: frozenset[AttentionReason]
) -> frozenset[AttentionReason]:
    """The calls in ``current`` that weren't already raised in ``previous`` (ring once each).

    A call that clears and comes back later counts as new again.
    """
    return current - previous
