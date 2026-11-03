import pytest

from tama.domain.minigames import GameResult, Side
from tama.domain.minigames.tic_tac_toe import CELLS, TicTacToe
from tama.errors import GameOverError, IllegalMoveError

P, T = Side.PLAYER, Side.PET
_: Side | None = None


def play(*cells: int) -> TicTacToe:
    game = TicTacToe()
    for cell in cells:
        game = game.place(cell)
    return game


def test_new_board_is_empty_and_the_player_starts() -> None:
    game = TicTacToe()

    assert CELLS == 9
    assert game.to_move is P
    assert game.legal_moves() == tuple(range(9))
    assert game.result is None
    assert game.line == ()


def test_marks_alternate() -> None:
    game = play(4, 0)

    assert game.at(4) is P
    assert game.at(0) is T
    assert game.to_move is P
    assert game.legal_moves() == (1, 2, 3, 5, 6, 7, 8)
    assert game.last == 0


def test_occupied_cells_cannot_be_played() -> None:
    with pytest.raises(IllegalMoveError, match="taken"):
        play(4).place(4)


@pytest.mark.parametrize("cell", [-1, CELLS])
def test_cells_off_the_board_are_rejected(cell: int) -> None:
    with pytest.raises(IllegalMoveError, match="cell"):
        TicTacToe().place(cell)


@pytest.mark.parametrize(
    "line",
    [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)],
)
def test_three_in_a_row_wins_on_all_eight_lines(line: tuple[int, int, int]) -> None:
    others = [cell for cell in range(9) if cell not in line]
    cells: list[Side | None] = [None] * 9
    for cell in line:
        cells[cell] = P
    # Two pet marks that don't make a line of their own, so the counts are legal.
    placed = 0
    for cell in others:
        if placed < 2:
            cells[cell] = T
            placed += 1
    game = TicTacToe(tuple(cells))

    assert game.line == line
    assert game.winner is P
    assert game.result is GameResult.WIN
    assert game.legal_moves() == ()


def test_the_pet_winning_is_a_loss() -> None:
    game = TicTacToe((T, T, T, P, P, _, P, _, _))

    assert game.result is GameResult.LOSS


def test_a_full_board_without_a_line_is_a_draw() -> None:
    game = TicTacToe((P, T, P, P, T, T, T, P, P))

    assert game.is_full
    assert game.result is GameResult.DRAW


def test_no_moves_after_the_game_is_over() -> None:
    with pytest.raises(GameOverError):
        play(0, 3, 1, 4, 2).place(8)


def test_wins_with_checks_a_move_without_playing_it() -> None:
    game = play(0, 3, 1, 4)

    assert game.wins_with(2, P)
    assert game.wins_with(5, T)
    assert not game.wins_with(8, P)


def test_impossible_boards_are_rejected() -> None:
    with pytest.raises(IllegalMoveError, match="board"):
        TicTacToe((None,) * 8)
