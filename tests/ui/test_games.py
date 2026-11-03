"""The mini-games from the main screen: choosing, playing and their effect on the pet."""

import pytest

from tama.domain.animation import AnimationKey
from tama.domain.minigames import GameKind, GameResult, Side
from tama.domain.minigames.four_in_a_row import COLUMNS, ROWS, FourInARow
from tama.domain.minigames.tic_tac_toe import TicTacToe
from tama.domain.stage import LifeStage, Variant
from tama.domain.stats import Stats
from tama.ui.app import TamaApp
from tama.ui.screens.games import board
from tama.ui.screens.games import four_in_a_row as four_screen
from tama.ui.screens.games.four_in_a_row import FourInARowScreen, four_in_a_row_markup
from tama.ui.screens.games.left_right import LeftRightScreen
from tama.ui.screens.games.select import GameSelectScreen
from tama.ui.screens.games.tic_tac_toe import TicTacToeScreen, tic_tac_toe_markup
from tama.ui.screens.main import MainScreen
from tama.ui.sprites import load_sprite
from tama.ui.widgets.pet_view import PetView, ViewOptions
from tests.ui.helpers import make_app, repo_with, text

P, T = Side.PLAYER, Side.PET
EFFECT = {GameResult.WIN: 70, GameResult.DRAW: 60, GameResult.LOSS: 55}
"""Happiness after a game, starting from 50."""


def playful() -> TamaApp:
    return make_app(repo_with(stats=Stats(happiness=50, energy=50)))


# --- Choosing a game ----------------------------------------------------------------------


async def test_p_opens_the_game_select_and_escape_closes_it() -> None:
    app = playful()
    async with app.run_test() as pilot:
        await pilot.press("p")
        assert isinstance(app.screen, GameSelectScreen)

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, MainScreen)
        assert app.session is not None
        assert app.session.pet.stats.happiness == 50


@pytest.mark.parametrize(
    ("keys", "screen_type"),
    [
        (["1"], LeftRightScreen),
        (["2"], FourInARowScreen),
        (["3"], TicTacToeScreen),
        (["enter"], LeftRightScreen),
        (["down", "enter"], FourInARowScreen),
        (["down", "down", "enter"], TicTacToeScreen),
    ],
)
async def test_choosing_a_game(keys: list[str], screen_type: type) -> None:
    app = playful()
    async with app.run_test() as pilot:
        await pilot.press("p", *keys)
        await pilot.pause()

        assert isinstance(app.screen, screen_type)


async def test_the_last_game_is_preselected() -> None:
    app = playful()
    async with app.run_test() as pilot:
        await pilot.press("p", "3", "escape", "p")
        await pilot.pause()

        assert isinstance(app.screen, GameSelectScreen)
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, TicTacToeScreen)
        assert isinstance(app.screen_stack[1], MainScreen)
        assert app.screen_stack[1].last_game is GameKind.TIC_TAC_TOE


# --- Left or Right ------------------------------------------------------------------------


async def test_playing_the_mini_game() -> None:
    app = make_app(repo_with(stats=Stats(happiness=50, energy=50)))
    async with app.run_test() as pilot:
        await pilot.press("p", "1", "1")
        assert isinstance(app.screen, LeftRightScreen)
        game_screen = app.screen

        await pilot.press("left", "right", "left", "right", "left")
        assert game_screen.game.is_over
        won = game_screen.game.result is GameResult.WIN
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, MainScreen)
        assert app.session is not None
        assert app.session.pet.stats.happiness == (70 if won else 55)
        assert app.session.pet.stats.energy == 40


async def test_the_pet_turns_the_way_it_looked() -> None:
    app = make_app(repo_with(species="owl"))
    async with app.run_test() as pilot:
        await pilot.press("p", "1", "1")
        game_screen = app.screen
        assert isinstance(game_screen, LeftRightScreen)
        pet_view = game_screen.query_one(PetView)
        idle = load_sprite("owl", Variant.DEFAULT, LifeStage.CHILD, AnimationKey.IDLE)
        assert pet_view.current == idle

        await pilot.press("left")

        last = game_screen.game.last_result
        assert last is not None
        key = AnimationKey(f"look_{last.pet_looked.value}")
        assert pet_view.current == load_sprite("owl", Variant.DEFAULT, LifeStage.CHILD, key)


async def test_enter_does_nothing_until_the_game_is_over() -> None:
    app = make_app(repo_with())
    async with app.run_test() as pilot:
        await pilot.press("p", "1", "left", "enter")

        assert isinstance(app.screen, LeftRightScreen)
        assert len(app.screen.game.results) == 1
        assert "Round 2/5" in text(app, "#game-body")


async def test_giving_up_the_game_changes_nothing() -> None:
    app = make_app(repo_with(stats=Stats(happiness=50)))
    async with app.run_test() as pilot:
        await pilot.press("p", "1", "left", "escape")
        await pilot.pause()

        assert isinstance(app.screen, MainScreen)
        assert app.session is not None
        assert app.session.pet.stats.happiness == 50


async def test_guessing_after_game_over_is_ignored() -> None:
    app = make_app(repo_with())
    async with app.run_test() as pilot:
        await pilot.press("p", "1", *["left"] * 5)
        screen = app.screen
        assert isinstance(screen, LeftRightScreen)
        finished = screen.game

        await pilot.press("right")

        assert screen.game is finished


# --- Four in a Row ------------------------------------------------------------------------


async def test_four_in_a_row_drop_and_the_pets_reply() -> None:
    app = playful()
    async with app.run_test() as pilot:
        await pilot.press("p", "2", "down")
        screen = app.screen
        assert isinstance(screen, FourInARowScreen)

        assert screen.game.at(3, 0) is P
        assert sum(len(column) for column in screen.game.columns) == 2
        assert screen.game.to_move is P
        assert "Your move." in text(app, "#game-status")


async def test_four_in_a_row_marker_wraps_and_skips_full_columns() -> None:
    app = playful()
    async with app.run_test() as pilot:
        await pilot.press("p", "2")
        screen = app.screen
        assert isinstance(screen, FourInARowScreen)
        full = ((P, T) * 3,)
        screen.show(FourInARow(((),) * 6 + full))

        await pilot.press("right", "right", "right")
        assert screen.cursor == 0  # 4, 5, then past the full column 6 to 0

        await pilot.press("left")
        assert screen.cursor == 5


async def test_four_in_a_row_played_to_the_end_with_the_keyboard() -> None:
    app = playful()
    async with app.run_test() as pilot:
        await pilot.press("p", "2")
        screen = app.screen
        assert isinstance(screen, FourInARowScreen)
        for _ in range(COLUMNS * ROWS):
            if screen.game.result is not None:
                break
            await pilot.press("down")
        result = screen.game.result
        assert result is not None
        assert "Press Enter" in text(app, "#game-status")

        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, MainScreen)
        assert app.session is not None
        assert app.session.pet.stats.happiness == EFFECT[result]
        assert app.session.pet.stats.energy == 40


async def test_the_pet_cheers_when_you_win() -> None:
    app = playful()
    async with app.run_test() as pilot:
        await pilot.press("p", "2")
        screen = app.screen
        assert isinstance(screen, FourInARowScreen)

        screen.show(FourInARow(((P,), (P,), (P,), (P,), (T,), (T,), (T,))))

        assert "You won!" in text(app, "#game-status")
        happy = load_sprite("tama", Variant.DEFAULT, LifeStage.CHILD, AnimationKey.HAPPY)
        assert screen.query_one(PetView).current == happy


def settled(screen: FourInARowScreen) -> bool:
    # A function call, so the type checker doesn't keep ``busy`` narrowed to True.
    return not screen.busy


async def test_four_in_a_row_thinks_and_drops_with_motion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(board, "THINK_SECONDS", 0.5)
    monkeypatch.setattr(four_screen, "FALL_SECONDS", 0.01)
    app = make_app(repo_with(), view=ViewOptions(animate=True))
    async with app.run_test() as pilot:
        await pilot.press("p", "2", "down")
        screen = app.screen
        assert isinstance(screen, FourInARowScreen)
        assert screen.busy
        assert "is thinking" in text(app, "#game-status")
        await pilot.press("left", "down")  # ignored while busy
        assert screen.cursor == 3
        assert sum(len(column) for column in screen.game.columns) == 1

        for _ in range(100):
            await pilot.pause(0.02)
            if settled(screen):
                break

        assert sum(len(column) for column in screen.game.columns) == 2
        assert screen.ghost is None


async def test_reduced_motion_answers_at_once() -> None:
    app = make_app(repo_with(), view=ViewOptions(animate=True, reduced_motion=True))
    async with app.run_test() as pilot:
        await pilot.press("p", "2", "down")
        screen = app.screen
        assert isinstance(screen, FourInARowScreen)

        assert not screen.busy
        assert sum(len(column) for column in screen.game.columns) == 2


def test_four_in_a_row_markup_shapes_in_monochrome() -> None:
    game = FourInARow().drop(0).drop(1)

    mono = four_in_a_row_markup(game, 2, mono=True)
    colour = four_in_a_row_markup(game, 2, mono=False)

    assert "●" in mono
    assert "○" in mono
    assert "$tama" not in mono
    assert "[$tama-piece-player]●[/]" in colour
    assert "[$tama-piece-pet]●[/]" in colour
    assert mono.splitlines()[0].index("▼") == 1 + 3 * 2 + 1


def test_four_in_a_row_markup_highlights_the_winning_four() -> None:
    game = FourInARow(((P,), (P,), (P,), (P,), (T,), (T,), (T,)))

    assert four_in_a_row_markup(game, None, mono=True).count("[reverse]") == 4
    assert four_in_a_row_markup(game, None, mono=False).count("on $foreground") == 4


# --- Tic-Tac-Toe --------------------------------------------------------------------------


@pytest.mark.parametrize(("key", "cell"), [("7", 0), ("5", 4), ("3", 8), ("1", 6)])
async def test_tic_tac_toe_number_keys_are_a_keypad(key: str, cell: int) -> None:
    app = playful()
    async with app.run_test() as pilot:
        await pilot.press("p", "3", key)
        screen = app.screen
        assert isinstance(screen, TicTacToeScreen)

        assert screen.game.at(cell) is P
        assert screen.game.to_move is P  # the pet has answered


async def test_tic_tac_toe_cursor_and_enter() -> None:
    app = playful()
    async with app.run_test() as pilot:
        await pilot.press("p", "3", "up", "left", "left", "enter")
        screen = app.screen
        assert isinstance(screen, TicTacToeScreen)

        assert screen.game.at(0) is P


async def test_tic_tac_toe_ignores_taken_cells() -> None:
    app = playful()
    async with app.run_test() as pilot:
        await pilot.press("p", "3", "5")
        screen = app.screen
        assert isinstance(screen, TicTacToeScreen)
        before = screen.game

        await pilot.press("5")

        assert screen.game is before


async def test_tic_tac_toe_played_to_the_end_with_the_keyboard() -> None:
    app = playful()
    async with app.run_test() as pilot:
        await pilot.press("p", "3")
        screen = app.screen
        assert isinstance(screen, TicTacToeScreen)
        for key in "789456123":
            await pilot.press(key)
        result = screen.game.result
        assert result is not None

        await pilot.press("space", "enter")
        await pilot.pause()

        assert isinstance(app.screen, MainScreen)
        assert app.session is not None
        assert app.session.pet.stats.happiness == EFFECT[result]


def test_tic_tac_toe_markup() -> None:
    won = TicTacToe((P, P, P, T, T, None, None, None, None))

    assert tic_tac_toe_markup(won, None, mono=True).count("[reverse]") == 3
    assert "◯" in tic_tac_toe_markup(won, None, mono=True)
    assert "[$tama-piece-player]✕[/]" in tic_tac_toe_markup(won, None, mono=False)
    assert tic_tac_toe_markup(TicTacToe(), 4, mono=False).count("on $foreground") == 1
