"""Behaviour of the TUI, driven through Textual's Pilot."""

import asyncio
import os
import signal
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import pytest
from textual.content import Content
from textual.widgets import Static

from tama.domain.animation import AnimationKey
from tama.domain.balance import DEFAULT_BALANCE
from tama.domain.events import Died
from tama.domain.stage import DeathCause, LifeStage, Variant
from tama.domain.stats import Stats
from tama.errors import (
    CorruptSaveError,
    SaveError,
    SaveWriteError,
    UnsupportedSaveVersionError,
)
from tama.infra.clock import FakeClock
from tama.persistence.repository import LoadResult
from tama.services.session import CatchUp, SessionSettings
from tama.ui.app import EXIT_ERROR, TamaApp
from tama.ui.colours import Look, Mode
from tama.ui.screens.away import AwaySummaryScreen, away_text
from tama.ui.screens.dialogs import FeedMenu, HelpScreen, MiniGameScreen, StatusScreen
from tama.ui.screens.error import ErrorScreen
from tama.ui.screens.main import MainScreen
from tama.ui.screens.memorial import MemorialScreen
from tama.ui.screens.new_pet import NAME_RULE, NewPetScreen
from tama.ui.sprites import load_overlay, load_sprite, overlay_content
from tama.ui.widgets.pet_header import PetHeader
from tama.ui.widgets.pet_view import PetView, ViewOptions
from tests.factories import FIXED_NOW, make_pet
from tests.fakes import InMemorySaveRepository
from tests.ui.helpers import Notes, make_app, mono, repo_with, text

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


async def test_new_pet_hatches_as_the_chosen_species() -> None:
    repo = InMemorySaveRepository()
    app = make_app(repo, new_pet_species="owl")
    async with app.run_test() as pilot:
        await pilot.press(*"Hoot", "enter")
        await pilot.pause()

        assert app.session is not None
        assert app.session.pet.species == "owl"
        assert repo.game is not None
        assert repo.game.pet.species == "owl"


@pytest.mark.parametrize(("keys", "species"), [(["up"], "owl"), (["down"], "bear"), ([], "tama")])
async def test_species_can_be_chosen_on_the_name_prompt(keys: list[str], species: str) -> None:
    # Shipped species in order: bear, owl, tama; the prompt starts on tama and wraps around.
    repo = InMemorySaveRepository()
    app = make_app(repo)
    async with app.run_test() as pilot:
        await pilot.press(*keys, *"Mo")
        assert text(app, "#species").startswith(f"Species: {species}")
        egg = load_sprite(species, Variant.DEFAULT, LifeStage.EGG, AnimationKey.WOBBLE)
        assert app.screen.query_one(PetView).current == egg

        await pilot.press("enter")
        await pilot.pause()

        assert repo.game is not None
        assert repo.game.pet.name == "Mo"
        assert repo.game.pet.species == species
        assert app.species == species


async def test_species_choice_starts_from_the_command_line() -> None:
    app = make_app(new_pet_species="owl")
    async with app.run_test() as pilot:
        await pilot.press("down")
        assert text(app, "#species").startswith("Species: tama")


async def test_loaded_pet_sets_the_ui_species() -> None:
    app = make_app(repo_with(species="owl"))
    async with app.run_test():
        assert app.species == "owl"


async def test_status_shows_the_species() -> None:
    app = make_app(repo_with())
    async with app.run_test() as pilot:
        await pilot.press("s")

        assert "Species    tama" in text(app, "#status-body")


async def test_start_new_hatches_even_when_a_save_exists() -> None:
    app = make_app(repo_with(), start_new=True)
    async with app.run_test():
        assert isinstance(app.screen, NewPetScreen)


async def test_theme_from_config_is_applied() -> None:
    app = make_app(repo_with(), theme="nord")
    async with app.run_test():
        assert app.theme == "nord"


async def test_ui_colours_come_from_the_species_and_follow_the_mode() -> None:
    app = make_app(repo_with())
    async with app.run_test() as pilot:
        assert app.get_css_variables()["tama-accent"] == "#f6b26b"
        assert app.get_css_variables()["tama-stat-good"] == app.get_css_variables()["success"]

        app.theme = "textual-light"
        await pilot.pause()

        assert app.get_css_variables()["tama-accent"] == "#b45f06"


async def test_pet_is_drawn_for_the_theme_mode() -> None:
    app = make_app(repo_with(), theme="textual-light")
    async with app.run_test():
        view = app.screen.query_one(PetView)

        assert view.look == Look(Mode.LIGHT, color=True)


async def test_unknown_theme_is_ignored(caplog: pytest.LogCaptureFixture) -> None:
    app = make_app(repo_with(), theme="no-such-theme")
    async with app.run_test():
        assert app.theme == "textual-dark"
        assert "no-such-theme" in caplog.text


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
    async with app.run_test() as pilot:
        assert isinstance(app.screen, AwaySummaryScreen)
        body = text(app, "#away-body")
        assert "Mochi, while you were away (3h 0m):" in body
        assert "Pooped" in body

        await pilot.press("enter")
        assert isinstance(app.screen, MainScreen)


async def test_pet_sitter_is_mentioned_beyond_the_offline_cap() -> None:
    clock = FakeClock(FIXED_NOW)
    repo = repo_with()
    clock.advance(timedelta(hours=3))
    app = make_app(repo, clock=clock, settings=SessionSettings(offline_cap=timedelta(hours=1)))
    async with app.run_test():
        assert "A pet sitter looked after Mochi for the last 2h 0m." in text(app, "#away-body")


async def test_quiet_time_away_needs_no_summary() -> None:
    clock = FakeClock(FIXED_NOW)
    repo = repo_with()
    clock.advance(timedelta(seconds=30))
    app = make_app(repo, clock=clock)
    async with app.run_test():
        assert isinstance(app.screen, MainScreen)


# --- Death ----------------------------------------------------------------------------------

OLD: dict[str, Any] = {"stage": LifeStage.ELDER, "age": timedelta(days=15) - timedelta(minutes=1)}


async def test_a_dead_pet_opens_its_memorial() -> None:
    repo = repo_with(
        species="owl",
        stage=LifeStage.DEAD,
        cause_of_death=DeathCause.OLD_AGE,
        age=timedelta(days=15),
        care_mistakes=2,
    )
    app = make_app(repo)
    async with app.run_test():
        assert isinstance(app.screen, MemorialScreen)
        body = text(app, "#memorial-body")
        assert "Mochi the owl" in body
        assert "Passed away peacefully of old age" in body
        assert "Lived 15d 0h" in body
        assert "Care mistakes: 2" in body


async def test_dying_during_play_opens_the_memorial() -> None:
    clock = FakeClock(FIXED_NOW)
    app = make_app(repo_with(lifespan=timedelta(days=15), **OLD), clock=clock)
    async with app.run_test() as pilot:
        clock.advance(timedelta(minutes=2))
        app.tick()
        await pilot.pause()

        assert isinstance(app.screen, MemorialScreen)


async def test_a_new_egg_after_the_memorial() -> None:
    repo = repo_with(species="bear", stage=LifeStage.DEAD, cause_of_death=DeathCause.OLD_AGE)
    app = make_app(repo)
    async with app.run_test() as pilot:
        await pilot.press("n")
        await pilot.pause()
        assert isinstance(app.screen, NewPetScreen)
        assert text(app, "#species").startswith("Species: bear")

        await pilot.press(*"Bun", "enter")
        await pilot.pause()

        assert isinstance(app.screen, MainScreen)
        assert repo.game is not None
        assert repo.game.pet.name == "Bun"
        assert repo.game.pet.stage is LifeStage.EGG


async def test_quitting_from_the_memorial_saves() -> None:
    repo = repo_with(stage=LifeStage.DEAD, cause_of_death=DeathCause.OLD_AGE)
    app = make_app(repo)
    async with app.run_test() as pilot:
        await pilot.press("q")

    assert app.return_code == 0
    assert repo.save_count == 1


async def test_backup_recovery_is_mentioned() -> None:
    repo = repo_with()
    repo.from_backup = True
    app = make_app(repo)
    notes = Notes(app)
    async with app.run_test():
        assert "recovered from the backup" in notes


def unloadable(monkeypatch: pytest.MonkeyPatch, error: SaveError) -> InMemorySaveRepository:
    repo = repo_with()

    def broken() -> LoadResult:
        raise error

    monkeypatch.setattr(repo, "load", broken)
    return repo


async def test_unloadable_save_offers_a_new_pet(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = unloadable(monkeypatch, CorruptSaveError("bad json"))
    app = make_app(repo)
    async with app.run_test() as pilot:
        assert isinstance(app.screen, ErrorScreen)
        assert "bad json" in text(app, "#error-body")

        await pilot.press("n")
        await pilot.pause()

        assert repo.quarantined_at == FIXED_NOW
        assert isinstance(app.screen, NewPetScreen)
        await pilot.press(*"Mochi", "enter")
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)
        assert repo.game is not None


async def test_quitting_from_the_error_screen(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = unloadable(monkeypatch, CorruptSaveError("bad json"))
    app = make_app(repo)
    async with app.run_test() as pilot:
        await pilot.press("q")

    assert app.return_code == EXIT_ERROR
    assert repo.quarantined_at is None


async def test_a_newer_save_is_never_replaced(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = unloadable(monkeypatch, UnsupportedSaveVersionError("schema 9"))
    app = make_app(repo)
    async with app.run_test() as pilot:
        assert "Please upgrade tama" in text(app, "#error-body")
        await pilot.press("n")
        await pilot.pause()
        assert isinstance(app.screen, ErrorScreen)
        assert repo.quarantined_at is None

        await pilot.press("q")

    assert app.return_code == EXIT_ERROR


async def test_failing_to_move_a_bad_save_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = unloadable(monkeypatch, CorruptSaveError("bad json"))

    def stuck(now: object) -> list[object]:
        raise SaveWriteError("read-only")

    monkeypatch.setattr(repo, "quarantine", stuck)
    app = make_app(repo)
    async with app.run_test() as pilot:
        await pilot.press("n")

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
        assert text(app, "#overlay").strip() == ""


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
    app = make_app(repo_with(), view=mono())
    async with app.run_test():
        sprite = app.screen.query_one("#sprite", Static).render()

        assert isinstance(sprite, Content)
        assert sprite.plain.strip()
        assert all(not span.style for span in sprite.spans)


async def test_sleeping_pet_shows_zzz() -> None:
    night = FIXED_NOW.replace(hour=23)
    app = make_app(repo_with(is_asleep=True, updated_at=night), clock=FakeClock(night))
    async with app.run_test():
        assert text(app, "#overlay") == overlay_content(["zzz"], Look()).plain


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


async def test_the_pet_turns_the_way_it_looked() -> None:
    app = make_app(repo_with(species="owl"))
    async with app.run_test() as pilot:
        await pilot.press("p")
        game_screen = app.screen
        assert isinstance(game_screen, MiniGameScreen)
        pet_view = game_screen.query_one(PetView)
        idle = load_sprite("owl", Variant.DEFAULT, LifeStage.CHILD, AnimationKey.IDLE)
        assert pet_view.current == idle

        await pilot.press("left")

        last = game_screen.game.last_result
        assert last is not None
        key = AnimationKey(f"look_{last.pet_looked.value}")
        assert pet_view.current == load_sprite("owl", Variant.DEFAULT, LifeStage.CHILD, key)


async def test_feed_menu_shows_the_food() -> None:
    app = make_app(repo_with())
    async with app.run_test() as pilot:
        await pilot.press("f")
        menu = app.screen
        assert isinstance(menu, FeedMenu)
        assert menu.query_one("#meal", PetView).current == load_overlay("meal")
        assert menu.query_one("#snack", PetView).current == load_overlay("snack")


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

        assert text(app, "#overlay") == overlay_content(["poop"], Look()).plain
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


async def test_memorial_shows_the_species_gravestone() -> None:
    app = make_app(
        repo_with(species="owl", stage=LifeStage.DEAD, cause_of_death=DeathCause.OLD_AGE)
    )
    async with app.run_test():
        grave = load_sprite("owl", Variant.DEFAULT, LifeStage.DEAD, AnimationKey.IDLE)
        assert app.screen.query_one(PetView).current == grave


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


# --- Attention calls ----------------------------------------------------------------------


def count_bells(app: TamaApp) -> list[None]:
    rung: list[None] = []
    app.bell = lambda: rung.append(None)  # type: ignore[method-assign] # record, don't beep
    return rung


@pytest.mark.parametrize(("enabled", "rings"), [(True, 1), (False, 0)])
async def test_a_new_attention_call_rings_the_bell_once(enabled: bool, rings: int) -> None:
    clock = FakeClock(FIXED_NOW)
    app = make_app(repo_with(poop_progress=0), clock=clock, bell=enabled)
    rung = count_bells(app)
    async with app.run_test():
        clock.advance(timedelta(hours=2))
        app.tick()
        clock.advance(timedelta(seconds=1))
        app.tick()

        assert text(app, "#attention") == "⚠ poop"
        assert len(rung) == rings


async def test_needs_already_there_on_launch_dont_ring() -> None:
    app = make_app(repo_with(poop_count=1), bell=True)
    rung = count_bells(app)
    async with app.run_test():
        assert text(app, "#attention") == "⚠ poop"
        assert rung == []


async def test_attention_indicator_blinks_only_while_calling() -> None:
    app = make_app(repo_with(poop_count=1))
    async with app.run_test():
        header = app.screen.query_one(PetHeader)
        indicator = app.screen.query_one("#attention")
        header.blink()
        assert indicator.has_class("-blink-off")
        header.blink()
        assert not indicator.has_class("-blink-off")

        app.screen.query_one(PetHeader).show(make_pet(), DEFAULT_BALANCE)
        header.blink()
        assert not indicator.has_class("-blink-off")


@pytest.mark.parametrize(("reduced", "blinking"), [(False, True), (True, False)])
async def test_blinking_follows_reduced_motion(reduced: bool, blinking: bool) -> None:
    app = make_app(repo_with(poop_count=1), view=ViewOptions(animate=True, reduced_motion=reduced))
    async with app.run_test():
        assert app.screen.query_one(PetHeader).blinking is blinking


def test_no_pet_sitter_for_a_pet_that_died_while_away() -> None:
    away = CatchUp(
        timedelta(hours=80), timedelta(hours=72), (Died(timedelta(days=3), DeathCause.POOR_HEALTH),)
    )
    assert "pet sitter" not in away_text("Mochi", away)
