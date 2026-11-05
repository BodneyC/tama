"""M6.13 acceptance: a disciplined child learns to spin; the stage follows the time of day."""

from dataclasses import replace
from datetime import time, timedelta

from tama.domain.animation import AnimationKey
from tama.domain.balance import DEFAULT_BALANCE
from tama.domain.daylight import DayPhase
from tama.domain.stage import LifeStage, Variant
from tama.domain.stats import Stats
from tama.infra.clock import FakeClock
from tama.services.session import SessionSettings
from tama.ui.screens.main import MainScreen
from tama.ui.sprites import load_sprite
from tama.ui.widgets.pet_stage import PetStage
from tama.ui.widgets.pet_view import PetView
from tests.factories import FIXED_NOW
from tests.ui.helpers import Notes, make_app, repo_with


def child_sprite(key: AnimationKey) -> object:
    return load_sprite("tama", Variant.DEFAULT, LifeStage.CHILD, key)


async def test_disciplining_a_child_from_40_to_65_teaches_it_to_spin() -> None:
    app = make_app(repo_with(misbehaving=True, stats=Stats(happiness=90, discipline=40)))
    notes = Notes(app)
    async with app.run_test() as pilot:
        view = app.screen.query_one(PetView)

        await pilot.press("d")

        # A toast, and it performs the new trick at once.
        assert ("Learned to spin!", "information") in notes.messages
        assert view.current is child_sprite(AnimationKey.TRICK_SPIN)
        await pilot.press("s")
        assert "Tricks     wave, spin" in str(app.screen.query_one("#status-body").render())
        await pilot.press("escape")

        # Then, content, it performs one of its tricks now and then in place of a blink.
        tricks = [child_sprite(AnimationKey.TRICK_WAVE), child_sprite(AnimationKey.TRICK_SPIN)]
        shown = 0
        for _ in range(10 * 60 * 10):  # ten minutes of animation steps
            before = view.reaction
            view.step()
            if view.reaction is not before and any(view.reaction is t for t in tricks):
                shown += 1
        assert 3 <= shown <= 10  # every 1-3 minutes


async def test_the_stage_changes_at_dusk_and_dawn_of_the_configured_night() -> None:
    # A night owl's window: 01:00-09:00, so dusk is 00:00-01:00 and dawn 09:00-10:00.
    balance = replace(DEFAULT_BALANCE, night_start=time(1), night_end=time(9))
    clock = FakeClock(FIXED_NOW.replace(hour=23, minute=55))
    app = make_app(
        repo_with(updated_at=clock.now(), is_asleep=False),
        clock=clock,
        settings=SessionSettings(balance=balance),
    )
    seen: list[tuple[str, str]] = []
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, MainScreen)
        for minutes in (0, 10, 60, 8 * 60, 60, 1):  # 23:55, 00:05, 01:05, 09:05, 10:05, 10:06
            clock.advance(timedelta(minutes=minutes))
            screen.tick()
            await pilot.pause()
            stage = screen.query_one(PetStage)
            phase = next(p for p in DayPhase if stage.has_class(f"-{p}"))
            seen.append((f"{clock.now():%H:%M}", phase.value))

    assert seen == [
        ("23:55", "day"),
        ("00:05", "dusk"),
        ("01:05", "night"),
        ("09:05", "dawn"),
        ("10:05", "day"),
        ("10:06", "day"),
    ]  # readable in both themes: tests/ui/snapshots/test_daylight_snapshots.py, reviewed
