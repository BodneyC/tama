import runpy
import sys

import pytest
from typer.testing import CliRunner

import tama
from tama.cli import app

runner = CliRunner()


def test_version_flag_prints_version_and_exits_successfully() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == f"tama-go-chi {tama.__version__}"


def test_version_matches_package_metadata() -> None:
    assert tama.__version__ == "0.1.0"


def test_running_without_args_reports_tui_not_yet_available() -> None:
    result = runner.invoke(app, [])

    assert result.exit_code == 1
    assert "not implemented yet" in result.stdout


def test_python_dash_m_entry_point(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["tama", "--version"])

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("tama", run_name="__main__")

    assert exc_info.value.code == 0
