"""Holiday: pausing a settled pet so nothing happens to it while the player is away.

See SPEC §2.6 and ADR 0008. ``advance`` leaves a paused pet frozen; this module decides when a
pet may be paused and records the start and end of a holiday.
"""

from dataclasses import replace
from datetime import datetime
from enum import StrEnum

from tama.domain.attention import attention_reasons
from tama.domain.balance import Balance
from tama.domain.events import Outcome, PausedForHoliday, PauseRefused, ResumedFromHoliday
from tama.domain.pet import Pet
from tama.domain.stage import LifeStage


class PauseBlocker(StrEnum):
    """Why a pet can't go on holiday right now (the attention calls, plus a few states)."""

    EGG = "egg"
    DEAD = "dead"
    ON_HOLIDAY = "on_holiday"
    HUNGRY = "hungry"
    UNHAPPY = "unhappy"
    DIRTY = "dirty"
    SICK = "sick"
    POOP = "poop"
    MISBEHAVING = "misbehaving"
    LIGHTS = "lights"


def pause_blockers(pet: Pet, balance: Balance) -> tuple[PauseBlocker, ...]:
    """Every reason ``pet`` can't be paused, sorted; empty if it can.

    Only a hatched, living pet with no attention calls is settled enough, so a holiday can't be
    used to dodge a need that is already low.
    """
    if pet.stage is LifeStage.EGG:
        return (PauseBlocker.EGG,)
    if not pet.is_alive:
        return (PauseBlocker.DEAD,)
    if pet.on_holiday:
        return (PauseBlocker.ON_HOLIDAY,)
    return tuple(sorted(PauseBlocker(reason.value) for reason in attention_reasons(pet, balance)))


def pause(pet: Pet, balance: Balance) -> Outcome:
    """Put ``pet`` on holiday as of its last update, or refuse with the reasons.

    The pet must be up to date (its ``updated_at`` is "now"), so no time goes unsimulated.
    """
    blockers = pause_blockers(pet, balance)
    if blockers:
        return Outcome(pet, (PauseRefused(pet.age, blockers),))
    paused = replace(pet, paused_since=pet.updated_at)
    return Outcome(paused, (PausedForHoliday(pet.age),))


def resume(pet: Pet, now: datetime) -> Outcome:
    """Bring ``pet`` back from holiday at ``now``, exactly as it was. No-op if not paused."""
    if pet.paused_since is None:
        return Outcome(pet)
    back = replace(pet, paused_since=None, updated_at=now)
    return Outcome(back, (ResumedFromHoliday(pet.age, now - pet.paused_since),))
