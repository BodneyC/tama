"""Visits between two of the player's pets (SPEC §3.2, ADR 0011)."""

import os
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from random import Random
from typing import Any

import pytest

from tama.domain.events import PlayedWith, Visited
from tama.domain.journal import Topic
from tama.domain.minigames import GameKind, GameResult
from tama.domain.minigames.four_in_a_row import FourInARow
from tama.domain.minigames.tic_tac_toe import TicTacToe
from tama.domain.stage import LifeStage
from tama.domain.stats import Stats
from tama.domain.visit import VisitRefusal
from tama.errors import (
    InvalidArgumentError,
    PetLockedError,
    SaveError,
    SaveWriteError,
    VisitRefusedError,
)
from tama.infra.clock import FakeClock
from tama.persistence.models import SaveGame
from tama.persistence.roster import PetFile, PetRoster
from tama.services.library import PetLibrary
from tama.services.session import GameSession, SessionSettings
from tama.services.visit import OPEN_ELSEWHERE, UNREADABLE, VisitSession
from tests.factories import FIXED_NOW
from tests.factories import make_pet as base_pet

FOUR = GameKind.FOUR_IN_A_ROW


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(FIXED_NOW)


@pytest.fixture
def library(tmp_path: Path, clock: FakeClock) -> PetLibrary:
    return PetLibrary(PetRoster(tmp_path), clock=clock, settings=SessionSettings())


def add(library: PetLibrary, name: str, seed: int = 0, **overrides: Any) -> PetFile:
    """An adult saved as of now, so nothing happens to it while catching up."""
    fields: dict[str, Any] = {"stage": LifeStage.ADULT, "stats": Stats(happiness=50)}
    pet = replace(base_pet(**(fields | overrides)), name=name, updated_at=FIXED_NOW)
    file = library.roster.create(name)
    file.repo().save(SaveGame(pet, Random(seed).getstate()))
    return file


def lock_elsewhere(file: PetFile) -> None:
    """Lock ``file`` as another running tama would (the parent process is surely alive)."""
    file.path.with_name(file.path.name + ".lock").write_text(str(os.getppid()))


def saved(file: PetFile) -> SaveGame:
    return file.repo().load().game


@pytest.fixture
def mochi(library: PetLibrary) -> GameSession:
    return library.open(add(library, "Mochi", seed=1)).session


@pytest.fixture
def pip(library: PetLibrary) -> PetFile:
    return add(library, "Pip", seed=2)


@pytest.fixture
def visit(library: PetLibrary, mochi: GameSession, pip: PetFile) -> VisitSession:
    return library.borrow_for_visit(pip, mochi)


# --- Inviting ------------------------------------------------------------------------------


def test_the_picker_lists_every_other_pet_with_why_it_cant_come(
    library: PetLibrary, mochi: GameSession
) -> None:
    add(library, "Ace")
    add(library, "Bo", is_asleep=True)
    add(library, "Cy", paused_since=FIXED_NOW)
    lock_elsewhere(add(library, "Di"))
    library.roster.create("Ed").path.write_text("not json", encoding="utf-8")

    rows = {c.summary.name[:2]: c for c in library.visit_candidates()}

    assert set(rows) == {"Ac", "Bo", "Cy", "Di", "ed"}  # never the host; "ed-…" is its file
    assert rows["Ac"].can_come
    assert {name: row.reason for name, row in rows.items() if not row.can_come} == {
        "Bo": "asleep",
        "Cy": "on holiday",
        "Di": OPEN_ELSEWHERE,
        "ed": UNREADABLE,
    }


def test_a_visit_cheers_both_pets_up_once_and_saves_them(
    visit: VisitSession, mochi: GameSession, pip: PetFile
) -> None:
    assert visit.greetings is not None
    host, guest = visit.greetings
    assert host.events == (Visited(mochi.pet.age, "Pip", cheered=True),)
    assert guest.events == (Visited(guest.pet.age, "Mochi", cheered=True),)
    assert mochi.pet.stats.happiness == 60
    assert saved(pip).pet.stats.happiness == 60
    assert saved(pip).journal.entries[-1].topic is Topic.VISIT


def test_the_guest_is_locked_for_the_visit(library: PetLibrary, visit: VisitSession) -> None:
    lock = Path(str(library.roster.files()[1].path) + ".lock")
    assert lock.read_text() == str(os.getpid())

    visit.close()

    assert not lock.exists()


def test_a_pet_open_elsewhere_cant_visit(
    library: PetLibrary, mochi: GameSession, pip: PetFile
) -> None:
    lock_elsewhere(pip)

    with pytest.raises(PetLockedError):
        library.borrow_for_visit(pip, mochi)


def test_a_pet_cant_visit_itself(library: PetLibrary, mochi: GameSession) -> None:
    assert library.open_file is not None

    with pytest.raises(InvalidArgumentError):
        library.borrow_for_visit(library.open_file, mochi)


def test_a_guest_that_cant_come_is_given_back_untouched(
    library: PetLibrary, mochi: GameSession
) -> None:
    bo = add(library, "Bo", is_asleep=True)
    before = bo.path.read_text()

    with pytest.raises(VisitRefusedError, match="Bo can't visit: asleep"):
        library.borrow_for_visit(bo, mochi)

    assert bo.path.read_text() == before
    assert not Path(str(bo.path) + ".lock").exists()
    assert mochi.pet.stats.happiness == 50


def test_a_host_that_cant_have_a_visit_takes_no_lock(library: PetLibrary, pip: PetFile) -> None:
    host = library.open(add(library, "Mochi", stats=Stats(energy=0))).session

    with pytest.raises(VisitRefusedError, match="too tired"):
        library.borrow_for_visit(pip, host)

    assert not Path(str(pip.path) + ".lock").exists()


def test_an_unreadable_guest_is_unlocked(library: PetLibrary, mochi: GameSession) -> None:
    ed = library.roster.create("Ed")
    ed.path.write_text("not json", encoding="utf-8")

    with pytest.raises(SaveError):
        library.borrow_for_visit(ed, mochi)

    assert not Path(str(ed.path) + ".lock").exists()


# --- During the visit ----------------------------------------------------------------------


def test_both_pets_live_in_real_time(visit: VisitSession, clock: FakeClock) -> None:
    clock.advance(timedelta(minutes=10))

    tick = visit.tick()

    assert visit.host.pet.updated_at == visit.guest.pet.updated_at == clock.now()
    assert tick.ended is None


def test_the_visit_ends_when_the_guest_cant_go_on(visit: VisitSession) -> None:
    visit.guest._pet = replace(visit.guest.pet, is_asleep=True)

    ended = visit.ended()

    assert ended is not None
    assert (ended.leaver, ended.reason) == ("Pip", VisitRefusal.ASLEEP)
    assert ended.text == "Pip got sleepy and went home"


def test_the_host_is_checked_first(visit: VisitSession) -> None:
    visit.host._pet = replace(visit.host.pet, sickness_doses=1)
    visit.guest._pet = replace(visit.guest.pet, misbehaving=True)

    ended = visit.ended()

    assert ended is not None
    assert ended.text == "Mochi felt poorly, so Pip went home"
    assert not visit.can_play()


def test_each_pet_moves_for_its_own_side(visit: VisitSession) -> None:
    game = visit.move(FourInARow())  # the host opens
    game = visit.move(game)  # then the guest

    assert sum(len(c) for c in game.columns) == 2


def test_a_game_plays_out_to_the_end(visit: VisitSession) -> None:
    assert visit.play_out(TicTacToe()).result is not None


def test_a_game_replays_from_the_two_pets_saved_rngs(tmp_path: Path) -> None:
    def play(folder: str) -> FourInARow:
        lib = PetLibrary(
            PetRoster(tmp_path / folder), clock=FakeClock(FIXED_NOW), settings=SessionSettings()
        )
        host = lib.open(add(lib, "Mochi", seed=1)).session
        visit = lib.borrow_for_visit(add(lib, "Pip", seed=2), host)
        return visit.play_out(FourInARow())

    assert play("a") == play("b")


@pytest.mark.parametrize(
    ("result", "host_result", "guest_result"),
    [
        (GameResult.WIN, GameResult.WIN, GameResult.LOSS),
        (GameResult.LOSS, GameResult.LOSS, GameResult.WIN),
        (GameResult.DRAW, GameResult.DRAW, GameResult.DRAW),
    ],
)
def test_each_pet_gets_the_game_from_its_own_side(
    visit: VisitSession,
    pip: PetFile,
    result: GameResult,
    host_result: GameResult,
    guest_result: GameResult,
) -> None:
    host, guest = visit.finish_game(FOUR, result)

    assert host.events == (PlayedWith(host.events[0].age, "Pip", FOUR, host_result),)
    assert guest.events == (PlayedWith(guest.events[0].age, "Mochi", FOUR, guest_result),)
    assert visit.host.pet.stats.energy == visit.guest.pet.stats.energy == 90
    assert saved(pip).pet.stats.energy == 90


# --- Ending ------------------------------------------------------------------------------


def test_closing_saves_the_guest_once(visit: VisitSession, pip: PetFile, clock: FakeClock) -> None:
    clock.advance(timedelta(minutes=5))
    visit.tick()

    visit.close()
    first = pip.path.read_text()
    visit.close()

    assert visit.closed
    assert saved(pip).pet.updated_at == FIXED_NOW + timedelta(minutes=5)
    assert pip.path.read_text() == first


def test_the_guest_is_unlocked_even_if_it_cant_be_saved(
    visit: VisitSession, pip: PetFile, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail() -> None:
        raise SaveWriteError("disk full")

    monkeypatch.setattr(visit.guest, "close", fail)

    with pytest.raises(SaveWriteError):
        visit.close()

    assert not Path(str(pip.path) + ".lock").exists()
