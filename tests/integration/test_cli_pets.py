"""Several pets from the shell: --status, --pet, --new, --pause/--resume (SPEC §6.1, §8)."""

import os
import re
from dataclasses import replace
from pathlib import Path
from random import Random
from typing import Any, ClassVar

import pytest
from typer.testing import CliRunner

from tama import cli
from tama.cli import EXIT_ERROR, EXIT_NO_PET, app
from tama.domain.stage import DeathCause, LifeStage
from tama.domain.stats import Stats
from tama.infra.clock import SystemClock
from tama.infra.paths import DATA_DIR_ENV, LEGACY_SAVE, SAVE_PATH_ENV
from tama.persistence.lock import PetLock
from tama.persistence.models import SaveGame
from tama.persistence.repository import JsonSaveRepository
from tama.persistence.roster import PetFile, PetRoster
from tama.services.roster import MAX_PETS
from tests.factories import make_pet

runner = CliRunner()
DEAD: dict[str, Any] = {"stage": LifeStage.DEAD, "cause_of_death": DeathCause.OLD_AGE}


class FakeApp:
    """Stands in for TamaApp: records how it was built and 'runs' instantly."""

    instances: ClassVar[list["FakeApp"]] = []
    return_code: int | None = 0

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        FakeApp.instances.append(self)

    def run(self) -> None:
        pass


@pytest.fixture(autouse=True)
def several_pets_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """No single save file: tama uses the pet list in TAMA_DATA_DIR."""
    monkeypatch.delenv(SAVE_PATH_ENV)
    FakeApp.instances = []
    monkeypatch.setattr(cli, "TamaApp", FakeApp)
    monkeypatch.setattr(cli, "configure_logging", lambda directory: directory / "tama.log")


def data_dir() -> Path:
    return Path(os.environ[DATA_DIR_ENV])


def add(name: str, **overrides: Any) -> PetFile:
    """A pet saved as of the real now, so the CLI has little to catch up."""
    now = SystemClock().now()
    pet = replace(make_pet(**overrides), name=name, updated_at=now, born_at=now)
    if pet.paused_since is not None:
        pet = replace(pet, paused_since=now)
    file = PetRoster(data_dir()).create(name)
    file.repo().save(SaveGame(pet, Random(0).getstate()))
    return file


def snapshot() -> dict[Path, bytes]:
    return {p: p.read_bytes() for p in data_dir().rglob("*") if p.is_file()}


# --- --status -----------------------------------------------------------------------------


def test_status_without_pets() -> None:
    result = runner.invoke(app, ["--status"])

    assert result.exit_code == EXIT_NO_PET
    assert "No pet yet" in result.stdout


def test_status_lists_every_pet_last_played_first(tmp_path: Path) -> None:
    add("Bao")
    mochi = add("Mochi", species="owl")
    add("Old", **DEAD)
    PetRoster(data_dir()).set_last(mochi)

    result = runner.invoke(app, ["--status"])

    assert result.exit_code == 0
    lines = result.stdout.splitlines()
    assert lines[0].startswith("* Mochi · child owl · ")
    assert lines[1].startswith("  Bao · child tama · ")
    assert lines[2].startswith("  Old · tama · passed away")


def test_status_lists_the_dead_last_even_if_played_last() -> None:
    old = add("Aldo", **DEAD)
    add("Bao")
    add("Cy")
    PetRoster(data_dir()).set_last(old)

    lines = runner.invoke(app, ["--status"]).stdout.splitlines()

    assert [line[2:].split(" · ")[0] for line in lines] == ["Bao", "Cy", "Aldo"]
    assert lines[2].startswith("* Aldo · tama · passed away")


def test_status_is_coloured_on_a_terminal() -> None:
    add("Bao", stats=Stats(hunger=10))
    add("Old", **DEAD)

    out = runner.invoke(app, ["--status"], color=True).stdout

    assert "\x1b[1mBao\x1b[0m" in out  # names in bold
    assert "\x1b[31mhunger 10\x1b[0m" in out  # a low need in red
    assert "\x1b[2mOld\x1b[0m" in out  # the dead dimmed


def test_status_respects_no_color(monkeypatch: pytest.MonkeyPatch) -> None:
    add("Bao")
    monkeypatch.setenv("NO_COLOR", "1")

    assert "\x1b[" not in runner.invoke(app, ["--status"], color=True).stdout


def test_status_is_plain_when_piped() -> None:
    add("Bao")

    assert "\x1b[" not in runner.invoke(app, ["--status"]).stdout


def test_status_is_also_a_subcommand() -> None:
    add("Bao")

    assert runner.invoke(app, ["status"]).stdout == runner.invoke(app, ["--status"]).stdout


def test_status_for_one_pet() -> None:
    add("Bao")
    add("Mochi")

    result = runner.invoke(app, ["--status", "--pet", "moc"])

    assert result.exit_code == 0
    assert result.stdout.startswith("Mochi · child tama · ")
    assert len(result.stdout.splitlines()) == 1


def test_status_never_changes_a_save() -> None:
    add("Bao", stats=Stats(hunger=30))
    add("Mochi")
    before = snapshot()

    runner.invoke(app, ["--status"])

    assert snapshot() == before


def test_status_reports_unreadable_pets() -> None:
    add("Bao")
    (data_dir() / "pets" / "broken-abcdef.json").write_text("{ nope", encoding="utf-8")

    result = runner.invoke(app, ["--status"])

    assert result.exit_code == EXIT_ERROR
    assert "broken-abcdef · can't be read" in result.stdout
    assert "Bao · child tama" in result.stdout


def test_an_old_single_save_is_picked_up() -> None:
    legacy = data_dir() / LEGACY_SAVE
    now = SystemClock().now()
    pet = replace(make_pet(), name="Veteran", updated_at=now, born_at=now)
    JsonSaveRepository(legacy).save(SaveGame(pet, Random(0).getstate()))

    result = runner.invoke(app, ["--status"])

    assert result.exit_code == 0
    assert result.stdout.startswith("* Veteran · ")
    assert not legacy.exists()
    assert [f.key[:8] for f in PetRoster(data_dir()).files()] == ["veteran-"]


# --- --pet, --new and --species -----------------------------------------------------------


def test_pet_opens_that_pet() -> None:
    add("Bao")
    mochi = add("Mochi")

    result = runner.invoke(app, ["--pet", "MOCHI"])

    assert result.exit_code == 0
    [instance] = FakeApp.instances
    assert instance.kwargs["open_pet"] == mochi
    assert instance.kwargs["library"] is not None


def words(output: str) -> str:
    """``output`` as plain words: no colour, no box drawing, lines rejoined.

    Typer draws usage errors in a Rich box, coloured on CI and wrapped to the console's width
    (79 columns on Windows), so a phrase can be split anywhere.
    """
    return " ".join(re.sub(r"\x1b\[[0-9;]*m|[│─╭╮╰╯]", " ", output).split())


def test_an_unknown_pet_is_a_usage_error_listing_the_pets() -> None:
    add("Bao")
    add("Mochi")

    result = runner.invoke(app, ["--pet", "Zed"])

    assert result.exit_code == 2
    assert "Your pets: Bao, Mochi." in words(result.output)
    assert not FakeApp.instances


def test_new_adds_a_pet_without_asking() -> None:
    add("Bao")

    result = runner.invoke(app, ["--new", "--species", "owl"])

    assert result.exit_code == 0
    [instance] = FakeApp.instances
    assert instance.kwargs["start_new"] is True
    assert instance.kwargs["new_pet_species"] == "owl"


def test_no_tenth_pet() -> None:
    for i in range(MAX_PETS):
        add(f"Pet{i}")

    result = runner.invoke(app, ["--new"])

    assert result.exit_code == EXIT_ERROR
    assert "nine pets" in result.stderr


def test_a_pet_cannot_change_species() -> None:
    add("Bao")

    result = runner.invoke(app, ["--pet", "Bao", "--species", "owl"])

    assert result.exit_code == EXIT_ERROR
    assert "Bao is a tama" in result.stderr


def test_save_path_plays_one_file_and_cannot_pick_a_pet(tmp_path: Path) -> None:
    result = runner.invoke(app, ["--save-path", str(tmp_path / "s.json"), "--pet", "Bao"])

    assert result.exit_code == 2
    assert "can't pick a pet" in result.output


def test_save_path_still_plays_one_file(tmp_path: Path) -> None:
    result = runner.invoke(app, ["--save-path", str(tmp_path / "s.json")])

    assert result.exit_code == 0
    [instance] = FakeApp.instances
    assert instance.kwargs["repo"].path == tmp_path / "s.json"


# --- --pause / --resume -------------------------------------------------------------------


def test_pause_puts_every_living_pet_on_holiday() -> None:
    bao, mochi = add("Bao"), add("Mochi")
    add("Old", **DEAD)

    result = runner.invoke(app, ["--pause"])

    assert result.exit_code == 0
    assert sorted(result.stdout.splitlines()) == [
        "Bao: Went on holiday",
        "Mochi: Went on holiday",
    ]
    assert all(f.repo().load().game.pet.on_holiday for f in (bao, mochi))


def test_pause_one_pet() -> None:
    bao, mochi = add("Bao"), add("Mochi")

    result = runner.invoke(app, ["--pause", "--pet", "bao"])

    assert result.stdout == "Bao: Went on holiday\n"
    assert bao.repo().load().game.pet.on_holiday
    assert not mochi.repo().load().game.pet.on_holiday


def test_pause_skips_pets_open_elsewhere_and_refusals() -> None:
    open_elsewhere = add("Bao")
    add("Hungry", stats=Stats(hunger=5))
    add("Mochi")
    PetLock(open_elsewhere.path, pid=os.getppid()).acquire()

    result = runner.invoke(app, ["--pause"])

    assert result.exit_code == EXIT_ERROR
    assert sorted(result.stdout.splitlines()) == [
        "Bao: open in another tama; skipped",
        "Hungry: Can't go on holiday: hungry",
        "Mochi: Went on holiday",
    ]
    assert not open_elsewhere.repo().load().game.pet.on_holiday


def test_resume_brings_back_only_pets_on_holiday() -> None:
    add("Bao")
    away = add("Away", paused_since=SystemClock().now())

    result = runner.invoke(app, ["--resume"])

    assert result.exit_code == 0
    [line] = result.stdout.splitlines()
    assert line.startswith("Away: Was on holiday for ")
    assert not away.repo().load().game.pet.on_holiday
    assert not PetLock(away.path).path.exists()


def test_resume_with_nobody_away() -> None:
    add("Bao")

    assert runner.invoke(app, ["--resume"]).stdout == "No pets are on holiday.\n"


def test_holiday_without_pets() -> None:
    assert runner.invoke(app, ["--pause"]).exit_code == EXIT_NO_PET
