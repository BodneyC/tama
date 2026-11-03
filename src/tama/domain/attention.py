"""Attention calls: why the pet wants the player right now (SPEC §4)."""

from enum import StrEnum

from tama.domain.balance import Balance
from tama.domain.pet import Pet
from tama.domain.stage import LifeStage


class AttentionReason(StrEnum):
    """Something the player should deal with."""

    HUNGRY = "hungry"
    UNHAPPY = "unhappy"
    DIRTY = "dirty"
    SICK = "sick"
    POOP = "poop"
    MISBEHAVING = "misbehaving"
    LIGHTS = "lights"


def attention_reasons(pet: Pet, balance: Balance) -> frozenset[AttentionReason]:
    """Return every current reason the pet is calling for attention.

    The UI shows an indicator while this is non-empty and can diff successive results to
    decide when to ring the bell.
    """
    if pet.stage in (LifeStage.EGG, LifeStage.DEAD):
        return frozenset()
    threshold = balance.attention_threshold
    checks = {
        AttentionReason.HUNGRY: pet.stats.hunger < threshold,
        AttentionReason.UNHAPPY: pet.stats.happiness < threshold,
        AttentionReason.DIRTY: pet.stats.hygiene < threshold,
        AttentionReason.SICK: pet.is_sick,
        AttentionReason.POOP: pet.poop_count > 0,
        AttentionReason.MISBEHAVING: pet.misbehaving,
        AttentionReason.LIGHTS: pet.is_asleep and pet.lights_on,
    }
    return frozenset(reason for reason, active in checks.items() if active)
