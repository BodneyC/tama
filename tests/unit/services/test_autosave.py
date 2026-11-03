from datetime import timedelta

import pytest

from tama.domain.events import Died, Event, Evolved, FellAsleep
from tama.domain.stage import DeathCause, LifeStage, Variant
from tama.services.autosave import AutosavePolicy
from tests.factories import FIXED_NOW

AGE = timedelta(hours=1)
POLICY = AutosavePolicy()


def due(seconds_since_save: float | None, events: list[Event] | None = None) -> bool:
    last = None if seconds_since_save is None else FIXED_NOW - timedelta(seconds=seconds_since_save)
    return POLICY.is_due(now=FIXED_NOW, last_saved_at=last, events=events or [])


def test_default_interval_is_a_minute() -> None:
    assert POLICY.interval == timedelta(seconds=60)


def test_due_if_never_saved() -> None:
    assert due(None)


@pytest.mark.parametrize(
    ("seconds", "expected"), [(0, False), (59, False), (60, True), (600, True)]
)
def test_due_after_interval(seconds: float, expected: bool) -> None:
    assert due(seconds) is expected


@pytest.mark.parametrize(
    "event",
    [Evolved(AGE, LifeStage.BABY, LifeStage.CHILD, Variant.DEFAULT), Died(AGE, DeathCause.OLD_AGE)],
)
def test_due_immediately_on_milestones(event: Event) -> None:
    assert due(1, [event])


def test_ordinary_events_do_not_force_a_save() -> None:
    assert not due(1, [FellAsleep(AGE)])


def test_due_if_clock_went_backwards_since_last_save() -> None:
    assert due(-30)
