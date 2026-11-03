"""Tic-Tac-Toe against the pet (SPEC §3.1)."""

from typing import ClassVar, override

from textual.binding import Binding, BindingType

from tama.domain.minigames import Side
from tama.domain.minigames.tic_tac_toe import TicTacToe
from tama.services.session import GameSession
from tama.ui.screens.games.board import BoardGameScreen, highlight
from tama.ui.widgets.pet_view import ViewOptions

KEYPAD = {7: 0, 8: 1, 9: 2, 4: 3, 5: 4, 6: 5, 1: 6, 2: 7, 3: 8}
"""Number keys laid out like a numeric keypad: 7 is top-left, 3 bottom-right."""
MARKS = {Side.PLAYER: "✕", Side.PET: "◯"}


def tic_tac_toe_markup(game: TicTacToe, cursor: int | None, *, mono: bool) -> str:
    """The board as content markup, with ``cursor`` (if any) and a winning line highlighted."""
    winning = set(game.line)
    rows: list[str] = []
    for top in (0, 3, 6):
        cells: list[str] = []
        for cell in range(top, top + 3):
            side = game.at(cell)
            mark = " " if side is None else MARKS[side]
            if side is not None and not mono:
                mark = f"[$tama-piece-{side.value}]{mark}[/]"
            if cell in winning or cell == cursor:
                cells.append(highlight(f" {mark} ", mono=mono))
            else:
                cells.append(f" {mark} ")
        rows.append("[dim]│[/]".join(cells))
    return "\n[dim]───┼───┼───[/]\n".join(rows)


class TicTacToeScreen(BoardGameScreen[TicTacToe]):
    """Arrow keys and ``Enter``/``Space``, or ``1``-``9`` laid out like a keypad."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "move(-3)", "Up", show=False),
        Binding("down", "move(3)", "Down", show=False),
        Binding("left", "move(-1)", "Left", show=False),
        Binding("right", "move(1)", "Right", show=False),
        Binding("space", "place", "Place", show=False),
        *(Binding(str(key), f"keypad({key})", show=False) for key in KEYPAD),
    ]
    GAME_TITLE = "Tic-Tac-Toe"
    HINT = "Arrows + Enter, or 1-9 like a keypad · Esc give up"

    def __init__(self, session: GameSession, view: ViewOptions | None = None) -> None:
        """Start an empty board, with the cursor in the centre."""
        super().__init__(TicTacToe(), session, view)
        self.cursor = 4

    @override
    def board_markup(self) -> str:
        """The board, with the cursor only while it is the player's turn."""
        playing = self.game.result is None and not self.busy
        return tic_tac_toe_markup(self.game, self.cursor if playing else None, mono=self.mono)

    def action_move(self, step: int) -> None:
        """Move the cursor one cell, stopping at the edges of the board."""
        row, column = divmod(self.cursor, 3)
        if abs(step) == 3:
            row = min(2, max(0, row + step // 3))
        else:
            column = min(2, max(0, column + step))
        self.cursor = row * 3 + column
        self.redraw()

    def action_place(self) -> None:
        """Mark the cell under the cursor."""
        self.player_move(self.cursor)

    def action_keypad(self, key: int) -> None:
        """Mark the cell for number ``key`` (7 8 9 / 4 5 6 / 1 2 3)."""
        self.cursor = KEYPAD[key]
        self.player_move(self.cursor)

    @override
    def action_confirm(self) -> None:
        """Mark the cell under the cursor, or close the finished game."""
        if self.game.result is None:
            self.action_place()
        else:
            super().action_confirm()
