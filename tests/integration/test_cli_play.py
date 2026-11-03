"""`tama` with no subcommand launches the TUI with the right wiring (the app itself is faked)."""

import os
from pathlib import Path
from typing import Any, ClassVar

import click
import pytest
from typer.testing import CliRunner

from tama import cli
from tama.cli import EXIT_ERROR, app
from tama.infra.clock import FakeClock, ScaledClock, SystemClock
from tama.infra.config import Config
from tama.infra.paths import CONFIG_PATH_ENV
from tama.persistence.repository import JsonSaveRepository
from tama.services.session import GameSession, SessionSettings
from tama.ui.widgets.pet_view import ViewOptions
from tests.factories import FIXED_NOW

runner = CliRunner()


class FakeApp:
    """Stands in for TamaApp: records how it was built and 'runs' instantly."""

    instances: ClassVar[list["FakeApp"]] = []
    return_code: int | None = 0

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.ran = False
        FakeApp.instances.append(self)

    def run(self) -> None:
        self.ran = True


@pytest.fixture(autouse=True)
def fake_app(monkeypatch: pytest.MonkeyPatch) -> type[FakeApp]:
    FakeApp.instances = []
    FakeApp.return_code = 0
    monkeypatch.setattr(cli, "TamaApp", FakeApp)
    monkeypatch.setattr(cli, "configure_logging", lambda directory: directory / "tama.log")
    return FakeApp


def launched() -> FakeApp:
    assert len(FakeApp.instances) == 1
    instance = FakeApp.instances[0]
    assert instance.ran
    return instance


def test_plain_tama_launches_the_app_with_defaults() -> None:
    result = runner.invoke(app, [])

    assert result.exit_code == 0
    kwargs = launched().kwargs
    assert isinstance(kwargs["clock"], SystemClock)
    assert isinstance(kwargs["repo"], JsonSaveRepository)
    assert kwargs["repo"].path == Path(os.environ["TAMA_SAVE_PATH"])
    assert isinstance(kwargs["settings"], SessionSettings)
    assert kwargs["seed"] is None
    assert kwargs["start_new"] is False
    assert kwargs["bell"] is False
    assert kwargs["view"] == ViewOptions()
    assert kwargs["theme"] is None


def test_no_color_environment_draws_monochrome(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")

    runner.invoke(app, [])

    assert launched().kwargs["view"].monochrome is True


def test_save_path_option(tmp_path: Path) -> None:
    runner.invoke(app, ["--save-path", str(tmp_path / "pet.json")])

    assert launched().kwargs["repo"].path == tmp_path / "pet.json"


def test_speed_uses_a_scaled_clock() -> None:
    runner.invoke(app, ["--speed", "60"])

    assert isinstance(launched().kwargs["clock"], ScaledClock)


def test_invalid_speed_is_a_usage_error() -> None:
    result = runner.invoke(app, ["--speed", "0"])

    assert result.exit_code == 2
    # Typer's error panel may be styled (CI forces colour), so compare without ANSI codes.
    assert "--speed" in click.unstyle(result.stderr)
    assert FakeApp.instances == []


def test_seed_and_new_without_an_existing_pet_skip_the_prompt() -> None:
    result = runner.invoke(app, ["--new", "--seed", "5"])

    assert result.exit_code == 0
    assert launched().kwargs["seed"] == 5
    assert launched().kwargs["start_new"] is True


def existing_pet(path: Path) -> None:
    GameSession.create(
        "Old", repo=JsonSaveRepository(path), clock=FakeClock(FIXED_NOW), settings=SessionSettings()
    )


def test_new_with_an_existing_pet_asks_first(tmp_path: Path) -> None:
    path = tmp_path / "save.json"
    existing_pet(path)

    declined = runner.invoke(app, ["--save-path", str(path), "--new"], input="n\n")

    assert declined.exit_code == 0
    assert "Start over?" in declined.stdout
    assert FakeApp.instances == []

    accepted = runner.invoke(app, ["--save-path", str(path), "--new"], input="y\n")

    assert accepted.exit_code == 0
    assert launched().kwargs["start_new"] is True


def test_flags_override_config(monkeypatch: pytest.MonkeyPatch) -> None:
    Path(os.environ[CONFIG_PATH_ENV]).write_text("bell = true\n", encoding="utf-8")

    runner.invoke(app, ["--quiet", "--reduced-motion"])

    assert launched().kwargs["bell"] is False
    assert launched().kwargs["view"].reduced_motion is True


def test_config_is_used_without_flags() -> None:
    Path(os.environ[CONFIG_PATH_ENV]).write_text("bell = true\n", encoding="utf-8")

    runner.invoke(app, [])

    assert launched().kwargs["bell"] is Config(bell=True).bell


def test_theme_comes_from_config() -> None:
    Path(os.environ[CONFIG_PATH_ENV]).write_text('theme = "nord"\n', encoding="utf-8")

    runner.invoke(app, [])

    assert launched().kwargs["theme"] == "nord"


def test_bad_config_stops_before_launching() -> None:
    Path(os.environ[CONFIG_PATH_ENV]).write_text("volume = 11\n", encoding="utf-8")

    result = runner.invoke(app, [])

    assert result.exit_code == EXIT_ERROR
    assert "volume" in result.stderr
    assert FakeApp.instances == []


def test_app_exit_code_is_propagated() -> None:
    FakeApp.return_code = EXIT_ERROR

    result = runner.invoke(app, [])

    assert result.exit_code == EXIT_ERROR
