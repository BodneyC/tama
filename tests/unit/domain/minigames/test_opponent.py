from dataclasses import replace
from random import Random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tama.domain.balance import DEFAULT_BALANCE, Balance
from tama.domain.minigames import Side
from tama.domain.minigames.four_in_a_row import COLUMNS, ROWS, FourInARow
from tama.domain.minigames.opponent import BoardGame, pet_move
from tama.domain.minigames.tic_tac_toe import CELLS, TicTacToe
from tama.domain.stage import LifeStage
from tama.errors import GameOverError, IllegalMoveError

P, T = Side.PLAYER, Side.PET
_: Side | None = None
STAGES = [LifeStage.BABY, LifeStage.CHILD, LifeStage.TEEN, LifeStage.ADULT, LifeStage.ELDER]


def chances(chance: float) -> Balance:
    return replace(
        DEFAULT_BALANCE,
        baby_mistake_chance=chance,
        child_mistake_chance=chance,
        teen_mistake_chance=chance,
        adult_mistake_chance=chance,
        elder_mistake_chance=chance,
    )


SHARP = chances(0.0)
CLUMSY = chances(1.0)


def move(game: BoardGame, seed: int = 0, balance: Balance = SHARP) -> int:
    return pet_move(game, LifeStage.ADULT, balance, Random(seed))


def drops(*columns: int) -> FourInARow:
    game = FourInARow()
    for column in columns:
        game = game.drop(column)
    return game


# --- Four in a Row ------------------------------------------------------------------------


def test_takes_a_winning_drop() -> None:
    game = drops(0, 6, 0, 6, 1, 6, 5)  # the pet has three up column 6

    assert move(game) == 6


def test_blocks_the_players_four() -> None:
    game = drops(0, 6, 1, 6, 2)  # the player threatens column 3

    assert move(game) == 3


def test_winning_beats_blocking() -> None:
    game = drops(0, 6, 1, 6, 2, 6, 5)  # both sides threaten; the pet moves

    # The player threatens column 3 and the pet threatens column 6: the pet takes its win.
    assert move(game) == 6


def test_wont_drop_where_the_player_can_win_on_top() -> None:
    # The player has (1,1), (2,1) and (4,1): dropping into column 3 would let them win at (3,1).
    game = FourInARow(((), (T, P), (P, P), (), (T, P), (), (T,)))
    assert game.to_move is T

    for seed in range(20):
        assert move(game, seed) != 3


def test_prefers_the_centre_column() -> None:
    assert {move(drops(0), seed) for seed in range(20)} == {3}


def test_ties_are_broken_at_random() -> None:
    # Column 3 is full, so columns 2 and 4 are equally good.
    game = drops(3, 3, 3, 3, 3, 3, 0)

    assert {move(game, seed) for seed in range(30)} == {2, 4}


def test_a_mistake_is_any_legal_move() -> None:
    game = drops(0, 6, 1, 6, 2)

    assert {move(game, seed, CLUMSY) for seed in range(80)} == set(range(COLUMNS))


def test_mistakes_follow_the_stage() -> None:
    game = drops(0, 6, 1, 6, 2)
    balance = replace(SHARP, baby_mistake_chance=1.0)

    baby = {pet_move(game, LifeStage.BABY, balance, Random(s)) for s in range(80)}
    adult = {pet_move(game, LifeStage.ADULT, balance, Random(s)) for s in range(80)}

    assert len(baby) > 1
    assert adult == {3}


def test_the_same_seed_gives_the_same_move() -> None:
    game = drops(3)

    assert move(game, 5, DEFAULT_BALANCE) == move(game, 5, DEFAULT_BALANCE)


def test_refuses_to_move_out_of_turn() -> None:
    with pytest.raises(IllegalMoveError, match="turn"):
        move(FourInARow())


def test_refuses_to_move_once_the_game_is_over() -> None:
    game = drops(0, 6, 1, 6, 2, 5, 3)

    with pytest.raises(GameOverError):
        move(game)


# --- Playing the player's side (pet vs pet, SPEC §3.2) -----------------------------------


def host_move(game: BoardGame, seed: int = 0, balance: Balance = SHARP) -> int:
    return pet_move(game, LifeStage.ADULT, balance, Random(seed), side=P)


def test_can_open_the_game_as_the_first_player() -> None:
    assert {host_move(FourInARow(), seed) for seed in range(20)} == {3}


def test_playing_first_it_takes_its_own_win() -> None:
    game = drops(0, 6, 0, 6, 0, 5)  # the first player has three up column 0

    assert host_move(game) == 0


def test_playing_first_it_blocks_the_other_pet() -> None:
    game = drops(0, 6, 1, 6, 5, 6)  # the second player threatens the top of column 6

    assert host_move(game) == 6


def test_playing_first_it_wont_hand_the_other_side_a_win() -> None:
    # The second player has (1,1), (2,1) and (4,1); a drop into column 3 lets them win at (3,1).
    game = FourInARow(((P,), (P, T), (T, T), (), (P, T), (P,), ()))
    assert game.to_move is P

    for seed in range(20):
        assert host_move(game, seed) != 3


def test_refuses_to_move_for_the_side_not_on_turn() -> None:
    with pytest.raises(IllegalMoveError, match="turn"):
        host_move(drops(3))


def test_tic_tac_toe_as_the_first_player_takes_the_centre() -> None:
    assert host_move(TicTacToe()) == 4


# --- Tic-Tac-Toe --------------------------------------------------------------------------


def test_tic_tac_toe_takes_a_win() -> None:
    game = TicTacToe((P, P, _, T, T, _, P, _, _))

    assert move(game) == 5


def test_tic_tac_toe_blocks() -> None:
    game = TicTacToe((P, P, _, _, T, _, _, _, _))

    assert move(game) == 2


def test_tic_tac_toe_takes_the_centre_first() -> None:
    assert move(TicTacToe().place(0)) == 4


def test_tic_tac_toe_answers_the_centre_with_a_corner() -> None:
    corners = {move(TicTacToe().place(4), seed) for seed in range(40)}

    assert corners == {0, 2, 6, 8}


# --- Properties ---------------------------------------------------------------------------


def new_game(kind: int) -> FourInARow | TicTacToe:
    return FourInARow() if kind == 0 else TicTacToe()


def size(game: FourInARow | TicTacToe) -> int:
    return COLUMNS * ROWS if isinstance(game, FourInARow) else CELLS


@settings(deadline=None)
@given(
    st.sampled_from([0, 1]),
    st.sampled_from(STAGES),
    st.floats(min_value=0, max_value=1),
    st.randoms(use_true_random=False),
)
def test_games_against_the_pet_always_finish_legally(
    kind: int, stage: LifeStage, chance: float, player: Random
) -> None:
    game = new_game(kind)
    rng = Random(player.random())
    moves = 0
    while game.result is None:
        legal = game.legal_moves()
        if game.to_move is P:
            choice = player.choice(legal)
        else:
            choice = pet_move(game, stage, chances(chance), rng)
            assert choice in legal
        game = game.play(choice)
        moves += 1

    assert moves <= size(game)
    assert game.legal_moves() == ()
    assert (game.winner is None) == (game.line == ())


@settings(deadline=None)
@given(st.sampled_from([0, 1]), st.randoms(use_true_random=False))
def test_without_mistakes_the_pet_never_misses_a_win_or_a_block(kind: int, rng: Random) -> None:
    game = new_game(kind)
    while game.result is None:
        legal = game.legal_moves()
        if game.to_move is P:
            game = game.play(rng.choice(legal))
            continue
        wins = [m for m in legal if game.wins_with(m, T)]
        blocks = [m for m in legal if game.wins_with(m, P)]
        choice = pet_move(game, LifeStage.ADULT, SHARP, rng)
        if wins:
            assert choice in wins
        elif blocks:
            assert choice in blocks
        game = game.play(choice)
