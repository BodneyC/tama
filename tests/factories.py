"""Shared test builders.

Domain builders (``make_pet``, ``make_ctx``) are added here in M1. Tests should use these
rather than hand-constructing full objects.
"""

from datetime import UTC, datetime

from tama.infra.clock import FakeClock

FIXED_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
"""A stable, timezone-aware 'now' for deterministic tests."""


def make_clock(now: datetime = FIXED_NOW) -> FakeClock:
    """Return a ``FakeClock`` starting at ``now``."""
    return FakeClock(now)
