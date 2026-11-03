"""SVG snapshots of key screens at 80x24, with a frozen clock and no tick timer.

Regenerate with ``uv run pytest -n0 tests/ui/snapshots --snapshot-update`` and review the diff.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from textual.pilot import Pilot

from tama.domain.stage import DeathCause, LifeStage, Variant
from tama.domain.stats import Stats
from tama.errors import CorruptSaveError, SaveError, UnsupportedSaveVersionError
from tama.infra.clock import FakeClock
from tama.persistence.repository import LoadResult
from tama.ui.app import TamaApp
from tama.ui.widgets.pet_header import PetHeader
from tests.factories import FIXED_NOW
from tests.ui.helpers import make_app, mono, repo_with

SnapCompare = Callable[..., bool]
NIGHT = datetime(2026, 1, 1, 23, tzinfo=UTC)


def child_app() -> TamaApp:
    """A child who needs a bit of attention: hungry-ish, one poop."""
    return make_app(repo_with(stats=Stats(hunger=20, happiness=45, energy=70), poop_count=1))


def test_new_pet_screen(snap_compare: SnapCompare) -> None:
    async def type_name(pilot: Pilot[None]) -> None:
        await pilot.press(*"Mochi")

    assert snap_compare(make_app(), run_before=type_name)


def test_main_screen(snap_compare: SnapCompare) -> None:
    assert snap_compare(child_app())


def test_status_screen(snap_compare: SnapCompare) -> None:
    assert snap_compare(child_app(), press=["s"])


def test_help_screen(snap_compare: SnapCompare) -> None:
    assert snap_compare(child_app(), press=["question_mark"])


def test_feed_menu(snap_compare: SnapCompare) -> None:
    assert snap_compare(child_app(), press=["f"])


def test_mini_game(snap_compare: SnapCompare) -> None:
    assert snap_compare(child_app(), press=["p", "left"])


def test_asleep_with_lights_off(snap_compare: SnapCompare) -> None:
    app = make_app(
        repo_with(is_asleep=True, lights_on=False, updated_at=NIGHT), clock=FakeClock(NIGHT)
    )
    assert snap_compare(app)


def test_memorial_screen(snap_compare: SnapCompare) -> None:
    app = make_app(
        repo_with(stage=LifeStage.DEAD, cause_of_death=DeathCause.OLD_AGE, care_mistakes=3)
    )
    assert snap_compare(app)


def test_away_summary(snap_compare: SnapCompare) -> None:
    clock = FakeClock(FIXED_NOW)
    repo = repo_with(poop_progress=0)
    clock.advance(timedelta(hours=5))
    assert snap_compare(make_app(repo, clock=clock))


@pytest.mark.parametrize(
    "error",
    [CorruptSaveError("save.json: invalid JSON"), UnsupportedSaveVersionError("save is v9")],
    ids=["corrupt", "newer"],
)
def test_error_screen(snap_compare: SnapCompare, error: SaveError) -> None:
    repo = repo_with()

    def broken() -> LoadResult:
        raise error

    repo.load = broken  # type: ignore[method-assign] # simulate an unreadable save
    assert snap_compare(make_app(repo))


def test_attention_indicator_blinked_off(snap_compare: SnapCompare) -> None:
    async def blink(pilot: Pilot[None]) -> None:
        pilot.app.screen.query_one(PetHeader).blink()

    assert snap_compare(child_app(), run_before=blink)


def test_main_screen_monochrome(snap_compare: SnapCompare) -> None:
    app = make_app(
        repo_with(stats=Stats(hunger=20, happiness=45, energy=70), poop_count=1), view=mono()
    )
    assert snap_compare(app)


LIVING_STAGES = [s for s in LifeStage if s is not LifeStage.DEAD]


@pytest.mark.parametrize("stage", LIVING_STAGES)
def test_idle_sprite_per_stage(snap_compare: SnapCompare, stage: LifeStage) -> None:
    app = make_app(repo_with(stage=stage))
    assert snap_compare(app, terminal_size=(60, 20))


@pytest.mark.parametrize("stage", LIVING_STAGES)
def test_idle_sprite_per_stage_light_theme(snap_compare: SnapCompare, stage: LifeStage) -> None:
    app = make_app(repo_with(stage=stage), theme="textual-light")
    assert snap_compare(app, terminal_size=(60, 20))


@pytest.mark.parametrize("variant", [Variant.GOOD, Variant.SCRUFFY])
def test_adult_variants(snap_compare: SnapCompare, variant: Variant) -> None:
    app = make_app(repo_with(stage=LifeStage.ADULT, variant=variant))
    assert snap_compare(app, terminal_size=(60, 20))


def test_sick_pet_with_overlays(snap_compare: SnapCompare) -> None:
    app = make_app(repo_with(sickness_doses=1, poop_count=2))
    assert snap_compare(app)


def test_main_screen_monochrome_light_theme(snap_compare: SnapCompare) -> None:
    app = make_app(
        repo_with(stats=Stats(hunger=20, happiness=45, energy=70), poop_count=1),
        view=mono(),
        theme="textual-light",
    )
    assert snap_compare(app)


def test_terminal_too_small(snap_compare: SnapCompare) -> None:
    assert snap_compare(child_app(), terminal_size=(50, 15))


def test_snapshots_use_the_fixed_clock() -> None:
    # Guard: these snapshots rely on FIXED_NOW being midday (daytime, pet awake).
    assert FIXED_NOW.hour == 12
