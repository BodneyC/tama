"""How long a family line lasts: the balance tool's players, keeping a line going for a month.

    uv run python -m tools.generations             # 20 lines per player, 30 days each
    uv run python -m tools.generations --days 60

Each line starts from a new egg. When a pet dies of old age the player hatches its egg
straight away (SPEC §2.8); a death of poor health ends the line. Reports how many generations
each player reaches and how lines end.
"""

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import UTC, timedelta
from random import Random
from statistics import mean

from tama.domain.balance import DEFAULT_BALANCE, Balance
from tama.domain.context import Context
from tama.domain.lineage import hatch_heir, heir_name
from tama.domain.pet import new_egg
from tama.domain.simulation import advance
from tools.balance import PLAYERS, START, TICK, Player, care


@dataclass(frozen=True)
class Line:
    """How far one family line got."""

    generations: int
    """The generation alive (or last to die) when the time ran out or the line ended."""
    ended: str
    """``"going"`` if a pet was still alive at the end, else what ended it."""


def keep_a_line(player: Player, seed: int, balance: Balance, days: int) -> Line:
    """Play ``days`` as ``player``, hatching each egg as soon as it is left."""
    ctx = Context(rng=Random(seed), balance=balance, tz=UTC)
    pet = new_egg("Sim", START, Random(seed), balance)
    habits = Random(seed + 1_000_003)
    next_check, now, end = START, START, START + timedelta(days=days)
    while now < end:
        pet, now = advance(pet, TICK, ctx).pet, now + TICK
        if not pet.is_alive:
            if not pet.egg_waiting:
                return Line(pet.generation, "poor health")
            name = heir_name(pet.name) or "Sim"
            pet, _ = hatch_heir(pet, name, now, Random(ctx.rng.getrandbits(64)), balance)
        if now >= next_check and player.present(now):
            pet = care(pet, ctx, snacker=player.snacker)
            next_check = now + max(TICK, player.every * habits.uniform(0.5, 1.5))
    return Line(pet.generation, "going")


def report(player: Player, lines: list[Line]) -> str:
    """One player's lines in a couple of rows."""
    reached = Counter(line.generations for line in lines)
    ended = Counter(line.ended for line in lines)
    spread = ", ".join(f"gen {g}: {n}" for g, n in sorted(reached.items()))
    return "\n".join(
        [
            player.name,
            f"  generations: mean {mean(line.generations for line in lines):.1f}   ({spread})",
            f"  lines: {dict(ended)}",
        ]
    )


def _run(args: tuple[Player, int, Balance, int]) -> Line:
    return keep_a_line(*args)


def simulate(balance: Balance, seeds: int, days: int) -> str:
    """Every player keeps ``seeds`` lines going for ``days`` days."""
    players = [p for p in PLAYERS if not p.away]  # a day away is fatal; it says nothing here
    jobs = [(player, seed, balance, days) for player in players for seed in range(seeds)]
    with ProcessPoolExecutor() as pool:
        lines = list(pool.map(_run, jobs))
    return "\n\n".join(
        report(player, lines[i * seeds : (i + 1) * seeds]) for i, player in enumerate(players)
    )


def main(argv: list[str] | None = None) -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=20, help="lines per player")
    parser.add_argument("--days", type=int, default=30, help="how long to keep each line going")
    args = parser.parse_args(argv)
    print(simulate(DEFAULT_BALANCE, args.seeds, args.days))  # noqa: T201 - CLI output


if __name__ == "__main__":
    main()
