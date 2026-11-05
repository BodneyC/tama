"""The stage's background follows the player's time of day (SPEC §5.1)."""

from datetime import timedelta

import pytest

from tama.domain.daylight import DayPhase
from tama.infra.clock import FakeClock
from tama.ui.screens.main import MainScreen
from tama.ui.widgets.pet_stage import PetStage
from tests.factories import FIXED_NOW
from tests.ui.helpers import make_app, mono, repo_with

PHASES = [f"-{phase}" for phase in DayPhase]


def phase_classes(stage: PetStage) -> list[str]:
    return [name for name in PHASES if stage.has_class(name)]


async def test_the_stage_is_plain_by_day() -> None:
    app = make_app(repo_with())  # midday
    async with app.run_test():
        assert phase_classes(app.screen.query_one(PetStage)) == ["-day"]


@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    [(21, 0, "-dusk"), (22, 0, "-night"), (7, 0, "-dawn"), (8, 0, "-day")],
)
async def test_the_stage_changes_at_dusk_and_dawn_on_the_next_tick(
    hour: int, minute: int, expected: str
) -> None:
    change = FIXED_NOW.replace(hour=hour, minute=minute)
    clock = FakeClock(change - timedelta(minutes=30))
    app = make_app(repo_with(updated_at=clock.now()), clock=clock)
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, MainScreen)
        before = phase_classes(screen.query_one(PetStage))
        clock.set(change)

        screen.tick()
        await pilot.pause()

        assert phase_classes(screen.query_one(PetStage)) == [expected] != before


async def test_the_tint_shows_and_lights_off_dims_on_top() -> None:
    clock = FakeClock(FIXED_NOW.replace(hour=22, minute=30))
    app = make_app(repo_with(updated_at=clock.now()), clock=clock)
    async with app.run_test() as pilot:
        stage = app.screen.query_one(PetStage)
        night = stage.styles.background
        assert night != app.screen.styles.background

        await pilot.press("l")

        assert stage.has_class("lights-off")
        assert stage.has_class("-night")
        assert stage.styles.background != night


async def test_no_tint_without_colour() -> None:
    clock = FakeClock(FIXED_NOW.replace(hour=22, minute=30))
    app = make_app(repo_with(updated_at=clock.now()), clock=clock, view=mono())
    async with app.run_test():
        assert phase_classes(app.screen.query_one(PetStage)) == []


async def test_a_pet_on_holiday_still_sees_the_time_of_day() -> None:
    clock = FakeClock(FIXED_NOW.replace(hour=21, minute=15))
    app = make_app(repo_with(updated_at=clock.now(), paused_since=clock.now()), clock=clock)
    async with app.run_test():
        assert phase_classes(app.screen.query_one(PetStage)) == ["-dusk"]
