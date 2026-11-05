"""The player's time of day: night for the pet's sleep, and the phase the stage is tinted by.

Everything here is a pure function of a timestamp, the night window in ``Balance`` and the
player's time zone (SPEC §2.4, §5.1).
"""

from datetime import datetime, time, timedelta
from enum import StrEnum

from tama.domain.context import Context

_DAY = timedelta(days=1)


class DayPhase(StrEnum):
    """A part of the player's day."""

    DAWN = "dawn"
    DAY = "day"
    DUSK = "dusk"
    NIGHT = "night"


def _since_midnight(clock: time) -> timedelta:
    return timedelta(hours=clock.hour, minutes=clock.minute, seconds=clock.second)


def _within(local: timedelta, start: timedelta, end: timedelta) -> bool:
    """Whether ``local`` is in ``[start, end)`` on a 24-hour dial (the window may wrap)."""
    start, end = start % _DAY, end % _DAY
    if start <= end:
        return start <= local < end
    return local >= start or local < end


def is_night(when: datetime, ctx: Context) -> bool:
    """Whether ``when`` falls in the night window, in the player's time zone."""
    local = _since_midnight(when.astimezone(ctx.tz).time())
    b = ctx.balance
    return _within(local, _since_midnight(b.night_start), _since_midnight(b.night_end))


def phase(when: datetime, ctx: Context) -> DayPhase:
    """The phase of the player's day at ``when``.

    Dawn is the ``Balance.twilight`` after ``night_end`` and dusk the one before
    ``night_start``; where a short day lets them overlap, dawn wins.
    """
    if is_night(when, ctx):
        return DayPhase.NIGHT
    local = _since_midnight(when.astimezone(ctx.tz).time())
    b = ctx.balance
    start, end = _since_midnight(b.night_start), _since_midnight(b.night_end)
    if _within(local, end, end + b.twilight):
        return DayPhase.DAWN
    if _within(local, start - b.twilight, start):
        return DayPhase.DUSK
    return DayPhase.DAY
