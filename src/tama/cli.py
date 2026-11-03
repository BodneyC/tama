"""Command-line entry point (``tama``)."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from tama import __version__
from tama.errors import ConfigError, SaveError, SaveNotFoundError
from tama.infra.clock import SystemClock, local_timezone
from tama.infra.config import load_config
from tama.infra.paths import resolve_config_path, resolve_save_path
from tama.persistence.repository import JsonSaveRepository
from tama.services.describe import status_line
from tama.services.session import GameSession, SessionSettings

app = typer.Typer(add_completion=False, no_args_is_help=False)

EXIT_NO_PET = 1
EXIT_ERROR = 2


@dataclass(frozen=True, slots=True)
class _Options:
    save_path: Path | None


def _version_callback(value: bool) -> None:  # noqa: FBT001 - signature dictated by Typer
    if value:
        typer.echo(f"tama {__version__}")
        raise typer.Exit


@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    *,
    save_path: Annotated[
        Path | None,
        typer.Option(
            "--save-path", help="Save file to use (default: $TAMA_SAVE_PATH or user data dir)."
        ),
    ] = None,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
) -> None:
    """Look after your terminal pet."""
    del version  # handled eagerly by its callback
    ctx.obj = _Options(save_path=save_path)
    if ctx.invoked_subcommand is None:
        typer.echo("The tama TUI is not implemented yet.")
        raise typer.Exit(code=1)


@app.command()
def status(ctx: typer.Context) -> None:
    """Print a one-line status of your pet (handy for shell prompts). Never modifies the save."""
    options: _Options = ctx.obj
    try:
        config = load_config(resolve_config_path())
    except ConfigError as exc:
        typer.echo(f"tama: {exc}", err=True)
        raise typer.Exit(code=EXIT_ERROR) from exc
    repo = JsonSaveRepository(resolve_save_path(options.save_path))
    settings = SessionSettings.from_config(config, local_timezone())
    try:
        loaded = GameSession.load(repo=repo, clock=SystemClock(), settings=settings)
    except SaveNotFoundError as exc:
        typer.echo("No pet yet. Run `tama` to hatch one.")
        raise typer.Exit(code=EXIT_NO_PET) from exc
    except SaveError as exc:
        typer.echo(f"tama: could not load your pet: {exc}", err=True)
        raise typer.Exit(code=EXIT_ERROR) from exc
    typer.echo(status_line(loaded.session.pet, loaded.session.balance))


def main() -> None:
    """Run the CLI."""
    app()
