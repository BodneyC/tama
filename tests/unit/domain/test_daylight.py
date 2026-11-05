from datetime import UTC, datetime, time, timedelta, timezone

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tama.domain.balance import Balance
from tama.domain.daylight import DayPhase, is_night, phase
from tests.factories import make_ctx

DAWN, DAY, DUSK, NIGHT = DayPhase.DAWN, DayPhase.DAY, DayPhase.DUSK, DayPhase.NIGHT


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, 1, hour, minute, tzinfo=UTC)


# --- Night -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("hour", "night"),
    [(21, False), (22, True), (3, True), (6, True), (7, False), (12, False)],
)
def test_is_night_with_window_wrapping_midnight(hour: int, night: bool) -> None:
    assert is_night(at(hour), make_ctx()) is night


@pytest.mark.parametrize(("hour", "night"), [(0, False), (1, True), (4, True), (5, False)])
def test_is_night_with_window_within_a_day(hour: int, night: bool) -> None:
    ctx = make_ctx(balance=Balance(night_start=time(1), night_end=time(5)))

    assert is_night(at(hour), ctx) is night


def test_is_night_uses_local_time_zone() -> None:
    plus_two = timezone(timedelta(hours=2))
    utc_evening = at(20, 30)  # 22:30 at UTC+2

    assert is_night(utc_evening, make_ctx(tz=plus_two))
    assert not is_night(utc_evening, make_ctx(tz=UTC))


# --- Phases ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    [
        (6, 59, NIGHT),
        (7, 0, DAWN),  # the hour after night_end (07:00)
        (7, 59, DAWN),
        (8, 0, DAY),
        (20, 59, DAY),
        (21, 0, DUSK),  # the hour before night_start (22:00)
        (21, 59, DUSK),
        (22, 0, NIGHT),
        (0, 0, NIGHT),
    ],
)
def test_phases_with_the_default_night(hour: int, minute: int, expected: DayPhase) -> None:
    assert phase(at(hour, minute), make_ctx()) is expected


@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    [
        (23, 30, DUSK),  # dusk crosses midnight into a night that starts at 00:30
        (0, 15, DUSK),
        (0, 30, NIGHT),
        (5, 59, NIGHT),
        (6, 0, DAWN),
        (7, 0, DAY),
    ],
)
def test_phases_with_a_night_after_midnight(hour: int, minute: int, expected: DayPhase) -> None:
    ctx = make_ctx(balance=Balance(night_start=time(0, 30), night_end=time(6)))

    assert phase(at(hour, minute), ctx) is expected


@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    [(23, 30, DAWN), (0, 0, DAWN), (0, 30, DAY), (12, 0, DAY)],
)
def test_dawn_can_cross_midnight(hour: int, minute: int, expected: DayPhase) -> None:
    ctx = make_ctx(balance=Balance(night_start=time(18), night_end=time(23, 30)))

    assert phase(at(hour, minute), ctx) is expected


def test_in_a_short_day_dawn_comes_before_dusk() -> None:
    # Night 22:00-21:00 leaves an hour of day; dawn and dusk both claim it.
    ctx = make_ctx(balance=Balance(night_start=time(22), night_end=time(21)))

    assert phase(at(21, 30), ctx) is DAWN


def test_phases_use_local_time_zone() -> None:
    plus_two = timezone(timedelta(hours=2))

    assert phase(at(19, 30), make_ctx(tz=plus_two)) is DUSK  # 21:30 local
    assert phase(at(19, 30), make_ctx(tz=UTC)) is DAY


def test_twilight_length_comes_from_balance() -> None:
    ctx = make_ctx(balance=Balance(twilight=timedelta(minutes=30)))

    assert phase(at(7, 29), ctx) is DAWN
    assert phase(at(7, 30), ctx) is DAY


def test_balance_rejects_a_twilight_longer_than_half_a_day() -> None:
    with pytest.raises(ValueError, match="twilight"):
        Balance(twilight=timedelta(hours=13))


@given(st.integers(0, 23), st.integers(0, 59))
def test_night_phase_is_exactly_the_night(hour: int, minute: int) -> None:
    ctx = make_ctx()

    assert (phase(at(hour, minute), ctx) is NIGHT) is is_night(at(hour, minute), ctx)
