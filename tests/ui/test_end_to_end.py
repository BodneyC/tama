"""M4 acceptance: the game is playable end to end against a real save file."""

from datetime import timedelta
from pathlib import Path

from tama.domain.stage import LifeStage
from tama.infra.clock import FakeClock
from tama.persistence.repository import JsonSaveRepository
from tama.ui.screens.main import MainScreen
from tests.factories import FIXED_NOW
from tests.ui.helpers import make_app, text


async def test_hatch_care_quit_and_come_back(tmp_path: Path) -> None:
    repo = JsonSaveRepository(tmp_path / "save.json")
    clock = FakeClock(FIXED_NOW)

    # First session: hatch, let it grow a little, care for it, quit.
    app = make_app(repo, clock=clock, seed=3)
    async with app.run_test() as pilot:
        await pilot.press(*"Mochi", "enter")
        await pilot.pause()
        clock.advance(timedelta(hours=2))
        app.tick()
        assert text(app, "#identity") == "Mochi · child · 2h 0m"

        hunger_before = app.session.pet.stats.hunger if app.session else 0
        await pilot.press("f", "m", "c", "p", *["left"] * 5, "enter")
        assert app.session is not None
        at_quit = app.session.pet
        await pilot.press("q")
    assert app.return_code == 0
    saved = repo.load().game.pet
    assert saved == at_quit
    assert saved.stage is LifeStage.CHILD
    assert saved.stats.hunger > hunger_before
    assert saved.stats.hygiene == 100
    assert saved.poop_count == 0

    # Later: the pet has carried on without us, and remembers everything.
    clock.advance(timedelta(minutes=30))
    again = make_app(repo, clock=clock)
    async with again.run_test() as pilot:
        assert isinstance(again.screen, MainScreen)
        assert again.session is not None
        assert again.session.pet.name == "Mochi"
        assert again.session.pet.age == saved.age + timedelta(minutes=30)
        await pilot.press("q")
    assert again.return_code == 0
