"""ROADMAP M6.7 acceptance: three pets (one dead, one from an old save.json) end to end."""

import os
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from random import Random
from typing import Any

import pytest
from typer.testing import CliRunner

from tama.cli import app as cli_app
from tama.domain.stage import DeathCause, LifeStage
from tama.infra.clock import FakeClock, SystemClock
from tama.infra.paths import DATA_DIR_ENV, LEGACY_SAVE, SAVE_PATH_ENV
from tama.persistence.models import SaveGame
from tama.persistence.repository import JsonSaveRepository
from tama.persistence.roster import PetRoster
from tama.services.library import PetLibrary
from tama.services.session import SessionSettings
from tama.ui.screens.main import MainScreen
from tama.ui.screens.pet_select import PetSelectScreen
from tests.factories import make_pet
from tests.ui.helpers import make_library_app


def files_snapshot(directory: Path) -> dict[Path, bytes]:
    return {p: p.read_bytes() for p in directory.rglob("*") if p.is_file()}


async def test_three_pets_one_dead_one_from_an_old_save(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SAVE_PATH_ENV)
    data = Path(os.environ[DATA_DIR_ENV])
    now = SystemClock().now()  # the CLI reads the real clock
    clock = FakeClock(now)

    def saved(name: str, **overrides: Any) -> SaveGame:
        pet = replace(make_pet(**overrides), name=name, updated_at=now, born_at=now)
        return SaveGame(pet, Random(0).getstate())

    JsonSaveRepository(data / LEGACY_SAVE).save(saved("Veteran"))
    roster = PetRoster(data)
    roster.create("Bao").repo().save(saved("Bao"))
    gone: dict[str, Any] = {"stage": LifeStage.DEAD, "cause_of_death": DeathCause.OLD_AGE}
    roster.create("Old Pip").repo().save(saved("Old Pip", **gone))

    # tama --status: every pet as of now, the old save picked up, nothing else changed.
    result = CliRunner().invoke(cli_app, ["--status"])
    assert result.exit_code == 0
    lines = result.stdout.splitlines()
    assert len(lines) == 3
    assert lines[0].startswith("* Veteran · child tama · ")
    assert any(line.startswith("  Old Pip · tama · passed away") for line in lines)
    assert not (data / LEGACY_SAVE).exists()
    before = files_snapshot(data)
    CliRunner().invoke(cli_app, ["--status"])
    assert files_snapshot(data) == before

    # tama: all three offered; play one, then switch to another with t.
    library = PetLibrary(roster, clock=clock, settings=SessionSettings())
    app = make_library_app(library, clock=clock)
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, PetSelectScreen)
        assert [row.name for row in screen.rows] == ["Veteran", "Bao", "Old Pip"]

        await pilot.press("2")
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)
        assert app.session is not None
        assert app.session.pet.name == "Bao"

        clock.advance(timedelta(minutes=5))
        await pilot.press("t")
        await pilot.pause()
        assert isinstance(app.screen, PetSelectScreen)
        assert [row.name for row in app.screen.rows] == ["Bao", "Veteran", "Old Pip"]

        await pilot.press("2")
        await pilot.pause()
        assert app.session is not None
        assert app.session.pet.name == "Veteran"
