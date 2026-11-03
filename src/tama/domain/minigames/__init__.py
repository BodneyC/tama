"""Mini-games played with the pet (SPEC §3.1, ADR 0006).

Each game is a frozen state object whose moves return a new state, with ``result`` set (from
the player's side) once it is over. The pet's moves in the board games come from
``opponent``.
"""

from enum import StrEnum


class GameKind(StrEnum):
    """The games on the game select dialog, in the order they are listed."""

    LEFT_RIGHT = "left_right"
    FOUR_IN_A_ROW = "four_in_a_row"
    TIC_TAC_TOE = "tic_tac_toe"


class GameResult(StrEnum):
    """How a finished game went for the player."""

    WIN = "win"
    DRAW = "draw"
    LOSS = "loss"


class Side(StrEnum):
    """Who a piece or mark belongs to. The player always moves first."""

    PLAYER = "player"
    PET = "pet"


def result_for(winner: Side | None, *, full: bool) -> GameResult | None:
    """A board game's result from the player's side: ``None`` while it can go on."""
    if winner is Side.PLAYER:
        return GameResult.WIN
    if winner is Side.PET:
        return GameResult.LOSS
    return GameResult.DRAW if full else None
