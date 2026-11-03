"""Sources of wall-clock time.

This is the only module allowed to read the system clock; everything else receives a
``Clock`` so time can be faked in tests and scaled for debugging (``--speed``).
"""

from datetime import UTC, datetime, timedelta, tzinfo
from typing import Protocol, runtime_checkable

from tama.errors import InvalidArgumentError


@runtime_checkable
class Clock(Protocol):
    """Something that can tell the current time."""

    def now(self) -> datetime:
        """Return the current time as a timezone-aware UTC ``datetime``."""
        ...


def _require_aware(when: datetime) -> datetime:
    if when.tzinfo is None or when.utcoffset() is None:
        raise InvalidArgumentError(f"datetime must be timezone-aware, got {when!r}")
    return when.astimezone(UTC)


class SystemClock:
    """The real system clock."""

    def now(self) -> datetime:
        """Return the current UTC time."""
        return datetime.now(UTC)


class FakeClock:
    """A manually-controlled clock for tests.

    Time only moves when told to, and may move backwards to simulate system clock changes.
    """

    def __init__(self, start: datetime) -> None:
        """Create a clock frozen at ``start`` (must be timezone-aware)."""
        self._now = _require_aware(start)

    def now(self) -> datetime:
        """Return the clock's current time."""
        return self._now

    def advance(self, delta: timedelta) -> None:
        """Move the clock by ``delta`` (negative values move it backwards)."""
        self._now += delta

    def set(self, when: datetime) -> None:
        """Jump the clock to ``when`` (must be timezone-aware)."""
        self._now = _require_aware(when)


class ScaledClock:
    """Wraps another clock so that time passes ``speed`` times faster.

    Scaling is anchored at construction: ``now()`` equals the base clock's time at creation,
    then diverges as ``origin + elapsed * speed``.
    """

    def __init__(self, base: Clock, *, speed: float) -> None:
        """Create a clock running ``speed`` times faster than ``base`` (``speed`` > 0)."""
        if speed <= 0:
            raise InvalidArgumentError(f"speed must be positive, got {speed}")
        self._base = base
        self._speed = speed
        self._origin = base.now()

    def now(self) -> datetime:
        """Return the scaled current time."""
        elapsed: timedelta = self._base.now() - self._origin
        return self._origin + elapsed * self._speed


def local_timezone() -> tzinfo:
    """Return the system's current local time zone (used for the pet's day/night)."""
    return datetime.now(UTC).astimezone().tzinfo or UTC
