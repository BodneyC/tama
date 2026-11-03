"""Behaviour of the TUI, driven through Textual's Pilot."""

import asyncio
import os
import signal
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from textual.content import Content
from textual.widgets import Static

from tama.domain.animation import AnimationKey
from tama.domain.stage import DeathCause, LifeStage, Variant
from tama.domain.stats import Stats
from tama.errors import CorruptSaveError
from tama.infra.clock import FakeClock
from tama.persistence.repository import LoadResult
from tama.ui.app import EXIT_ERROR
from tama.ui.screens.dialogs import FeedMenu, HelpScreen, MiniGameScreen, StatusScreen
from tama.ui.screens.main import MainScreen
from tama.ui.screens.new_pet import NAME_RULE, NewPetScreen
from tama.ui.sprites import load_sprite
from tests.factories import FIXED_NOW
from tests.fakes import InMemorySaveRepository
from tests.ui.helpers import Notes, make_app, repo_with, text

if TYPE_CHECKING:
    from tama.domain.minigame import LeftRightGame

# --- Starting up --------------------------------------------------------------------------


async def test_without_a_save_asks_for_a_name_and_hatches_an_egg() -> None:
    repo = InMemorySaveRepository()
    app = make_app(repo, seed=1)
    async with app.run_test() as pilot:
        assert isinstance(app.screen, NewPetScreen)

        await pilot.press(*"Mochi", "enter")
        await pilot.pause()

        assert isinstance(app.screen, MainScreen)
        assert app.session is not None
        assert app.session.pet.name == "Mochi"
        assert app.session.pet.stage is LifeStage.EGG
        assert repo.save_count == 1


async def test_invalid_name_is_explained_and_not_accepted() -> None:
    app = make_app()
    async with app.run_test() as pilot:
        await pilot.press("space", "enter")
        await pilot.pause()

        assert isinstance(app.screen, NewPetScreen)
        assert text(app, "#name-error") == NAME_RULE


async def test_escaping_the_name_prompt_quits_without_a_pet() -> None:
    repo = InMemorySaveRepository()
    app = make_app(repo)
    async with app.run_test() as pilot:
        await pilot.press("escape")

    assert app.return_code == 0
    assert repo.save_count == 0


async def test_failing_to_save_a_new_pet_exits_with_an_error() -> None:
    repo = InMemorySaveRepository()
    repo.fail_saves = True
    app = make_app(repo)
    async with app.run_test() as pilot:
        await pilot.press(*"Mochi", "enter")

    assert app.return_code == EXIT_ERROR


async def test_start_new_hatches_even_when_a_save_exists() -> None:
    app = make_app(repo_with(), start_new=True)
    async with app.run_test():
        assert isinstance(app.screen, NewPetScreen)


async def test_existing_save_opens_the_main_screen() -> None:
    app = make_app(repo_with(stats=Stats(hunger=10)))
    async with app.run_test():
        assert isinstance(app.screen, MainScreen)
        assert text(app, "#identity") == "Mochi · child · 1h 0m"
        assert "🍖 10" in text(app, "#stats")
        assert text(app, "#attention") == "⚠ hungry"


async def test_time_away_is_summarised() -> None:
    clock = FakeClock(FIXED_NOW)
    repo = repo_with(poop_progress=0)
    clock.advance(timedelta(hours=3))
    app = make_app(repo, clock=clock)
    notes = Notes(app)
    async with app.run_test():
        assert "Pooped" in notes


async def test_backup_recovery_is_mentioned() -> None:
    repo = repo_with()
    repo.from_backup = True
    app = make_app(repo)
    notes = Notes(app)
    async with app.run_test():
        assert "recovered from the backup" in notes


async def test_unloadable_save_exits_with_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = repo_with()

    def broken() -> LoadResult:
        raise CorruptSaveError("bad json")

    monkeypatch.setattr(repo, "load", broken)
    app = make_app(repo)
    async with app.run_test():
        pass

    assert app.return_code == EXIT_ERROR


# --- Care actions -------------------------------------------------------------------------


async def test_clean() -> None:
    app = make_app(repo_with(poop_count=2, stats=Stats(hygiene=30)))
    notes = Notes(app)
    async with app.run_test() as pilot:
        await pilot.press("c")

        assert app.session is not None
        assert app.session.pet.poop_count == 0
        assert app.session.pet.stats.hygiene == 100
        assert "Was cleaned up" in notes
        assert "💩" not in text(app, "#overlay")


async def test_medicine() -> None:
    app = make_app(repo_with(sickness_doses=1))
    async with app.run_test() as pilot:
        await pilot.press("m")

        assert app.session is not None
        assert not app.session.pet.is_sick


async def test_lights_toggle_and_dim_the_stage() -> None:
    app = make_app(repo_with())
    async with app.run_test() as pilot:
        await pilot.press("l")
        await pilot.pause()

        assert app.session is not None
        assert not app.session.pet.lights_on
        assert app.screen.query_one("PetStage").has_class("lights-off")


async def test_sprite_is_drawn_in_colour_by_default() -> None:
    app = make_app(repo_with())
    async with app.run_test():
        sprite = app.screen.query_one("#sprite", Static).render()

        assert isinstance(sprite, Content)
        assert sprite.spans
        assert "█" in sprite.plain or "▀" in sprite.plain


async def test_monochrome_sprite_has_no_colours() -> None:
    app = make_app(repo_with(), monochrome=True)
    async with app.run_test():
        sprite = app.screen.query_one("#sprite", Static).render()

        assert isinstance(sprite, Content)
        assert sprite.plain.strip()
        assert all(not span.style for span in sprite.spans)


async def test_sleeping_pet_shows_zzz() -> None:
    night = FIXED_NOW.replace(hour=23)
    app = make_app(repo_with(is_asleep=True, updated_at=night), clock=FakeClock(night))
    async with app.run_test():
        assert text(app, "#overlay") == "Zzz"


async def test_failed_save_after_an_action_is_shown() -> None:
    repo = repo_with(poop_count=1)
    app = make_app(repo)
    notes = Notes(app)
    async with app.run_test() as pilot:
        repo.fail_saves = True
        await pilot.press("c")

        assert "Couldn't save" in notes
        assert "error" in notes.severities()


async def test_discipline() -> None:
    app = make_app(repo_with(misbehaving=True))
    async with app.run_test() as pilot:
        await pilot.press("d")

        assert app.session is not None
        assert not app.session.pet.misbehaving
        assert app.session.pet.stats.discipline == 25


@pytest.mark.parametrize(("key", "hunger", "happiness"), [("m", 80, 50), ("s", 55, 65)])
async def test_feed_menu(key: str, hunger: int, happiness: int) -> None:
    app = make_app(repo_with(stats=Stats(hunger=50, happiness=50)))
    async with app.run_test() as pilot:
        await pilot.press("f")
        assert isinstance(app.screen, FeedMenu)

        await pilot.press(key)
        await pilot.pause()

        assert isinstance(app.screen, MainScreen)
        assert app.session is not None
        assert app.session.pet.stats.hunger == hunger
        assert app.session.pet.stats.happiness == happiness


async def test_feed_menu_can_be_cancelled() -> None:
    repo = repo_with(stats=Stats(hunger=50))
    app = make_app(repo)
    async with app.run_test() as pilot:
        await pilot.press("f", "escape")
        await pilot.pause()

        assert isinstance(app.screen, MainScreen)
        assert app.session is not None
        assert app.session.pet.stats.hunger == 50


async def test_refused_action_is_explained() -> None:
    app = make_app(repo_with(stats=Stats(hunger=100)))
    notes = Notes(app)
    async with app.run_test() as pilot:
        await pilot.press("f", "m")
        await pilot.pause()

        assert "Refused a meal: not hungry" in notes
        assert "warning" in notes.severities()


async def test_playing_the_mini_game() -> None:
    app = make_app(repo_with(stats=Stats(happiness=50, energy=50)))
    async with app.run_test() as pilot:
        await pilot.press("p")
        assert isinstance(app.screen, MiniGameScreen)
        game_screen = app.screen

        await pilot.press("left", "right", "left", "right", "left")
        assert game_screen.game.is_over
        won = game_screen.game.won
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, MainScreen)
        assert app.session is not None
        assert app.session.pet.stats.happiness == (70 if won else 55)
        assert app.session.pet.stats.energy == 40


async def test_enter_does_nothing_until_the_game_is_over() -> None:
    app = make_app(repo_with())
    async with app.run_test() as pilot:
        await pilot.press("p", "left", "enter")

        assert isinstance(app.screen, MiniGameScreen)
        assert len(app.screen.game.results) == 1
        assert "Round 2/5" in text(app, "#game-body")


async def test_giving_up_the_game_changes_nothing() -> None:
    app = make_app(repo_with(stats=Stats(happiness=50)))
    async with app.run_test() as pilot:
        await pilot.press("p", "left", "escape")
        await pilot.pause()

        assert isinstance(app.screen, MainScreen)
        assert app.session is not None
        assert app.session.pet.stats.happiness == 50


async def test_too_tired_to_play() -> None:
    app = make_app(repo_with(stats=Stats(energy=5)))
    notes = Notes(app)
    async with app.run_test() as pilot:
        await pilot.press("p")

        assert isinstance(app.screen, MainScreen)
        assert "Refused to play: too tired" in notes


async def test_guessing_after_game_over_is_ignored() -> None:
    app = make_app(repo_with())
    async with app.run_test() as pilot:
        await pilot.press("p", *["left"] * 5)
        screen = app.screen
        assert isinstance(screen, MiniGameScreen)
        finished: LeftRightGame = screen.game

        await pilot.press("right")

        assert screen.game is finished


# --- Information screens ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "screen_type", "close"),
    [
        ("s", StatusScreen, "escape"),
        ("s", StatusScreen, "s"),
        ("question_mark", HelpScreen, "escape"),
    ],
)
async def test_information_screens_open_and_close(key: str, screen_type: type, close: str) -> None:
    app = make_app(repo_with())
    async with app.run_test() as pilot:
        await pilot.press(key)
        assert isinstance(app.screen, screen_type)

        await pilot.press(close)
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)


async def test_status_shows_stat_bars() -> None:
    app = make_app(repo_with(stats=Stats(hunger=50)))
    async with app.run_test() as pilot:
        await pilot.press("s")

        assert "Hunger     ██████████░░░░░░░░░░  50" in text(app, "#status-body")


# --- Time passing -------------------------------------------------------------------------


async def test_tick_redraws_and_announces_evolving() -> None:
    clock = FakeClock(FIXED_NOW)
    app = make_app(repo_with(stage=LifeStage.BABY, age=timedelta(minutes=59)), clock=clock)
    notes = Notes(app)
    async with app.run_test():
        clock.advance(timedelta(minutes=1))
        app.tick()

        assert text(app, "#identity") == "Mochi · child · 1h 0m"
        assert "Grew into a child" in notes


async def test_routine_events_are_not_announced() -> None:
    clock = FakeClock(FIXED_NOW)
    app = make_app(repo_with(poop_progress=0), clock=clock)
    notes = Notes(app)
    async with app.run_test():
        clock.advance(timedelta(hours=2))
        app.tick()

        assert "💩" in text(app, "#overlay")
        assert "Pooped" not in notes


async def test_failed_autosave_is_shown_once() -> None:
    repo = repo_with()
    clock = FakeClock(FIXED_NOW)
    app = make_app(repo, clock=clock)
    notes = Notes(app)
    async with app.run_test():
        repo.fail_saves = True
        app.tick()
        clock.advance(timedelta(minutes=1))
        app.tick()

        assert notes.severities().count("error") == 1


async def test_tick_before_a_pet_exists_does_nothing() -> None:
    app = make_app()
    async with app.run_test():
        app.tick()
        assert app.session is None


async def test_dead_pet_shows_a_tombstone_and_refuses_care() -> None:
    app = make_app(repo_with(stage=LifeStage.DEAD, cause_of_death=DeathCause.OLD_AGE))
    notes = Notes(app)
    async with app.run_test() as pilot:
        tombstone = load_sprite(Variant.DEFAULT, LifeStage.DEAD, AnimationKey.IDLE)
        assert text(app, "#sprite") == tombstone.frames(color=True)[0].plain

        await pilot.press("c")

        assert "Refused to be cleaned: dead" in notes


async def test_refreshing_before_the_screen_mounts_is_harmless() -> None:
    app = make_app(repo_with())
    async with app.run_test():
        assert app.session is not None
        unmounted = MainScreen(app.session)

        unmounted.refresh_pet()

        assert not unmounted.is_mounted


async def test_timer_ticks_the_session() -> None:
    clock = FakeClock(FIXED_NOW)
    repo = repo_with()
    app = make_app(repo, clock=clock)
    app._tick_interval = 0.01
    async with app.run_test() as pilot:
        await pilot.pause(0.1)

        assert repo.save_count >= 1


# --- Layout -------------------------------------------------------------------------------


async def test_too_small_terminal_shows_a_notice() -> None:
    app = make_app(repo_with())
    async with app.run_test(size=(50, 15)) as pilot:
        await pilot.pause()

        assert app.screen.has_class("-too-small")
        assert app.screen.query_one("#too-small").display


async def test_big_enough_terminal_has_no_notice() -> None:
    app = make_app(repo_with())
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()

        assert not app.screen.has_class("-too-small")


# --- Quitting -----------------------------------------------------------------------------


@pytest.mark.parametrize("key", ["q", "ctrl+c"])
async def test_quit_saves(key: str) -> None:
    repo = repo_with()
    app = make_app(repo)
    async with app.run_test() as pilot:
        await pilot.press(key)

    assert repo.save_count == 1
    assert app.return_code == 0


async def test_quit_with_failing_save_warns_then_exits() -> None:
    repo = repo_with()
    app = make_app(repo)
    notes = Notes(app)
    async with app.run_test() as pilot:
        repo.fail_saves = True
        await pilot.press("q")
        assert app.is_running
        assert "Quit again to exit without saving" in notes

        await pilot.press("q")

    assert app.return_code == 0


async def test_quitting_from_the_name_prompt() -> None:
    repo = InMemorySaveRepository()
    app = make_app(repo)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+c")

    assert repo.save_count == 0


async def test_termination_signal_saves_and_exits() -> None:
    repo = repo_with()
    app = make_app(repo)
    async with app.run_test():
        app.save_and_exit()

    assert repo.save_count == 1


async def test_termination_signal_without_a_pet_just_exits() -> None:
    app = make_app()
    async with app.run_test():
        app.save_and_exit()

    assert app.return_code == 0


async def test_termination_signal_tolerates_a_failing_save() -> None:
    repo = repo_with()
    app = make_app(repo)
    async with app.run_test():
        repo.fail_saves = True
        app.save_and_exit()

    assert app.return_code == 0


@pytest.mark.skipif(os.name != "posix", reason="POSIX signals")
async def test_sigterm_handler_is_installed_and_removed() -> None:
    repo = repo_with()
    app = make_app(repo, handle_signals=True)
    async with app.run_test() as pilot:
        os.kill(os.getpid(), signal.SIGTERM)
        await pilot.pause(0.1)

    assert repo.save_count == 1
    loop = asyncio.get_running_loop()
    assert not loop.remove_signal_handler(signal.SIGTERM)
