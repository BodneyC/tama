"""Command-line entry point (``tama``)."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from tama import __version__
from tama.errors import ConfigError, InvalidArgumentError, SaveError, SaveNotFoundError
from tama.infra.clock import Clock, ScaledClock, SystemClock, local_timezone
from tama.infra.config import Config, load_config, no_color_requested
from tama.infra.logging import configure_logging
from tama.infra.paths import log_dir, resolve_config_path, resolve_save_path
from tama.persistence.repository import JsonSaveRepository
from tama.services.describe import status_line
from tama.services.session import GameSession, SessionSettings
from tama.ui.app import TamaApp
from tama.ui.widgets.pet_view import ViewOptions

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


def _load_config() -> Config:
    try:
        return load_config(resolve_config_path())
    except ConfigError as exc:
        typer.echo(f"tama: {exc}", err=True)
        raise typer.Exit(code=EXIT_ERROR) from exc


@app.callback(invoke_without_command=True)
def root(  # noqa: PLR0913 - one parameter per CLI option
    ctx: typer.Context,
    *,
    save_path: Annotated[
        Path | None,
        typer.Option(
            "--save-path", help="Save file to use (default: $TAMA_SAVE_PATH or user data dir)."
        ),
    ] = None,
    new: Annotated[
        bool, typer.Option("--new", help="Start over with a new egg (asks first).")
    ] = False,
    reduced_motion: Annotated[
        bool, typer.Option("--reduced-motion", help="Keep animation to a minimum.")
    ] = False,
    quiet: Annotated[bool, typer.Option("--quiet", help="Never ring the terminal bell.")] = False,
    speed: Annotated[
        float, typer.Option("--speed", hidden=True, help="Debug: run time this many times faster.")
    ] = 1.0,
    seed: Annotated[
        int | None, typer.Option("--seed", hidden=True, help="Debug: RNG seed for a new pet.")
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
    if ctx.invoked_subcommand is not None:
        return
    try:
        clock: Clock = SystemClock() if speed == 1 else ScaledClock(SystemClock(), speed=speed)
    except InvalidArgumentError as exc:
        raise typer.BadParameter(str(exc), param_hint="--speed") from exc

    config = _load_config().with_overrides(
        bell=False if quiet else None, reduced_motion=True if reduced_motion else None
    )
    repo = JsonSaveRepository(resolve_save_path(save_path))
    if new and repo.exists():
        replace = typer.confirm(
            "Start over? Your current pet will be replaced (the old save is kept as a backup).",
            default=False,
        )
        if not replace:
            raise typer.Exit
    configure_logging(log_dir())
    tui = TamaApp(
        repo=repo,
        clock=clock,
        settings=SessionSettings.from_config(config, local_timezone()),
        seed=seed,
        start_new=new,
        bell=config.bell,
        view=ViewOptions(monochrome=no_color_requested(), reduced_motion=config.reduced_motion),
        theme=config.theme,
    )
    tui.run()
    raise typer.Exit(code=tui.return_code or 0)


@app.command()
def status(ctx: typer.Context) -> None:
    """Print a one-line status of your pet (handy for shell prompts). Never modifies the save."""
    options: _Options = ctx.obj
    config = _load_config()
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
