"""Headless board-game balancing: many games against the pet at every life stage.

    uv run python -m tools.games              # the shipped Balance
    uv run python -m tools.games --games 2000 --set adult_mistake_chance=0.1

Two scripted players stand in for people: a *random* one who drops pieces anywhere, and a
*casual* one who takes a win and blocks the pet's when they see them, else plays at random.
Young pets should lose most games to the casual player; grown-ups should put up a fight
(ROADMAP M6.5).
"""

import argparse
from collections import Counter
from collections.abc import Callable
from random import Random

from tama.domain.balance import DEFAULT_BALANCE, Balance
from tama.domain.minigames import GameResult, Side
from tama.domain.minigames.four_in_a_row import FourInARow
from tama.domain.minigames.opponent import pet_move
from tama.domain.minigames.tic_tac_toe import TicTacToe
from tama.domain.stage import LifeStage
from tools.balance import with_changes

type Game = FourInARow | TicTacToe
type Player = Callable[[Game, Random], int]

STAGES = (LifeStage.BABY, LifeStage.CHILD, LifeStage.TEEN, LifeStage.ADULT, LifeStage.ELDER)
BOARDS: dict[str, Callable[[], Game]] = {"Four in a Row": FourInARow, "Tic-Tac-Toe": TicTacToe}


def random_player(game: Game, rng: Random) -> int:
    """Any legal move."""
    return rng.choice(game.legal_moves())


def casual_player(game: Game, rng: Random) -> int:
    """Win if you can, block if you must, else anything."""
    moves = game.legal_moves()
    for side in (Side.PLAYER, Side.PET):
        decisive = [move for move in moves if game.wins_with(move, side)]
        if decisive:
            return rng.choice(decisive)
    return rng.choice(moves)


PLAYERS: dict[str, Player] = {"random": random_player, "casual": casual_player}


def play(
    new_game: Callable[[], Game], player: Player, stage: LifeStage, balance: Balance, seed: int
) -> GameResult:
    """One game, the player moving first."""
    rng = Random(seed)
    game = new_game()
    while game.result is None:
        if game.to_move is Side.PLAYER:
            game = game.play(player(game, rng))
        else:
            game = game.play(pet_move(game, stage, balance, rng))
    return game.result


def results(
    new_game: Callable[[], Game], player: Player, stage: LifeStage, balance: Balance, games: int
) -> Counter[GameResult]:
    """How ``games`` games went for the player."""
    return Counter(play(new_game, player, stage, balance, seed) for seed in range(games))


def report(balance: Balance, games: int) -> str:
    """Win/draw/loss percentages for every board, player and stage."""
    lines: list[str] = []
    for board, new_game in BOARDS.items():
        for name, player in PLAYERS.items():
            lines.append(f"{board}, {name} player (win / draw / loss %)")
            for stage in STAGES:
                counts = results(new_game, player, stage, balance, games)
                pct = [100 * counts[result] / games for result in GameResult]
                lines.append(f"  {stage.value:<6} {pct[0]:5.1f} {pct[1]:5.1f} {pct[2]:5.1f}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None, balance: Balance = DEFAULT_BALANCE) -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--games", type=int, default=500, help="games per stage and player")
    parser.add_argument(
        "--set", action="append", default=[], metavar="FIELD=VALUE", help="try a Balance value"
    )
    args = parser.parse_args(argv)
    print(report(with_changes(balance, args.set), args.games))  # noqa: T201 - CLI output


if __name__ == "__main__":
    main()
