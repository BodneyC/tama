"""Four in a Row against the pet (SPEC §3.1)."""

from collections.abc import Callable
from typing import ClassVar, override

from textual.binding import Binding, BindingType

from tama.domain.minigames import Side
from tama.domain.minigames.four_in_a_row import COLUMNS, ROWS, Cell, FourInARow
from tama.services.session import GameSession
from tama.ui.screens.games.board import BoardGameScreen, highlight, piece_markup
from tama.ui.widgets.pet_view import ViewOptions

FALL_SECONDS = 0.04
"""How long a falling piece spends in each row (skipped with reduced motion)."""

type Ghost = tuple[Cell, Side]
"""A piece drawn on top of the board while it falls."""


def four_in_a_row_markup(
    game: FourInARow, cursor: int | None, *, mono: bool, ghost: Ghost | None = None
) -> str:
    """The board as content markup, with the drop marker above ``cursor`` (if any).

    The winning four are highlighted (reversed in monochrome).
    """
    marker = "".join(
        (" ▼ " if mono else " [$tama-piece-player]▼[/] ") if column == cursor else "   "
        for column in range(COLUMNS)
    )
    winning = set(game.line)
    lines = [f" {marker} ", "╭" + "─" * (3 * COLUMNS) + "╮"]
    for row in reversed(range(ROWS)):
        cells: list[str] = []
        for column in range(COLUMNS):
            side = game.at(column, row)
            if ghost is not None and ghost[0] == (column, row):
                side = ghost[1]
            if side is None:
                cells.append(" [dim]·[/] ")
            elif (column, row) in winning:
                cells.append(highlight(f" {piece_markup(side, mono=mono)} ", mono=mono))
            else:
                cells.append(f" {piece_markup(side, mono=mono)} ")
        lines.append("│" + "".join(cells) + "│")
    lines.append("╰" + "─" * (3 * COLUMNS) + "╯")
    return "\n".join(lines)


class FourInARowScreen(BoardGameScreen[FourInARow]):
    """``←``/``→`` choose a column, ``↓`` or ``Enter`` drop a piece."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("left", "move(-1)", "Left"),
        Binding("right", "move(1)", "Right"),
        Binding("down", "drop", "Drop"),
    ]
    GAME_TITLE = "Four in a Row"
    HINT = "←→ choose a column · ↓ or Enter drop · Esc give up"

    def __init__(self, session: GameSession, view: ViewOptions | None = None) -> None:
        """Start an empty board, with the marker over the centre column."""
        super().__init__(FourInARow(), session, view)
        self.cursor = COLUMNS // 2
        self.ghost: Ghost | None = None

    @override
    def board_markup(self) -> str:
        """The board, with the marker only while it is the player's turn."""
        playing = self.game.result is None and not self.busy
        cursor = self.cursor if playing else None
        return four_in_a_row_markup(self.game, cursor, mono=self.mono, ghost=self.ghost)

    def action_move(self, step: int) -> None:
        """Move the marker to the next column that isn't full, wrapping at the edges."""
        if self.busy or self.game.result is not None:
            return
        for i in range(1, COLUMNS + 1):
            column = (self.cursor + i * step) % COLUMNS
            if len(self.game.columns[column]) < ROWS:
                self.cursor = column
                break
        self.redraw()

    def action_drop(self) -> None:
        """Drop a piece in the marked column."""
        self.player_move(self.cursor)

    @override
    def action_confirm(self) -> None:
        """Drop a piece, or close the finished game."""
        if self.game.result is None:
            self.action_drop()
        else:
            super().action_confirm()

    @override
    def player_turn_started(self) -> None:
        """Move the marker off a column the pet just filled."""
        if len(self.game.columns[self.cursor]) == ROWS:
            self.action_move(1)

    @override
    def animate_move(self, after: FourInARow, done: Callable[[], None]) -> None:
        """Let the new piece fall row by row to where it lands."""
        side = None if after.last is None else after.at(*after.last)
        if not self.animated or after.last is None or side is None:
            super().animate_move(after, done)
            return
        column, landing = after.last

        def fall(row: int) -> None:
            if row < landing:
                self.ghost = None
                super(FourInARowScreen, self).animate_move(after, done)
                return
            self.ghost = ((column, row), side)
            self.redraw()
            self.set_timer(FALL_SECONDS, lambda: fall(row - 1))

        fall(ROWS - 1)
