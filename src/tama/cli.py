"""Command-line entry point (``tama``)."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from tama import __version__
from tama.domain.events import PauseRefused
from tama.domain.pet import DEFAULT_SPECIES
from tama.errors import ConfigError, InvalidArgumentError, SaveError, SaveNotFoundError
from tama.infra.clock import Clock, ScaledClock, SystemClock, local_timezone
from tama.infra.config import Config, load_config, no_color_requested
from tama.infra.logging import configure_logging
from tama.infra.paths import log_dir, resolve_config_path, resolve_save_path
from tama.persistence.repository import JsonSaveRepository
from tama.services.describe import describe_event, holiday_since, status_line
from tama.services.session import GameSession, SessionSettings
from tama.ui.app import TamaApp
from tama.ui.sprites import available_species
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
    species: Annotated[
        str | None,
        typer.Option(
            "--species",
            metavar="ANIMAL",
            help="Which animal hatches from a new egg (default: tama). See --list-species.",
        ),
    ] = None,
    pause: Annotated[
        bool, typer.Option("--pause", help="Put your pet on holiday (frozen in time) and exit.")
    ] = False,
    resume: Annotated[
        bool, typer.Option("--resume", help="Bring your pet back from holiday and exit.")
    ] = False,
    list_species: Annotated[
        bool, typer.Option("--list-species", help="List the animals you can hatch and exit.")
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
    if list_species:
        typer.echo("\n".join(available_species()))
        raise typer.Exit
    if pause and resume:
        raise typer.BadParameter("choose --pause or --resume, not both", param_hint="--pause")
    if pause or resume:
        _holiday(save_path, pausing=pause)
    if species is not None and species not in available_species():
        choices = ", ".join(available_species())
        raise typer.BadParameter(
            f"unknown animal {species!r}; choose from: {choices}", param_hint="--species"
        )
    try:
        clock: Clock = SystemClock() if speed == 1 else ScaledClock(SystemClock(), speed=speed)
    except InvalidArgumentError as exc:
        raise typer.BadParameter(str(exc), param_hint="--speed") from exc

    config = _load_config().with_overrides(
        bell=False if quiet else None, reduced_motion=True if reduced_motion else None
    )
    repo = JsonSaveRepository(resolve_save_path(save_path))
    if species is not None and not new:
        _refuse_to_change_species(repo, species)
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
        new_pet_species=species or DEFAULT_SPECIES,
        bell=config.bell,
        view=ViewOptions(monochrome=no_color_requested(), reduced_motion=config.reduced_motion),
        theme=config.theme,
    )
    tui.run()
    raise typer.Exit(code=tui.return_code or 0)


def _refuse_to_change_species(repo: JsonSaveRepository, species: str) -> None:
    """A pet's species is fixed at hatching: stop if the saved pet is a different animal."""
    if not repo.exists():
        return
    try:
        pet = repo.load().game.pet
    except SaveError:
        return  # the TUI explains unreadable saves
    if pet.species != species:
        typer.echo(
            f"{pet.name} is a {pet.species}; an animal can't change species.\n"
            f"To start over with a new {species} egg: tama --new --species {species}",
            err=True,
        )
        raise typer.Exit(code=EXIT_ERROR)


def _load_session(save_path: Path | None) -> GameSession:
    """The saved pet, caught up to now; exits with a message if there is none to load."""
    config = _load_config()
    repo = JsonSaveRepository(resolve_save_path(save_path))
    settings = SessionSettings.from_config(config, local_timezone())
    try:
        return GameSession.load(repo=repo, clock=SystemClock(), settings=settings).session
    except SaveNotFoundError as exc:
        typer.echo("No pet yet. Run `tama` to hatch one.")
        raise typer.Exit(code=EXIT_NO_PET) from exc
    except SaveError as exc:
        typer.echo(f"tama: could not load your pet: {exc}", err=True)
        raise typer.Exit(code=EXIT_ERROR) from exc


def _holiday(save_path: Path | None, *, pausing: bool) -> NoReturn:
    """Pause or resume the pet and print one line about it (SPEC §2.6).

    Exits with ``EXIT_ERROR`` if the pet couldn't be paused or saved. Pausing a pet that is
    already on holiday isn't an error.
    """
    configure_logging(log_dir())
    session = _load_session(save_path)
    pet = session.pet
    code = 0
    if pausing and pet.paused_since is not None:
        line = f"already on holiday since {holiday_since(pet.paused_since, session.tz)}"
    else:
        outcome = session.pause() if pausing else session.resume()
        line = "; ".join(map(describe_event, outcome.events)) or "not on holiday"
        if any(isinstance(event, PauseRefused) for event in outcome.events):
            code = EXIT_ERROR
    typer.echo(f"{pet.name}: {line}")
    if session.save_error is not None:
        typer.echo(f"tama: couldn't save: {session.save_error}", err=True)
        code = EXIT_ERROR
    raise typer.Exit(code=code)


@app.command()
def status(ctx: typer.Context) -> None:
    """Print a one-line status of your pet (handy for shell prompts). Never modifies the save."""
    options: _Options = ctx.obj
    session = _load_session(options.save_path)
    typer.echo(status_line(session.pet, session.balance, session.tz))


def main() -> None:
    """Run the CLI."""
    app()
