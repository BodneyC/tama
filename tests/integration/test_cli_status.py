import os
from pathlib import Path

from typer.testing import CliRunner

from tama.cli import EXIT_ERROR, EXIT_NO_PET, app
from tama.infra.clock import SystemClock
from tama.persistence.repository import JsonSaveRepository
from tama.services.session import GameSession, SessionSettings

runner = CliRunner()


def hatch_egg(path: Path, name: str = "Mochi") -> None:
    GameSession.create(
        name, repo=JsonSaveRepository(path), clock=SystemClock(), settings=SessionSettings()
    )


def test_status_without_a_pet(tmp_path: Path) -> None:
    result = runner.invoke(app, ["--save-path", str(tmp_path / "none.json"), "status"])

    assert result.exit_code == EXIT_NO_PET
    assert "No pet yet" in result.stdout


def test_status_prints_one_line(tmp_path: Path) -> None:
    path = tmp_path / "save.json"
    hatch_egg(path)

    result = runner.invoke(app, ["--save-path", str(path), "status"])

    assert result.exit_code == 0
    assert result.stdout == "Mochi · egg · about to hatch\n"


def test_status_uses_save_path_from_environment() -> None:
    hatch_egg(Path(os.environ["TAMA_SAVE_PATH"]), name="FromEnv")

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert result.stdout.startswith("FromEnv · ")


def test_status_never_modifies_the_save(tmp_path: Path) -> None:
    path = tmp_path / "save.json"
    hatch_egg(path)
    before = path.read_bytes()

    runner.invoke(app, ["--save-path", str(path), "status"])

    assert path.read_bytes() == before
    assert not (tmp_path / "save.json.bak").exists()


def test_status_with_a_corrupt_save(tmp_path: Path) -> None:
    path = tmp_path / "save.json"
    path.write_text("{ nope", encoding="utf-8")

    result = runner.invoke(app, ["--save-path", str(path), "status"])

    assert result.exit_code == EXIT_ERROR
    assert "could not load your pet" in result.stderr


def test_status_with_a_bad_config(tmp_path: Path) -> None:
    Path(os.environ["TAMA_CONFIG_PATH"]).write_text("bell = \n", encoding="utf-8")

    result = runner.invoke(app, ["--save-path", str(tmp_path / "save.json"), "status"])

    assert result.exit_code == EXIT_ERROR
    assert "not valid TOML" in result.stderr
