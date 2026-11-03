"""Tic-Tac-Toe: a 3×3 board played against the pet (SPEC §3.1)."""

from dataclasses import dataclass
from typing import Self

from tama.domain.minigames import GameResult, Side, result_for
from tama.errors import GameOverError, IllegalMoveError

CELLS = 9
"""Cells are numbered 0-8 in reading order: 0 is top-left, 8 bottom-right."""

LINES: tuple[tuple[int, int, int], ...] = (
    (0, 1, 2),
    (3, 4, 5),
    (6, 7, 8),
    (0, 3, 6),
    (1, 4, 7),
    (2, 5, 8),
    (0, 4, 8),
    (2, 4, 6),
)

_CENTRE = 4
_CORNERS = frozenset({0, 2, 6, 8})


@dataclass(frozen=True, slots=True)
class TicTacToe:
    """An immutable board. Whose turn it is follows from the counts: the player moves first."""

    cells: tuple[Side | None, ...] = (None,) * CELLS
    last: int | None = None
    """The most recently marked cell, if any."""

    def __post_init__(self) -> None:
        """Reject boards that can't exist."""
        if len(self.cells) != CELLS:
            raise IllegalMoveError(f"a board has {CELLS} cells, not {len(self.cells)}")

    def at(self, cell: int) -> Side | None:
        """The mark in ``cell``, or ``None`` if it is empty."""
        return self.cells[cell]

    @property
    def to_move(self) -> Side:
        """Whose turn it is."""
        placed = sum(mark is not None for mark in self.cells)
        return Side.PLAYER if placed % 2 == 0 else Side.PET

    @property
    def is_full(self) -> bool:
        """Whether every cell is taken."""
        return None not in self.cells

    @property
    def line(self) -> tuple[int, ...]:
        """The winning three, or ``()`` if nobody has won."""
        for a, b, c in LINES:
            if self.cells[a] is not None and self.cells[a] is self.cells[b] is self.cells[c]:
                return (a, b, c)
        return ()

    @property
    def winner(self) -> Side | None:
        """Who made three in a row, if anyone."""
        line = self.line
        return self.cells[line[0]] if line else None

    @property
    def result(self) -> GameResult | None:
        """How the game went for the player, once it is over."""
        return result_for(self.winner, full=self.is_full)

    def legal_moves(self) -> tuple[int, ...]:
        """The empty cells (none once the game is over)."""
        if self.result is not None:
            return ()
        return tuple(cell for cell in range(CELLS) if self.cells[cell] is None)

    def place(self, cell: int) -> Self:
        """Put the next mark in ``cell``.

        Raises:
            GameOverError: If the game has already finished.
            IllegalMoveError: If the cell is off the board or taken.
        """
        if self.result is not None:
            raise GameOverError("the game is already over")
        return self._with(cell, self.to_move)

    def play(self, move: int) -> Self:
        """Same as ``place``: the move shape shared by every board game."""
        return self.place(move)

    def wins_with(self, cell: int, side: Side) -> bool:
        """Whether ``side`` would make three by marking ``cell`` now."""
        return self._with(cell, side).winner is side

    def preference(self, cell: int) -> int:
        """How the pet ranks ``cell`` when nothing else decides: centre, corners, edges."""
        if cell == _CENTRE:
            return 0
        return 1 if cell in _CORNERS else 2

    def _with(self, cell: int, side: Side) -> Self:
        if not 0 <= cell < CELLS:
            raise IllegalMoveError(f"no cell {cell}: cells are 0-{CELLS - 1}")
        if self.cells[cell] is not None:
            raise IllegalMoveError(f"cell {cell} is taken")
        return type(self)((*self.cells[:cell], side, *self.cells[cell + 1 :]), cell)
