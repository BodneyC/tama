"""The pet's moves in the board games (SPEC §3.1, ADR 0006).

A heuristic rather than a search, so it is cheap, predictable to test and beatable: win if it
can, else block the player's win, else avoid moves that hand the player a win, else play the
best-placed move. With its stage's mistake chance it plays any legal move instead.

The pet usually plays ``Side.PET``; in a pet-vs-pet game (SPEC §3.2) the host plays
``Side.PLAYER`` with the same heuristic.
"""

from random import Random
from typing import Protocol, Self

from tama.domain.balance import Balance
from tama.domain.minigames import GameResult, Side
from tama.domain.stage import LifeStage
from tama.errors import GameOverError, IllegalMoveError


class BoardGame(Protocol):
    """What the opponent needs from a board game. Moves are plain ints (column or cell)."""

    @property
    def to_move(self) -> Side:
        """Whose turn it is."""
        ...

    @property
    def result(self) -> GameResult | None:
        """How the game went for the player, once it is over."""
        ...

    def legal_moves(self) -> tuple[int, ...]:
        """The moves that can be played now."""
        ...

    def play(self, move: int) -> Self:
        """Make ``move`` for the side to move."""
        ...

    def wins_with(self, move: int, side: Side) -> bool:
        """Whether ``move`` would win the game for ``side``."""
        ...

    def preference(self, move: int) -> int:
        """How well-placed ``move`` is: lower is better."""
        ...


def pet_move(
    game: BoardGame, stage: LifeStage, balance: Balance, rng: Random, *, side: Side = Side.PET
) -> int:
    """Choose a pet's next move, playing ``side`` (the pet's own side by default).

    Always draws from ``rng`` for the mistake roll first, so a replay from the same seed
    makes the same moves.

    Raises:
        GameOverError: If the game has already finished.
        IllegalMoveError: If it is the other side's turn.
    """
    if game.result is not None:
        raise GameOverError("the game is already over")
    if game.to_move is not side:
        raise IllegalMoveError(f"it is not the {side.value}'s turn")
    other = Side.PLAYER if side is Side.PET else Side.PET
    moves = game.legal_moves()
    if rng.random() < balance.opponent_mistake_chance(stage):
        return rng.choice(moves)
    for wanted in (side, other):  # win, else block
        decisive = [move for move in moves if game.wins_with(move, wanted)]
        if decisive:
            return rng.choice(decisive)
    safe = [move for move in moves if not _hands_over_a_win(game.play(move), other)]
    best = min(game.preference(move) for move in safe or moves)
    return rng.choice([move for move in safe or moves if game.preference(move) == best])


def _hands_over_a_win(after: BoardGame, other: Side) -> bool:
    """Whether ``other`` could win straight away from ``after``."""
    return any(after.wins_with(move, other) for move in after.legal_moves())
