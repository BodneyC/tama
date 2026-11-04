"""``tama journal``: a pet's journal from the shell, read-only (SPEC §2.9, §8)."""

from pathlib import Path
from random import Random

import pytest
from typer.testing import CliRunner

from tama import cli
from tama.cli import EXIT_ERROR, EXIT_NO_PET, app
from tama.infra.paths import SAVE_PATH_ENV
from tama.persistence.models import SaveGame
from tama.persistence.repository import JsonSaveRepository
from tama.persistence.roster import PetFile, PetRoster
from tests.factories import make_journal, make_pet
from tests.integration.test_cli_pets import add, data_dir, snapshot

runner = CliRunner()


@pytest.fixture(autouse=True)
def several_pets_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SAVE_PATH_ENV)
    monkeypatch.setattr(cli, "configure_logging", lambda directory: directory / "tama.log")


def with_journal(name: str) -> PetFile:
    file = add(name)
    game = file.repo().load().game
    file.repo().save(SaveGame(game.pet, game.rng_state, make_journal()))
    return file


def test_journal_without_pets() -> None:
    result = runner.invoke(app, ["journal"])

    assert result.exit_code == EXIT_NO_PET
    assert "No pet yet" in result.stdout


def test_journal_prints_the_last_played_pet_newest_first() -> None:
    with_journal("Bao")
    PetRoster(data_dir()).set_last(with_journal("Mochi"))

    result = runner.invoke(app, ["journal"])

    assert result.exit_code == 0
    lines = result.stdout.splitlines()
    assert lines[0] == "Mochi's journal"
    assert lines[1].startswith("Meals 1 · snacks 0")
    assert lines[-1].endswith("Hatched")
    assert "Passed away peacefully of old age" in lines[lines.index("") + 1]


@pytest.mark.parametrize("args", [["journal", "--pet", "ba"], ["--pet", "ba", "journal"]])
def test_journal_for_another_pet(args: list[str]) -> None:
    with_journal("Bao")
    add("Mochi")

    result = runner.invoke(app, args)

    assert result.exit_code == 0
    assert result.stdout.startswith("Bao's journal\n")


def test_journal_of_an_unknown_pet_is_a_usage_error() -> None:
    add("Bao")

    result = runner.invoke(app, ["journal", "--pet", "zed"])

    assert result.exit_code == 2
    assert "Your pets: Bao." in result.output


def test_journal_of_an_unreadable_pet() -> None:
    add("Bao")
    (data_dir() / "pets" / "broken-abcdef.json").write_text("{ nope", encoding="utf-8")

    result = runner.invoke(app, ["journal", "--pet", "broken"])

    assert result.exit_code == EXIT_ERROR
    assert "broken-abcdef can't be read" in result.stderr


def test_journal_never_changes_a_save() -> None:
    with_journal("Bao")
    before = snapshot()

    runner.invoke(app, ["journal"])

    assert snapshot() == before


def test_journal_of_one_save_file(tmp_path: Path) -> None:
    path = tmp_path / "one.json"
    JsonSaveRepository(path).save(SaveGame(make_pet(), Random(0).getstate(), make_journal()))

    result = runner.invoke(app, ["--save-path", str(path), "journal"])

    assert result.exit_code == 0
    assert result.stdout.startswith("Mochi's journal\n")
