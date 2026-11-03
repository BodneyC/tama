"""Acceptance: the game is playable end to end against a real save file (M4, M6)."""

from datetime import datetime, time, timedelta
from pathlib import Path

import pytest
from textual.pilot import Pilot

from tama.domain.pet import Pet
from tama.domain.stage import DeathCause, LifeStage
from tama.domain.stats import Stat
from tama.infra.clock import FakeClock
from tama.persistence.repository import JsonSaveRepository
from tama.ui.screens.main import MainScreen
from tama.ui.screens.memorial import MemorialScreen
from tama.ui.screens.new_pet import NewPetScreen
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
        await pilot.press("f", "m", "c", "p", "1", *["left"] * 5, "enter")
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


def look_in(main: MainScreen) -> None:
    """Routine care on a visit, through the main screen's actions (what the keys trigger)."""
    pet = main.session.pet
    if pet.is_sick:
        main.action_act("medicine")
        main.action_act("medicine")
    if pet.poop_count or pet.stats.hygiene < 60:
        main.action_act("clean")
    for food, need, enough in (("meal", Stat.HUNGER, 70), ("snack", Stat.HAPPINESS, 60)):
        for _ in range(2):
            if main.session.pet.stats[need] < enough:
                main.action_act(food)
    if main.session.pet.misbehaving:
        main.action_act("discipline")
    pet = main.session.pet
    if pet.is_asleep == pet.lights_on:
        main.action_act("lights")


async def play_by_keyboard(pilot: Pilot[None], pet: Pet) -> None:
    """Once a day: feed through the menu and play a round of Left or Right."""
    if not pet.is_asleep and pet.stats.hunger < 95:
        await pilot.press("f", "m")
    if not pet.is_asleep and pet.stats.energy > 20:
        await pilot.press("p", "1", *["left"] * 5, "enter")


CHECK_INS = tuple(time(hour) for hour in range(7, 24, 2))
"""When the player looks in: every two hours while they're awake (07:00-23:00)."""


def next_check_in(now: datetime) -> datetime:
    """The first check-in time after ``now``."""
    for day in range(2):
        for at in CHECK_INS:
            candidate = datetime.combine(now.date() + timedelta(days=day), at, now.tzinfo)
            if candidate > now:
                return candidate
    raise AssertionError("unreachable")  # pragma: no cover - CHECK_INS repeats daily


@pytest.mark.slow
async def test_a_whole_life_from_egg_to_memorial_to_a_new_egg(tmp_path: Path) -> None:
    """M6 acceptance: hatch, raise it by keyboard to old age, then start again."""
    repo = JsonSaveRepository(tmp_path / "save.json")
    clock = FakeClock(FIXED_NOW)
    app = make_app(repo, clock=clock, seed=11)
    async with app.run_test() as pilot:
        await pilot.press(*"Mochi", "enter")
        await pilot.pause()
        clock.advance(timedelta(minutes=2))
        app.tick()
        assert app.session is not None
        stages = [app.session.pet.stage]
        while app.session.pet.is_alive and app.session.pet.age < timedelta(days=20):
            clock.set(next_check_in(clock.now()))
            app.tick()
            pet = app.session.pet  # the tick replaced it
            stages.append(pet.stage)
            if pet.is_alive and app.main is not None:
                look_in(app.main)
                if clock.now().time() == CHECK_INS[1]:
                    await play_by_keyboard(pilot, app.session.pet)
        await pilot.pause()

        assert isinstance(app.screen, MemorialScreen)
        assert app.session.pet.cause_of_death is DeathCause.OLD_AGE
        assert list(dict.fromkeys(stages)) == [
            LifeStage.BABY,
            LifeStage.CHILD,
            LifeStage.TEEN,
            LifeStage.ADULT,
            LifeStage.ELDER,
            LifeStage.DEAD,
        ]
        assert "Passed away peacefully of old age" in text(app, "#memorial-body")

        await pilot.press("n")
        await pilot.pause()
        assert isinstance(app.screen, NewPetScreen)
        await pilot.press(*"Mochi II", "enter")
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)

    reborn = repo.load().game.pet
    assert reborn.name == "Mochi II"
    assert reborn.stage is LifeStage.EGG
