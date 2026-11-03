from datetime import UTC, datetime, timedelta

import pytest

from tama.errors import InvalidArgumentError, TamaError
from tama.infra.clock import Clock, FakeClock, ScaledClock, SystemClock, local_timezone
from tests.factories import FIXED_NOW


def test_system_clock_returns_aware_utc_now() -> None:
    before = datetime.now(UTC)
    now = SystemClock().now()
    after = datetime.now(UTC)

    assert now.tzinfo is UTC
    assert before <= now <= after


def test_fake_clock_starts_at_given_time() -> None:
    assert FakeClock(FIXED_NOW).now() == FIXED_NOW


def test_fake_clock_advance_moves_time_forward() -> None:
    clock = FakeClock(FIXED_NOW)

    clock.advance(timedelta(minutes=5))

    assert clock.now() == FIXED_NOW + timedelta(minutes=5)


def test_fake_clock_can_go_backwards_to_simulate_system_clock_changes() -> None:
    clock = FakeClock(FIXED_NOW)

    clock.advance(timedelta(hours=-1))

    assert clock.now() == FIXED_NOW - timedelta(hours=1)


def test_fake_clock_set_jumps_to_time() -> None:
    clock = FakeClock(FIXED_NOW)
    target = FIXED_NOW + timedelta(days=3)

    clock.set(target)

    assert clock.now() == target


@pytest.mark.parametrize("naive", [datetime(2026, 1, 1)])  # noqa: DTZ001 - deliberately naive
def test_fake_clock_rejects_naive_datetimes(naive: datetime) -> None:
    with pytest.raises(InvalidArgumentError, match="timezone-aware"):
        FakeClock(naive)
    clock = FakeClock(FIXED_NOW)
    with pytest.raises(InvalidArgumentError, match="timezone-aware"):
        clock.set(naive)


def test_scaled_clock_multiplies_elapsed_time() -> None:
    base = FakeClock(FIXED_NOW)
    scaled = ScaledClock(base, speed=60)

    base.advance(timedelta(seconds=10))

    assert scaled.now() == FIXED_NOW + timedelta(minutes=10)


def test_scaled_clock_starts_at_base_time() -> None:
    base = FakeClock(FIXED_NOW)

    assert ScaledClock(base, speed=600).now() == FIXED_NOW


def test_scaled_clock_with_speed_one_tracks_base() -> None:
    base = FakeClock(FIXED_NOW)
    scaled = ScaledClock(base, speed=1)

    base.advance(timedelta(hours=2))

    assert scaled.now() == base.now()


@pytest.mark.parametrize("speed", [0, -1, -0.5])
def test_scaled_clock_rejects_non_positive_speed(speed: float) -> None:
    with pytest.raises(InvalidArgumentError, match="speed"):
        ScaledClock(FakeClock(FIXED_NOW), speed=speed)


def test_invalid_argument_error_is_a_tama_error_and_value_error() -> None:
    assert issubclass(InvalidArgumentError, TamaError)
    assert issubclass(InvalidArgumentError, ValueError)


@pytest.mark.parametrize(
    "clock",
    [SystemClock(), FakeClock(FIXED_NOW), ScaledClock(FakeClock(FIXED_NOW), speed=2)],
)
def test_all_clocks_satisfy_protocol(clock: Clock) -> None:
    assert isinstance(clock, Clock)


def test_local_timezone_matches_system_offset() -> None:
    zone = local_timezone()
    now = datetime.now(UTC)

    assert now.astimezone(zone).utcoffset() == now.astimezone().utcoffset()
