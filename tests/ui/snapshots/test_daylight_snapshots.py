"""The stage at each time of day, on dark and light themes (SPEC §5.1).

Regenerate with ``uv run pytest -n0 tests/ui/snapshots --snapshot-update`` and review the images:
the pet must stay readable on every tint.
"""

from collections.abc import Callable

import pytest

from tama.infra.clock import FakeClock
from tests.factories import FIXED_NOW
from tests.ui.helpers import make_app, repo_with

SnapCompare = Callable[..., bool]

TIMES = {"dawn": (7, 30), "day": (12, 0), "dusk": (21, 30), "night": (23, 30)}


@pytest.mark.parametrize("theme", ["textual-dark", "textual-light"])
@pytest.mark.parametrize("phase", list(TIMES))
def test_stage_at_each_time_of_day(snap_compare: SnapCompare, phase: str, theme: str) -> None:
    hour, minute = TIMES[phase]
    now = FIXED_NOW.replace(hour=hour, minute=minute)
    app = make_app(repo_with(updated_at=now), clock=FakeClock(now), theme=theme)
    assert snap_compare(app, terminal_size=(60, 20))
