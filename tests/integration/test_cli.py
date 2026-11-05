import io
import runpy
import sys
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

import tama
from tama import cli
from tama.cli import app

runner = CliRunner()


def test_version_flag_prints_version_and_exits_successfully() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == f"tama {tama.__version__}"


def test_version_matches_package_metadata() -> None:
    pyproject = Path(__file__).parents[2] / "pyproject.toml"

    assert tama.__version__ == tomllib.loads(pyproject.read_text())["project"]["version"]


def test_python_dash_m_entry_point(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["tama", "--version"])

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("tama", run_name="__main__")

    assert exc_info.value.code == 0


def test_output_the_terminal_cant_encode_is_replaced_not_a_crash() -> None:
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1252")  # a Windows pipe

    cli.tolerate_unencodable(stream)
    stream.write("Mochi → Mochi II …")
    stream.flush()

    assert raw.getvalue() == "Mochi ? Mochi II …".encode("cp1252")


def test_streams_that_cant_be_reconfigured_are_left_alone() -> None:
    cli.tolerate_unencodable(io.StringIO())  # e.g. a test runner's capture: nothing to do
