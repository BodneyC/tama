"""Visits in the app: inviting, watching a game, and every way the guest goes home (SPEC §3.2)."""

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from tama.domain.journal import Topic
from tama.domain.minigames import GameResult
from tama.domain.minigames.tic_tac_toe import TicTacToe
from tama.domain.pet import Pet
from tama.domain.stage import LifeStage
from tama.domain.stats import Stats
from tama.errors import PetLockedError
from tama.persistence.lock import PetLock
from tama.persistence.roster import PetFile
from tama.services.library import PetLibrary
from tama.ui.app import TamaApp
from tama.ui.screens.games.pet_vs_pet import PetVsPetScreen
from tama.ui.screens.games.select import GameSelectScreen
from tama.ui.screens.main import MainScreen
from tama.ui.screens.visit import VisitPickerScreen, VisitScreen, WhoseStatusScreen
from tama.ui.visit_flow import NO_OTHER_PETS
from tama.ui.widgets.pet_view import ViewOptions
from tests.factories import make_pet
from tests.ui.helpers import Notes, library_with, make_app, make_library_app, repo_with

STARTING = Stats(happiness=50)


def pet(name: str, **overrides: Any) -> Pet:
    fields: dict[str, Any] = {"stage": LifeStage.ADULT, "stats": STARTING}
    return replace(make_pet(**(fields | overrides)), name=name)


def two_pets(tmp_path: Path, **guest: Any) -> tuple[PetLibrary, list[PetFile], TamaApp]:
    library, files = library_with(tmp_path, pet("Mochi"), pet("Pip", **guest))
    return library, files, make_library_app(library, open_pet=files[0])


def lock_file(file: PetFile) -> Path:
    return file.path.with_name(file.path.name + ".lock")


def result_of(screen: PetVsPetScreen) -> GameResult | None:
    """Read afresh (a narrowed attribute would hide that a key press changed it)."""
    return screen.game.result


def saved(file: PetFile) -> Pet:
    return file.repo().load().game.pet


async def test_v_invites_a_pet_and_both_cheer_up_once(tmp_path: Path) -> None:
    _, files, app = two_pets(tmp_path)
    async with app.run_test() as pilot:
        assert isinstance(app.screen, MainScreen)
        await pilot.press("v")
        assert isinstance(app.screen, VisitPickerScreen)

        await pilot.press("1")
        await pilot.pause()

        assert isinstance(app.screen, VisitScreen)
        assert app.visit is not None
        assert app.visit.host.pet.stats.happiness == 60
        assert app.visit.guest.pet.stats.happiness == 60
        assert saved(files[1]).stats.happiness == 60


async def test_watching_four_in_a_row_gives_each_pet_its_own_result(tmp_path: Path) -> None:
    _, files, app = two_pets(tmp_path)
    async with app.run_test() as pilot:
        await pilot.press("v", "1")
        await pilot.pause()
        await pilot.press("g")
        assert isinstance(app.screen, GameSelectScreen)
        await pilot.press("1")  # Four in a Row: without animation it plays out at once
        await pilot.pause()
        game = app.screen
        assert isinstance(game, PetVsPetScreen)
        result = game.game.result
        assert result is not None

        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, VisitScreen)
        visit = app.visit
        assert visit is not None
        assert visit.host.pet.stats.energy == visit.guest.pet.stats.energy == 90
        host_entry = visit.host.journal.entries[-1]
        assert host_entry.topic is Topic.PLAYED_WITH
        assert host_entry.detail == f"four_in_a_row/{result}/Pip"
        guest_entry = files[1].repo().load().game.journal.entries[-1]
        assert guest_entry.detail == f"four_in_a_row/{result.mirrored}/Mochi"


async def test_abandoning_a_game_has_no_effect(tmp_path: Path) -> None:
    _, _, app = two_pets(tmp_path)
    async with app.run_test() as pilot:
        await pilot.press("v", "1")
        await pilot.pause()
        await pilot.press("g", "2", "escape")
        await pilot.pause()

        assert isinstance(app.screen, VisitScreen)
        assert app.visit is not None
        assert app.visit.host.pet.stats.energy == 100


async def test_ending_the_visit_saves_and_unlocks_the_guest(tmp_path: Path) -> None:
    _, files, app = two_pets(tmp_path)
    async with app.run_test() as pilot:
        await pilot.press("v", "1")
        await pilot.pause()
        assert lock_file(files[1]).exists()
        with pytest.raises(PetLockedError):  # another tama can't open the guest meanwhile
            PetLock(files[1].path, pid=1, alive=lambda _: True).acquire()
        notes = Notes(app)

        await pilot.press("v")
        await pilot.pause()

        assert isinstance(app.screen, MainScreen)
        assert app.visit is None
        assert not lock_file(files[1]).exists()
        assert "Pip went home" in notes
        assert app.session is not None
        assert app.session.pet.stats.happiness == 60


async def test_the_visit_ends_by_itself_when_the_guest_gets_sleepy(tmp_path: Path) -> None:
    _, files, app = two_pets(tmp_path)
    async with app.run_test() as pilot:
        await pilot.press("v", "1")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, VisitScreen)
        notes = Notes(app)
        guest = screen.visit.guest
        guest._pet = replace(guest.pet, is_asleep=True)

        screen.tick()
        await pilot.pause()

        assert isinstance(app.screen, MainScreen)
        assert "Pip got sleepy and went home" in notes
        assert saved(files[1]).is_asleep
        assert not lock_file(files[1]).exists()


async def test_quitting_mid_game_gives_the_guest_back(tmp_path: Path) -> None:
    _, files, app = two_pets(tmp_path)
    async with app.run_test() as pilot:
        await pilot.press("v", "1")
        await pilot.pause()
        await pilot.press("g", "1")
        await pilot.pause()
        await pilot.press("ctrl+c")
        await pilot.pause()
    assert not lock_file(files[1]).exists()
    assert saved(files[1]).stats.happiness == 60


async def test_a_crash_still_gives_the_guest_back(tmp_path: Path) -> None:
    _, files, app = two_pets(tmp_path)

    async def crash_mid_visit() -> None:
        async with app.run_test() as pilot:
            await pilot.press("v", "1")
            await pilot.pause()
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await crash_mid_visit()
    assert not lock_file(files[1]).exists()


async def test_t_ends_the_visit_and_opens_the_pet_list(tmp_path: Path) -> None:
    _, files, app = two_pets(tmp_path)
    async with app.run_test() as pilot:
        await pilot.press("v", "1")
        await pilot.pause()
        await pilot.press("t")
        await pilot.pause()

        assert app.visit is None
        assert not lock_file(files[1]).exists()
        assert not lock_file(files[0]).exists()


async def test_status_for_either_pet(tmp_path: Path) -> None:
    _, _, app = two_pets(tmp_path)
    async with app.run_test() as pilot:
        await pilot.press("v", "1")
        await pilot.pause()
        await pilot.press("s")
        assert isinstance(app.screen, WhoseStatusScreen)
        await pilot.press("2")
        await pilot.pause()

        assert "Pip" in str(app.screen.query_one("#status-body").render())


async def test_a_pet_that_cant_come_is_greyed_out_and_says_why(tmp_path: Path) -> None:
    _, _, app = two_pets(tmp_path, is_asleep=True)
    async with app.run_test() as pilot:
        await pilot.press("v")
        notes = Notes(app)
        await pilot.press("1")

        assert isinstance(app.screen, VisitPickerScreen)
        assert "Pip can't come: asleep" in notes
        await pilot.press("escape")
        assert isinstance(app.screen, MainScreen)


async def test_a_host_that_cant_have_a_visit_says_why(tmp_path: Path) -> None:
    library, files = library_with(tmp_path, pet("Mochi", misbehaving=True), pet("Pip"))
    app = make_library_app(library, open_pet=files[0])
    async with app.run_test() as pilot:
        notes = Notes(app)
        await pilot.press("v")

        assert isinstance(app.screen, MainScreen)
        assert "Can't have a visit: misbehaving" in notes


async def test_with_no_other_pets_v_says_so(tmp_path: Path) -> None:
    library, files = library_with(tmp_path, pet("Mochi"))
    app = make_library_app(library, open_pet=files[0])
    async with app.run_test() as pilot:
        notes = Notes(app)
        await pilot.press("v")

        assert NO_OTHER_PETS in notes


async def test_a_single_save_file_has_no_one_to_invite() -> None:
    app = make_app(repo_with(stage=LifeStage.ADULT))
    async with app.run_test() as pilot:
        notes = Notes(app)
        await pilot.press("v")

        assert NO_OTHER_PETS in notes


async def test_a_watched_game_moves_by_itself_and_space_skips_to_the_end(tmp_path: Path) -> None:
    library, files = library_with(tmp_path, pet("Mochi"), pet("Pip"))
    app = make_library_app(library, open_pet=files[0], view=ViewOptions())
    async with app.run_test() as pilot:
        await pilot.press("v", "1")
        await pilot.pause()
        await pilot.press("g", "2")
        await pilot.pause()
        game = app.screen
        assert isinstance(game, PetVsPetScreen)
        assert game.game.result is None
        assert "Mochi's move" in str(game.query_one("#game-status").render())

        game.step()  # what the 0.8 s timer does
        board = game.game
        assert isinstance(board, TicTacToe)
        assert sum(mark is not None for mark in board.cells) == 1
        await pilot.press("space")

        assert result_of(game) is not None
        assert "Press Enter" in str(game.query_one("#game-status").render())
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, VisitScreen)
