"""When to save automatically (SPEC §6).

Player actions and shutdown always save; this policy covers saves triggered by time passing.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from tama.domain.events import Died, Event, Evolved


@dataclass(frozen=True, slots=True)
class AutosavePolicy:
    """Save at most every ``interval``, and straight away on life milestones."""

    interval: timedelta = timedelta(seconds=60)

    def is_due(
        self, *, now: datetime, last_saved_at: datetime | None, events: Iterable[Event]
    ) -> bool:
        """Whether a save is due, given the events since the last tick."""
        if last_saved_at is None or any(isinstance(e, Evolved | Died) for e in events):
            return True
        since = now - last_saved_at
        # A negative gap means the system clock went backwards: save to re-anchor.
        return not timedelta(0) <= since < self.interval
