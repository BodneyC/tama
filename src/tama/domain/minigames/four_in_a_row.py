"""Four in a Row: a 7×6 connect-four style board played against the pet (SPEC §3.1)."""

from dataclasses import dataclass
from typing import Self

from tama.domain.minigames import GameResult, Side, result_for
from tama.errors import GameOverError, IllegalMoveError

COLUMNS = 7
ROWS = 6
CENTRE = COLUMNS // 2

type Cell = tuple[int, int]
"""``(column, row)``, with row 0 at the bottom."""


def _lines() -> tuple[tuple[Cell, ...], ...]:
    lines: list[tuple[Cell, ...]] = []
    for column in range(COLUMNS):
        for row in range(ROWS):
            for dc, dr in ((1, 0), (0, 1), (1, 1), (1, -1)):
                cells = tuple((column + i * dc, row + i * dr) for i in range(4))
                if all(0 <= c < COLUMNS and 0 <= r < ROWS for c, r in cells):
                    lines.append(cells)
    return tuple(lines)


LINES = _lines()
"""Every run of four cells on the board (69 of them)."""
LINES_THROUGH: dict[Cell, tuple[tuple[Cell, ...], ...]] = {
    (column, row): tuple(line for line in LINES if (column, row) in line)
    for column in range(COLUMNS)
    for row in range(ROWS)
}
"""The runs of four that pass through each cell, so a move only checks its own lines."""


@dataclass(frozen=True, slots=True)
class FourInARow:
    """An immutable board. ``columns[c]`` holds that column's pieces from the bottom up.

    Whose turn it is follows from the piece counts: the player moves first.
    """

    columns: tuple[tuple[Side, ...], ...] = ((),) * COLUMNS
    last: Cell | None = None
    """The cell of the most recent drop, if any."""

    def __post_init__(self) -> None:
        """Reject boards that can't exist."""
        if len(self.columns) != COLUMNS or any(len(c) > ROWS for c in self.columns):
            raise IllegalMoveError(f"a board has {COLUMNS} columns of at most {ROWS} pieces")

    def at(self, column: int, row: int) -> Side | None:
        """The piece at ``(column, row)``, or ``None`` if the cell is empty."""
        pieces = self.columns[column]
        return pieces[row] if row < len(pieces) else None

    @property
    def to_move(self) -> Side:
        """Whose turn it is."""
        placed = sum(len(column) for column in self.columns)
        return Side.PLAYER if placed % 2 == 0 else Side.PET

    @property
    def is_full(self) -> bool:
        """Whether every cell is taken."""
        return all(len(column) == ROWS for column in self.columns)

    @property
    def line(self) -> tuple[Cell, ...]:
        """The winning four, or ``()`` if nobody has won."""
        for cells in LINES:
            first = self.at(*cells[0])
            if first is not None and all(self.at(*cell) is first for cell in cells[1:]):
                return cells
        return ()

    @property
    def winner(self) -> Side | None:
        """Who made four in a row, if anyone."""
        line = self.line
        return self.at(*line[0]) if line else None

    @property
    def result(self) -> GameResult | None:
        """How the game went for the player, once it is over."""
        return result_for(self.winner, full=self.is_full)

    def legal_moves(self) -> tuple[int, ...]:
        """The columns that can be played (none once the game is over)."""
        if self.result is not None:
            return ()
        return tuple(c for c in range(COLUMNS) if len(self.columns[c]) < ROWS)

    def drop(self, column: int) -> Self:
        """Drop the next piece into ``column``; it falls to the lowest empty cell.

        Raises:
            GameOverError: If the game has already finished.
            IllegalMoveError: If the column is off the board or full.
        """
        if self.result is not None:
            raise GameOverError("the game is already over")
        return self._with(column, self.to_move)

    def play(self, move: int) -> Self:
        """Same as ``drop``: the move shape shared by every board game."""
        return self.drop(move)

    def wins_with(self, column: int, side: Side) -> bool:
        """Whether ``side`` would make four by dropping into ``column`` now."""
        after = self._with(column, side)
        cell = (column, len(self.columns[column]))
        return any(all(after.at(*other) is side for other in line) for line in LINES_THROUGH[cell])

    def preference(self, column: int) -> int:
        """How the pet ranks ``column`` when nothing else decides: lower is better."""
        return abs(column - CENTRE)

    def _with(self, column: int, side: Side) -> Self:
        if not 0 <= column < COLUMNS:
            raise IllegalMoveError(f"no column {column}: columns are 0-{COLUMNS - 1}")
        pieces = self.columns[column]
        if len(pieces) == ROWS:
            raise IllegalMoveError(f"column {column} is full")
        columns = (*self.columns[:column], (*pieces, side), *self.columns[column + 1 :])
        return type(self)(columns, (column, len(pieces)))
