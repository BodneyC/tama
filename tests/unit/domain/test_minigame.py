from random import Random

import pytest

from tama.domain.minigame import Direction, LeftRightGame, RoundResult
from tama.errors import GameOverError, InvalidArgumentError, TamaError


def play_all(game: LeftRightGame, guesses: list[Direction], seed: int = 0) -> LeftRightGame:
    rng = Random(seed)
    for guess in guesses:
        game = game.guess(guess, rng)
    return game


def test_new_game_has_five_rounds_and_needs_three_wins() -> None:
    game = LeftRightGame()

    assert game.rounds == 5
    assert game.wins_needed == 3
    assert game.round_number == 1
    assert not game.is_over
    assert not game.won
    assert game.last_result is None


def test_guess_records_a_round() -> None:
    game = LeftRightGame().guess(Direction.LEFT, Random(0))

    assert len(game.results) == 1
    assert game.round_number == 2
    assert game.last_result is not None
    assert game.last_result.guess is Direction.LEFT


@pytest.mark.parametrize(
    ("guess", "looked", "correct"),
    [
        (Direction.LEFT, Direction.LEFT, True),
        (Direction.LEFT, Direction.RIGHT, False),
    ],
)
def test_round_is_correct_when_guess_matches(
    guess: Direction, looked: Direction, correct: bool
) -> None:
    assert RoundResult(guess, looked).correct is correct


def test_game_is_deterministic_for_a_seed() -> None:
    guesses = [Direction.LEFT] * 5

    assert play_all(LeftRightGame(), guesses, seed=1) == play_all(LeftRightGame(), guesses, seed=1)


def test_pet_direction_comes_from_rng() -> None:
    looked = {
        play_all(LeftRightGame(), [Direction.LEFT], seed=s).results[0].pet_looked for s in range(20)
    }

    assert looked == set(Direction)


def test_game_ends_after_all_rounds() -> None:
    game = play_all(LeftRightGame(), [Direction.LEFT] * 5)

    assert game.is_over
    assert game.round_number == 5


def test_winning_needs_enough_correct_guesses() -> None:
    rounds = (RoundResult(Direction.LEFT, Direction.LEFT),) * 3 + (
        RoundResult(Direction.LEFT, Direction.RIGHT),
    ) * 2
    lost_rounds = (RoundResult(Direction.LEFT, Direction.LEFT),) * 2 + (
        RoundResult(Direction.LEFT, Direction.RIGHT),
    ) * 3

    assert LeftRightGame(results=rounds).won
    assert LeftRightGame(results=rounds).wins == 3
    assert not LeftRightGame(results=lost_rounds).won


def test_cannot_guess_after_game_over() -> None:
    game = play_all(LeftRightGame(), [Direction.RIGHT] * 5)

    with pytest.raises(GameOverError):
        game.guess(Direction.LEFT, Random(0))
    assert issubclass(GameOverError, TamaError)


@pytest.mark.parametrize(("rounds", "wins_needed"), [(0, 0), (3, 0), (3, 4)])
def test_invalid_game_settings_rejected(rounds: int, wins_needed: int) -> None:
    with pytest.raises(InvalidArgumentError):
        LeftRightGame(rounds=rounds, wins_needed=wins_needed)
