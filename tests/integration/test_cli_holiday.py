"""`tama --pause` / `tama --resume` from the shell (SPEC §2.6, §8)."""

from dataclasses import replace
from pathlib import Path
from random import Random
from typing import Any

from typer.testing import CliRunner

from tama.cli import EXIT_ERROR, EXIT_NO_PET, app
from tama.domain.stats import Stats
from tama.infra.clock import SystemClock
from tama.persistence.models import SaveGame
from tama.persistence.repository import JsonSaveRepository
from tests.factories import make_pet

runner = CliRunner()


def save_pet(path: Path, **overrides: Any) -> JsonSaveRepository:
    """A pet saved as of the real "now", so the CLI has nothing much to catch up."""
    repo = JsonSaveRepository(path)
    pet = make_pet(**overrides)
    pet = replace(pet, updated_at=SystemClock().now(), born_at=SystemClock().now())
    if pet.paused_since is not None:
        pet = replace(pet, paused_since=pet.updated_at)
    repo.save(SaveGame(pet, Random(0).getstate()))
    return repo


def invoke(path: Path, *args: str) -> Any:
    return runner.invoke(app, ["--save-path", str(path), *args])


def test_pause_puts_a_settled_pet_on_holiday(tmp_path: Path) -> None:
    path = tmp_path / "save.json"
    repo = save_pet(path)

    result = invoke(path, "--pause")

    assert result.exit_code == 0
    assert result.stdout == "Mochi: Went on holiday\n"
    assert repo.load().game.pet.on_holiday


def test_pause_refuses_an_unsettled_pet(tmp_path: Path) -> None:
    path = tmp_path / "save.json"
    repo = save_pet(path, stats=Stats(hunger=10))

    result = invoke(path, "--pause")

    assert result.exit_code == EXIT_ERROR
    assert result.stdout == "Mochi: Can't go on holiday: hungry\n"
    assert not repo.load().game.pet.on_holiday


def test_pausing_a_pet_already_on_holiday_is_fine(tmp_path: Path) -> None:
    path = tmp_path / "save.json"
    save_pet(path, paused_since=SystemClock().now())

    result = invoke(path, "--pause")

    assert result.exit_code == 0
    assert result.stdout.startswith("Mochi: already on holiday since ")


def test_resume_brings_a_pet_back(tmp_path: Path) -> None:
    path = tmp_path / "save.json"
    repo = save_pet(path, paused_since=SystemClock().now())

    result = invoke(path, "--resume")

    assert result.exit_code == 0
    assert result.stdout.startswith("Mochi: Was on holiday for ")
    assert not repo.load().game.pet.on_holiday


def test_resume_when_not_on_holiday(tmp_path: Path) -> None:
    path = tmp_path / "save.json"
    save_pet(path)

    result = invoke(path, "--resume")

    assert result.exit_code == 0
    assert result.stdout == "Mochi: not on holiday\n"


def test_status_shows_a_pet_on_holiday(tmp_path: Path) -> None:
    path = tmp_path / "save.json"
    save_pet(path)
    invoke(path, "--pause")

    result = invoke(path, "status")

    assert " · on holiday since " in result.stdout


def test_pause_and_resume_together_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "save.json"
    save_pet(path)

    result = invoke(path, "--pause", "--resume")

    assert result.exit_code != 0
    assert "not both" in result.output


def test_pause_without_a_pet(tmp_path: Path) -> None:
    result = invoke(tmp_path / "none.json", "--pause")

    assert result.exit_code == EXIT_NO_PET
    assert "No pet yet" in result.stdout


def test_pause_with_an_unreadable_save(tmp_path: Path) -> None:
    path = tmp_path / "save.json"
    path.write_text("{ nope", encoding="utf-8")

    result = invoke(path, "--resume")

    assert result.exit_code == EXIT_ERROR
    assert "could not load your pet" in result.stderr
