import pytest

from tama.domain.minigames import GameResult, Side
from tama.domain.minigames.four_in_a_row import COLUMNS, ROWS, FourInARow
from tama.errors import GameOverError, IllegalMoveError, TamaError

P, T = Side.PLAYER, Side.PET


def play(*columns: int) -> FourInARow:
    game = FourInARow()
    for column in columns:
        game = game.drop(column)
    return game


def test_new_board_is_empty_and_the_player_starts() -> None:
    game = FourInARow()

    assert (COLUMNS, ROWS) == (7, 6)
    assert game.to_move is P
    assert game.legal_moves() == tuple(range(COLUMNS))
    assert all(game.at(c, r) is None for c in range(COLUMNS) for r in range(ROWS))
    assert game.result is None
    assert game.line == ()


def test_pieces_fall_to_the_lowest_empty_cell_and_turns_alternate() -> None:
    game = play(3, 3, 4)

    assert game.at(3, 0) is P
    assert game.at(3, 1) is T
    assert game.at(4, 0) is P
    assert game.at(4, 1) is None
    assert game.to_move is T
    assert game.last == (4, 0)


def test_full_columns_cannot_be_played() -> None:
    game = play(*[0] * ROWS)

    assert 0 not in game.legal_moves()
    with pytest.raises(IllegalMoveError, match="full"):
        game.drop(0)
    assert issubclass(IllegalMoveError, TamaError)


@pytest.mark.parametrize("column", [-1, COLUMNS])
def test_columns_off_the_board_are_rejected(column: int) -> None:
    with pytest.raises(IllegalMoveError, match="column"):
        FourInARow().drop(column)


@pytest.mark.parametrize(
    ("columns", "line"),
    [
        # Horizontal along the bottom.
        (((P,), (P,), (P,), (P,), (T, T), (T,), ()), ((0, 0), (1, 0), (2, 0), (3, 0))),
        # Vertical.
        (((T, T, T), (P, P, P, P), (), (), (), (), ()), ((1, 0), (1, 1), (1, 2), (1, 3))),
        # Diagonal, rising to the right.
        (
            ((P,), (T, P), (T, T, P), (T, P, T, P), (), (), ()),
            ((0, 0), (1, 1), (2, 2), (3, 3)),
        ),
        # Diagonal, falling to the right.
        (
            ((), (), (), (T, P, T, P), (T, T, P), (T, P), (P,)),
            ((3, 3), (4, 2), (5, 1), (6, 0)),
        ),
    ],
    ids=["horizontal", "vertical", "rising", "falling"],
)
def test_four_in_a_row_wins_in_every_direction(
    columns: tuple[tuple[Side, ...], ...], line: tuple[tuple[int, int], ...]
) -> None:
    game = FourInARow(columns)

    assert game.result is GameResult.WIN
    assert game.winner is P
    assert sorted(game.line) == sorted(line)
    assert game.legal_moves() == ()


def test_the_pet_winning_is_a_loss() -> None:
    game = play(0, 6, 0, 6, 1, 6, 2, 6)

    assert game.winner is T
    assert game.result is GameResult.LOSS


def test_no_moves_after_the_game_is_over() -> None:
    game = play(0, 6, 1, 6, 2, 6, 3)

    with pytest.raises(GameOverError):
        game.drop(5)


def test_a_full_board_without_four_is_a_draw() -> None:
    a = (P, T, P, T, P, T)
    b = (T, P, T, P, T, P)
    # Shifting pairs of columns stops every horizontal and diagonal four.
    game = FourInARow((a, a, b, b, a, a, b))

    assert game.is_full
    assert game.line == ()
    assert game.result is GameResult.DRAW
    assert game.legal_moves() == ()


def test_wins_with_checks_a_move_without_playing_it() -> None:
    game = play(0, 6, 1, 6, 2, 6)

    assert game.wins_with(3, P)
    assert game.wins_with(6, T)
    assert not game.wins_with(4, T)
    assert game.to_move is P
    assert game.at(3, 0) is None


@pytest.mark.parametrize(
    "columns",
    [((),) * 6, ((),) * 8, ((P,) * 7, (), (), (), (), (), ())],
    ids=["too-few-columns", "too-many-columns", "column-too-tall"],
)
def test_impossible_boards_are_rejected(columns: tuple[tuple[Side, ...], ...]) -> None:
    with pytest.raises(IllegalMoveError, match="board"):
        FourInARow(columns)
