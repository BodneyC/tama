"""Holiday from the main screen: `h` pauses a settled pet and brings it back (SPEC §2.6)."""

from dataclasses import replace
from datetime import timedelta

import pytest

from tama.domain.stats import Stats
from tama.infra.clock import FakeClock
from tama.ui.screens.dialogs import FeedMenu
from tama.ui.screens.main import MainScreen
from tama.ui.widgets.pet_stage import PetStage, overlay_names
from tests.factories import FIXED_NOW, make_pet
from tests.ui.helpers import Notes, make_app, repo_with, text


async def test_h_puts_a_settled_pet_on_holiday() -> None:
    repo = repo_with()
    app = make_app(repo)
    notes = Notes(app)
    async with app.run_test() as pilot:
        await pilot.press("h")

        assert app.session is not None
        assert app.session.pet.on_holiday
        assert repo.game is not None
        assert repo.game.pet.on_holiday
        assert "Went on holiday" in notes
        assert text(app, "#attention") == "⏸ on holiday since 1 Jan"
        assert app.screen.query_one(PetStage).has_class("on-holiday")


async def test_an_unsettled_pet_is_not_paused() -> None:
    app = make_app(repo_with(stats=Stats(hunger=10), poop_count=1))
    notes = Notes(app)
    async with app.run_test() as pilot:
        await pilot.press("h")

        assert app.session is not None
        assert not app.session.pet.on_holiday
        assert "Can't go on holiday: hungry, poop" in notes
        assert "warning" in notes.severities()


@pytest.mark.parametrize(
    ("key", "message"),
    [
        ("f", "Refused a meal: on holiday"),
        ("p", "Refused to play: on holiday"),
        ("c", "Refused to be cleaned: on holiday"),
        ("d", "Refused discipline: on holiday"),
    ],
)
async def test_care_is_refused_on_holiday(key: str, message: str) -> None:
    app = make_app(repo_with(paused_since=FIXED_NOW))
    notes = Notes(app)
    async with app.run_test() as pilot:
        await pilot.press(key)
        await pilot.pause()

        assert isinstance(app.screen, MainScreen)
        assert not isinstance(app.screen, FeedMenu)
        assert message in notes


async def test_a_pet_comes_back_from_holiday_exactly_as_it_was() -> None:
    clock = FakeClock(FIXED_NOW)
    repo = repo_with(paused_since=FIXED_NOW, stats=Stats(hunger=40))
    assert repo.game is not None
    before = repo.game.pet
    clock.advance(timedelta(days=7))
    app = make_app(repo, clock=clock)
    notes = Notes(app)
    async with app.run_test() as pilot:
        assert isinstance(app.screen, MainScreen)  # nothing happened, so no away summary
        app.tick()
        await pilot.press("h")

        assert app.session is not None
        pet = app.session.pet
        assert not pet.on_holiday
        assert pet.age == before.age
        assert pet.stats == before.stats
        assert "Was on holiday for 7d 0h" in notes
        assert text(app, "#attention") == ""


def test_the_stage_shows_only_a_suitcase_on_holiday() -> None:
    pet = make_pet(paused_since=FIXED_NOW, poop_count=2, is_asleep=True)

    assert overlay_names(pet) == ["suitcase"]


async def test_acceptance_paused_with_h_and_back_after_a_week_exactly_as_it_was() -> None:
    clock = FakeClock(FIXED_NOW)
    repo = repo_with(stats=Stats(hunger=60, happiness=55, energy=70, hygiene=80))
    first = make_app(repo, clock=clock)
    async with first.run_test() as pilot:
        await pilot.press("h")
        assert first.session is not None
        before = first.session.pet
        await pilot.press("q")
    assert repo.game is not None
    assert repo.game.pet.on_holiday

    clock.advance(timedelta(days=7))
    second = make_app(repo, clock=clock)
    async with second.run_test() as pilot:
        assert isinstance(second.screen, MainScreen)
        await pilot.press("h")
        assert second.session is not None
        after = second.session.pet

    assert after.age == before.age
    assert after == replace(before, paused_since=None, updated_at=FIXED_NOW + timedelta(days=7))
