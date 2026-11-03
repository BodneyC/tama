"""Player actions (SPEC §3).

``apply`` validates an action and applies it, returning an ``Outcome`` whose events describe
what happened. A refused action leaves the pet unchanged and yields a single ``Refused``
event. ``Action.PLAY`` only checks that the pet is willing to play; the mini-game's result
is applied afterwards with ``apply_game_outcome``.
"""

from collections.abc import Callable
from dataclasses import replace

from tama.domain.balance import HOUR, Balance
from tama.domain.context import Context
from tama.domain.events import (
    Action,
    Ate,
    Cleaned,
    Disciplined,
    Event,
    GotSick,
    LightsToggled,
    MedicineGiven,
    Outcome,
    Played,
    RefusalReason,
    Refused,
)
from tama.domain.minigames import GameResult
from tama.domain.pet import ZERO, Pet
from tama.domain.stage import LifeStage
from tama.domain.stats import STAT_MAX, Stat

_REFUSED_BY_EGG = frozenset(
    {Action.MEAL, Action.SNACK, Action.PLAY, Action.DISCIPLINE, Action.MEDICINE}
)
_REFUSED_WHEN_ASLEEP = frozenset({Action.MEAL, Action.SNACK, Action.PLAY, Action.DISCIPLINE})


def refusal(pet: Pet, action: Action, balance: Balance) -> RefusalReason | None:
    """Return why ``pet`` would refuse ``action``, or ``None`` if it would accept it."""
    if not pet.is_alive:
        return RefusalReason.DEAD
    if pet.stage is LifeStage.EGG and action in _REFUSED_BY_EGG:
        return RefusalReason.EGG
    if pet.is_asleep and action in _REFUSED_WHEN_ASLEEP:
        return RefusalReason.ASLEEP
    return _specific_refusal(pet, action, balance)


def _specific_refusal(pet: Pet, action: Action, balance: Balance) -> RefusalReason | None:
    if action is Action.MEAL and pet.stats.hunger >= balance.meal_refuse_at_hunger:
        return RefusalReason.NOT_HUNGRY
    if action is Action.PLAY and pet.stats.energy < balance.play_min_energy:
        return RefusalReason.TOO_TIRED
    if action is Action.MEDICINE and not pet.is_sick:
        return RefusalReason.NOT_SICK
    return None


def apply(pet: Pet, action: Action, ctx: Context) -> Outcome:
    """Apply ``action`` to ``pet`` if it is accepted."""
    reason = refusal(pet, action, ctx.balance)
    if reason is not None:
        return Outcome(pet, (Refused(pet.age, action, reason),))
    return _HANDLERS[action](pet, ctx)


def apply_game_outcome(pet: Pet, result: GameResult, *, ctx: Context) -> Outcome:
    """Apply the result of a finished mini-game.

    Only death refuses this: the game was already accepted, so a pet that dozed off
    mid-game still gets the result.
    """
    if not pet.is_alive:
        return Outcome(pet, (Refused(pet.age, Action.PLAY, RefusalReason.DEAD),))
    b = ctx.balance
    happiness = {
        GameResult.WIN: b.play_win_happiness,
        GameResult.DRAW: b.play_draw_happiness,
        GameResult.LOSS: b.play_lose_happiness,
    }[result]
    weight_change = b.play_win_weight if result is GameResult.WIN else 0
    stats = pet.stats.adjust(Stat.HAPPINESS, happiness).adjust(Stat.ENERGY, b.play_energy)
    played = replace(pet, stats=stats, weight=_weight(pet, weight_change, b))
    return Outcome(played, (Played(pet.age, result),))


def _weight(pet: Pet, delta: int, b: Balance) -> int:
    return max(b.min_weight, pet.weight + delta)


def _meal(pet: Pet, ctx: Context) -> Outcome:
    b = ctx.balance
    fed = replace(
        pet,
        stats=pet.stats.adjust(Stat.HUNGER, b.meal_hunger),
        weight=_weight(pet, b.meal_weight, b),
    )
    return Outcome(fed, (Ate(pet.age, Action.MEAL),))


def _snack(pet: Pet, ctx: Context) -> Outcome:
    b = ctx.balance
    recent = tuple(t for t in pet.recent_snacks if pet.age - t < HOUR)
    stats = pet.stats.adjust(Stat.HAPPINESS, b.snack_happiness).adjust(Stat.HUNGER, b.snack_hunger)
    fed = replace(
        pet, stats=stats, weight=_weight(pet, b.snack_weight, b), recent_snacks=(*recent, pet.age)
    )
    events: list[Event] = [Ate(pet.age, Action.SNACK)]
    overindulged = len(recent) >= b.snack_limit_per_hour
    if overindulged and not pet.is_sick and ctx.rng.random() < b.snack_sickness_chance:
        doses = ctx.rng.randint(b.sickness_min_doses, b.sickness_max_doses)
        fed = replace(fed, sickness_doses=doses)
        events.append(GotSick(pet.age, doses))
    return Outcome(fed, tuple(events))


def _play(pet: Pet, _ctx: Context) -> Outcome:
    return Outcome(pet)


def _clean(pet: Pet, _ctx: Context) -> Outcome:
    cleaned = replace(pet, poop_count=0, stats=pet.stats.with_value(Stat.HYGIENE, STAT_MAX))
    return Outcome(cleaned, (Cleaned(pet.age, poops_removed=pet.poop_count),))


def _medicine(pet: Pet, _ctx: Context) -> Outcome:
    doses = pet.sickness_doses - 1
    treated = replace(pet, sickness_doses=doses)
    return Outcome(treated, (MedicineGiven(pet.age, cured=doses == 0),))


def _lights(pet: Pet, _ctx: Context) -> Outcome:
    on = not pet.lights_on
    return Outcome(replace(pet, lights_on=on), (LightsToggled(pet.age, on=on),))


def _discipline(pet: Pet, ctx: Context) -> Outcome:
    b = ctx.balance
    if not pet.misbehaving:
        upset = replace(
            pet, stats=pet.stats.adjust(Stat.HAPPINESS, b.discipline_unwarranted_happiness)
        )
        return Outcome(upset, (Disciplined(pet.age, effective=False),))
    behaved = replace(
        pet,
        misbehaving=False,
        stats=pet.stats.adjust(Stat.DISCIPLINE, b.discipline_gain),
        timers=replace(pet.timers, misbehaving=ZERO),
    )
    return Outcome(behaved, (Disciplined(pet.age, effective=True),))


_HANDLERS: dict[Action, Callable[[Pet, Context], Outcome]] = {
    Action.MEAL: _meal,
    Action.SNACK: _snack,
    Action.PLAY: _play,
    Action.CLEAN: _clean,
    Action.MEDICINE: _medicine,
    Action.LIGHTS: _lights,
    Action.DISCIPLINE: _discipline,
}
