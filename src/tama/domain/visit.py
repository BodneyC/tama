"""Visits: two of the player's pets spending time together (SPEC §3.2, ADR 0011).

The domain sees one pet at a time: these functions decide whether a pet can visit (or be
visited) and what starting a visit does to it. The other pet is only a name in the events.
Games between the two are applied with ``actions.apply_game_outcome`` from each pet's side.
"""

from dataclasses import replace
from enum import StrEnum

from tama.domain.balance import Balance
from tama.domain.events import Outcome, Visited
from tama.domain.pet import Pet
from tama.domain.stage import LifeStage
from tama.domain.stats import Stat
from tama.errors import VisitRefusedError


class VisitRefusal(StrEnum):
    """Why a pet can't visit or be visited right now, in the order they are reported."""

    EGG = "egg"
    DEAD = "dead"
    ON_HOLIDAY = "on_holiday"
    ASLEEP = "asleep"
    SICK = "sick"
    MISBEHAVING = "misbehaving"
    TOO_TIRED = "too_tired"


def visit_refusals(pet: Pet, balance: Balance) -> tuple[VisitRefusal, ...]:
    """Every reason ``pet`` can't visit, in ``VisitRefusal`` order; empty if it can.

    The same rule decides who may be invited and when a visit has to end, so a visit ends as
    soon as either pet couldn't have started it. An egg, a dead pet and a pet on holiday have
    that as their only reason.
    """
    if pet.stage is LifeStage.EGG:
        return (VisitRefusal.EGG,)
    if not pet.is_alive:
        return (VisitRefusal.DEAD,)
    if pet.on_holiday:
        return (VisitRefusal.ON_HOLIDAY,)
    checks = {
        VisitRefusal.ASLEEP: pet.is_asleep,
        VisitRefusal.SICK: pet.is_sick,
        VisitRefusal.MISBEHAVING: pet.misbehaving,
        VisitRefusal.TOO_TIRED: pet.stats.energy < balance.play_min_energy,
    }
    return tuple(reason for reason, applies in checks.items() if applies)


def can_visit(pet: Pet, balance: Balance) -> bool:
    """Whether ``pet`` can visit or be visited right now."""
    return not visit_refusals(pet, balance)


def start_visit(pet: Pet, friend: str, balance: Balance) -> Outcome:
    """``pet`` meets ``friend``: happier, unless it already had a visit within the cooldown.

    Every visit restarts the cooldown, so visits can't be farmed for happiness.

    Raises:
        VisitRefusedError: If ``pet`` can't visit (see ``visit_refusals``).
    """
    refusals = visit_refusals(pet, balance)
    if refusals:
        reasons = ", ".join(reason.value.replace("_", " ") for reason in refusals)
        raise VisitRefusedError(f"{pet.name} can't visit: {reasons}")
    recent = pet.last_visit is not None and pet.age - pet.last_visit < balance.visit_cooldown
    stats = pet.stats if recent else pet.stats.adjust(Stat.HAPPINESS, balance.visit_happiness)
    visited = replace(pet, stats=stats, last_visit=pet.age)
    return Outcome(visited, (Visited(pet.age, friend, cheered=not recent),))
