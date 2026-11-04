"""Headless balancing: play whole lives under different kinds of player, many times.

    uv run python -m tools.balance              # the shipped Balance
    uv run python -m tools.balance --seeds 40

A real ``--speed 60`` life takes six hours of play, so balancing uses simulated players
instead: each profile checks on the pet at its own rhythm during its waking hours and does
what an ordinary player would. Balance changes should be judged on these numbers (ROADMAP M6).
"""

import argparse
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, time, timedelta
from fractions import Fraction
from random import Random
from statistics import mean

from tama.domain.actions import apply, apply_game_outcome, refusal
from tama.domain.balance import DEFAULT_BALANCE, Balance
from tama.domain.context import Context
from tama.domain.events import (
    Action,
    CareMistake,
    Died,
    Event,
    Evolved,
    GotSick,
    Misbehaved,
    MisbehaviourIgnored,
    MistakeReason,
    Outcome,
)
from tama.domain.minigames import GameKind, GameResult
from tama.domain.pet import Pet, new_egg
from tama.domain.simulation import advance
from tama.domain.stage import LifeStage, Variant
from tama.domain.weight import WeightStatus, weight_status

START = datetime(2026, 1, 5, 9, tzinfo=UTC)  # a Monday morning
TICK = timedelta(minutes=1)


@dataclass(frozen=True)
class Player:
    """How often a player looks at the pet, and when they're around at all."""

    name: str
    every: timedelta
    awake_from: time = time(7)
    awake_until: time = time(23)
    away: tuple[tuple[timedelta, timedelta], ...] = ()
    """(start, length) offsets from hatching when the player can't look at all."""
    snacker: bool = False
    """Cheers the pet up with snacks instead of games (it gets fat: SPEC §2.7)."""

    def present(self, now: datetime) -> bool:
        """Whether the player could check on the pet at ``now``."""
        if any(start <= now - START < start + length for start, length in self.away):
            return False
        return self.awake_from <= now.time() < self.awake_until


PLAYERS = (
    Player("diligent (every 5 min)", timedelta(minutes=5)),
    Player("casual (every 30 min)", timedelta(minutes=30)),
    Player("busy (every 2 h)", timedelta(hours=2)),
    Player(
        "casual, away a day",
        timedelta(minutes=30),
        away=((timedelta(days=4, hours=-2), timedelta(days=1)),),
    ),
    Player("casual snacker (every 30 min)", timedelta(minutes=30), snacker=True),
)


def care(
    pet: Pet,
    ctx: Context,
    *,
    snacker: bool = False,
    seen: Callable[[Pet, Outcome], None] | None = None,
) -> Pet:
    """What an ordinary player does when they look: fix whatever needs fixing.

    ``seen`` is told about every outcome along with the pet before it (e.g. to keep a journal).
    """

    def done(outcome: Outcome) -> None:
        nonlocal pet
        if seen is not None:
            seen(pet, outcome)
        pet = outcome.pet  # refused actions just don't happen

    def act(action: Action) -> None:
        done(apply(pet, action, ctx))

    if pet.is_sick and pet.is_asleep:  # medicine needs it awake; the tantrum is dealt with next
        act(Action.WAKE)
    if pet.misbehaving:  # first: a tantrum refuses food and games
        act(Action.DISCIPLINE)
    if pet.is_sick:
        act(Action.MEDICINE)
        act(Action.MEDICINE)
    if pet.poop_count or pet.stats.hygiene < 60:
        act(Action.CLEAN)
    while pet.stats.hunger < 70 and refusal(pet, Action.MEAL, ctx.balance) is None:
        act(Action.MEAL)
    for _ in range(3):  # a few games while it's unhappy and has the energy
        if pet.stats.happiness >= 70 or refusal(pet, Action.PLAY, ctx.balance) is not None:
            break
        if snacker:  # a treat is quicker than a game
            act(Action.SNACK)
            continue
        result = GameResult.WIN if ctx.rng.random() < 0.6 else GameResult.LOSS
        done(apply_game_outcome(pet, result, game=GameKind.LEFT_RIGHT, ctx=ctx))
    if pet.stats.happiness < 50:
        act(Action.SNACK)
    if pet.is_asleep == pet.lights_on:
        act(Action.LIGHTS)
    return pet


@dataclass
class Life:
    """What happened in one life."""

    reached: LifeStage = LifeStage.EGG
    variant: Variant = Variant.DEFAULT
    died_of: str = ""
    age: timedelta = timedelta(0)
    mistakes: int = 0
    sicknesses: int = 0
    misbehaved: int = 0
    ignored: int = 0
    discipline_at_adult: int | None = None
    mistakes_at_adult: int | None = None
    weight_at_adult: int | None = None
    out_of_band: timedelta = timedelta(0)
    weight_mistakes: int = 0
    events: Counter[str] = field(default_factory=Counter)


def live(player: Player, seed: int, balance: Balance) -> Life:
    """Play one life as ``player``."""
    ctx = Context(rng=Random(seed), balance=balance, tz=UTC)
    pet = new_egg("Sim", START, Random(seed), balance)
    life = Life()
    # Players aren't in step with the pet's clock: each gap is 0.5-1.5x their usual one, drawn
    # from the player's own RNG so the pet's randomness is the same for every profile.
    habits = Random(seed + 1_000_003)
    next_check = START
    now = START
    while pet.is_alive:
        out = advance(pet, TICK, ctx)
        pet, now = out.pet, now + TICK
        record(life, pet, out.events)
        if pet.is_alive and weight_status(pet, balance) is not WeightStatus.HEALTHY:
            life.out_of_band += TICK
        if now >= next_check and player.present(now):
            pet = care(pet, ctx, snacker=player.snacker)
            gap = player.every * habits.uniform(0.5, 1.5)
            next_check = now + max(TICK, gap)
    life.age = pet.age
    life.mistakes = pet.care_mistakes
    life.variant = pet.variant
    return life


def record(life: Life, pet: Pet, events: tuple[Event, ...]) -> None:
    """Note the milestones of a life."""
    if pet.stage is not LifeStage.DEAD:
        life.reached = pet.stage
    for event in events:
        life.events[type(event).__name__] += 1
        if isinstance(event, GotSick):
            life.sicknesses += 1
        if isinstance(event, Died):
            life.died_of = event.cause.value
        if isinstance(event, Misbehaved):
            life.misbehaved += 1
        if isinstance(event, MisbehaviourIgnored):
            life.ignored += 1
        if isinstance(event, Evolved) and event.to_stage is LifeStage.ADULT:
            life.discipline_at_adult = pet.stats.discipline
            life.mistakes_at_adult = pet.care_mistakes
            life.weight_at_adult = pet.weight
        if isinstance(event, CareMistake) and event.reason is MistakeReason.WEIGHT:
            life.weight_mistakes += 1


def report(player: Player, lives: list[Life]) -> str:
    """One profile's results as a few lines."""
    old_age = sum(life.died_of == "old_age" for life in lives)
    reached = Counter(life.reached.value for life in lives)
    days = mean(life.age / timedelta(days=1) for life in lives)
    adults = [life for life in lives if life.discipline_at_adult is not None]
    disciplined = sum(
        life.discipline_at_adult is not None and life.discipline_at_adult >= 50 for life in adults
    )
    caught = mean(1 - life.ignored / life.misbehaved for life in lives if life.misbehaved)
    good = sum(life.variant is Variant.GOOD for life in lives)
    chubby = sum(life.variant is Variant.CHUBBY for life in lives)
    out_of_band = mean(life.out_of_band / life.age for life in lives if life.age)
    weights = [life.weight_at_adult for life in adults if life.weight_at_adult is not None]
    return "\n".join(
        [
            f"{player.name}",
            f"  died of old age: {old_age}/{len(lives)}   mean age: {days:.1f} d",
            f"  last stage: {dict(reached)}",
            f"  care mistakes: mean {mean(life.mistakes for life in lives):.1f}"
            f"   sicknesses: mean {mean(life.sicknesses for life in lives):.1f}",
            f"  misbehaviour: mean {mean(life.misbehaved for life in lives):.1f} per life,"
            f" {caught:.0%} disciplined in time",
            f"  discipline at adulthood: mean"
            f" {mean(life.discipline_at_adult or 0 for life in adults) if adults else 0:.0f},"
            f" >= 50 in {disciplined}/{len(adults)}   mistakes by then:"
            f" {mean(life.mistakes_at_adult or 0 for life in adults) if adults else 0:.1f}"
            f"   good adults: {good}/{len(lives)}",
            f"  weight: {out_of_band:.0%} of life out of band,"
            f" {mean(life.weight_mistakes for life in lives):.1f} weight mistakes,"
            f" at adulthood {min(weights, default=0)}-{max(weights, default=0)} g"
            f" (mean {mean(weights) if weights else 0:.0f})   chubby adults: {chubby}/{len(lives)}",
        ]
    )


def _run(args: tuple[Player, int, Balance]) -> Life:
    return live(*args)


def simulate(balance: Balance, seeds: int, players: tuple[Player, ...] = PLAYERS) -> str:
    """Every profile over ``seeds`` lives each."""
    jobs = [(player, seed, balance) for player in players for seed in range(seeds)]
    with ProcessPoolExecutor() as pool:
        lives = list(pool.map(_run, jobs))
    return "\n\n".join(
        report(player, lives[i * seeds : (i + 1) * seeds]) for i, player in enumerate(players)
    )


def main(argv: list[str] | None = None, balance: Balance = DEFAULT_BALANCE) -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=20, help="lives per player profile")
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="FIELD=VALUE",
        help="try another Balance value; durations in minutes (e.g. --set sick_health=8)",
    )
    args = parser.parse_args(argv)
    print(simulate(with_changes(balance, args.set), args.seeds))  # noqa: T201 - CLI output


def with_changes(balance: Balance, items: list[str]) -> Balance:
    """``balance`` with ``FIELD=VALUE`` overrides, parsed like each field's current value."""
    changes: dict[str, object] = {}
    for item in items:
        key, value = item.split("=")
        current = getattr(balance, key)
        if isinstance(current, timedelta):
            changes[key] = timedelta(minutes=float(value))
        elif isinstance(current, Fraction):
            changes[key] = Fraction(value)
        else:
            changes[key] = type(current)(value)
    return replace(balance, **changes)  # type: ignore[arg-type] # fields checked above


if __name__ == "__main__":
    main()
