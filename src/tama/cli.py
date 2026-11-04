"""Command-line entry point (``tama``).

By default tama keeps several pets in the user data directory (SPEC §6.1). ``--save-path``
(or ``TAMA_SAVE_PATH``) plays exactly one save file instead, as tama always used to.
"""

from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from tama import __version__
from tama.cli_pets import (
    EXIT_ERROR,
    EXIT_NO_PET,
    NO_PET,
    Report,
    holiday_report,
    journal_lines,
    journal_report,
    pause_or_resume,
    status_report,
)
from tama.domain.pet import DEFAULT_SPECIES
from tama.errors import (
    ConfigError,
    InvalidArgumentError,
    SaveError,
    SaveNotFoundError,
    SaveWriteError,
    UnknownPetError,
)
from tama.infra.clock import Clock, ScaledClock, SystemClock, local_timezone
from tama.infra.config import Config, load_config, no_color_requested
from tama.infra.logging import configure_logging
from tama.infra.paths import (
    LEGACY_SAVE,
    log_dir,
    resolve_config_path,
    resolve_data_dir,
    single_save_path,
)
from tama.persistence.repository import JsonSaveRepository
from tama.persistence.roster import PetRoster
from tama.services.describe import status_line
from tama.services.library import PetLibrary
from tama.services.roster import PetSummary, find_pet
from tama.services.session import GameSession, SessionSettings
from tama.ui.app import TamaApp
from tama.ui.sprites import available_species
from tama.ui.widgets.pet_view import ViewOptions

app = typer.Typer(add_completion=False, no_args_is_help=False)

__all__ = ["EXIT_ERROR", "EXIT_NO_PET", "app", "main"]


@dataclass(frozen=True, slots=True)
class _Options:
    save_path: Path | None
    pet: str | None


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


def _settings(config: Config) -> SessionSettings:
    return SessionSettings.from_config(config, local_timezone())


@app.callback(invoke_without_command=True)
def root(  # noqa: PLR0913 - one parameter per CLI option
    ctx: typer.Context,
    *,
    pet: Annotated[
        str | None,
        typer.Option(
            "--pet", metavar="NAME", help="Which pet (a name, or the start of one; any case)."
        ),
    ] = None,
    new: Annotated[
        bool, typer.Option("--new", help="Hatch another egg (up to nine pets).")
    ] = False,
    status: Annotated[
        bool, typer.Option("--status", help="Print one line per pet, as of now, and exit.")
    ] = False,
    pause: Annotated[
        bool, typer.Option("--pause", help="Put your pets on holiday (frozen in time) and exit.")
    ] = False,
    resume: Annotated[
        bool, typer.Option("--resume", help="Bring your pets back from holiday and exit.")
    ] = False,
    species: Annotated[
        str | None,
        typer.Option(
            "--species",
            metavar="ANIMAL",
            help="Which animal hatches from a new egg (default: tama). See --list-species.",
        ),
    ] = None,
    list_species: Annotated[
        bool, typer.Option("--list-species", help="List the animals you can hatch and exit.")
    ] = False,
    save_path: Annotated[
        Path | None,
        typer.Option(
            "--save-path",
            help="Play exactly this one save file, outside your pet list ($TAMA_SAVE_PATH).",
        ),
    ] = None,
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
    """Look after your terminal pets."""
    del version  # handled eagerly by its callback
    ctx.obj = _Options(save_path=save_path, pet=pet)
    if ctx.invoked_subcommand is not None:
        return
    if list_species:
        typer.echo("\n".join(available_species()))
        raise typer.Exit
    if pause and resume:
        raise typer.BadParameter("choose --pause or --resume, not both", param_hint="--pause")
    single = single_save_path(save_path)
    if single is not None and pet is not None:
        raise typer.BadParameter(
            "--save-path plays one file; it can't pick a pet", param_hint="--pet"
        )
    if status:
        _print_status(ctx.obj)
    if pause or resume:
        _holiday(ctx.obj, pausing=pause)
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
    settings = _settings(config)
    configure_logging(log_dir())
    make_app = partial(
        TamaApp,
        clock=clock,
        settings=settings,
        seed=seed,
        start_new=new,
        new_pet_species=species or DEFAULT_SPECIES,
        bell=config.bell,
        view=ViewOptions(monochrome=no_color_requested(), reduced_motion=config.reduced_motion),
        theme=config.theme,
    )
    if single is not None:
        repo = JsonSaveRepository(single)
        _check_single(repo, species=species, new=new)
        tui = make_app(repo=repo)
    else:
        library = _library(clock, settings)
        chosen = _find(library, pet) if pet is not None and not new else None
        _check_library(library, chosen, species=species, new=new)
        tui = make_app(library=library, open_pet=chosen.file if chosen else None)
    tui.run()
    raise typer.Exit(code=tui.return_code or 0)


# --- Several pets -------------------------------------------------------------------------


def _library(clock: Clock, settings: SessionSettings) -> PetLibrary:
    """The pet list in the data directory, after moving in an old single save (SPEC §6.1)."""
    data_dir = resolve_data_dir()
    roster = PetRoster(data_dir)
    try:
        roster.migrate_legacy(data_dir / LEGACY_SAVE)
    except SaveWriteError as exc:
        typer.echo(f"tama: could not move your old save into the pet list: {exc}", err=True)
        raise typer.Exit(code=EXIT_ERROR) from exc
    return PetLibrary(roster, clock=clock, settings=settings)


def _find(library: PetLibrary, query: str) -> PetSummary:
    try:
        return find_pet(library.summaries(), query)
    except UnknownPetError as exc:
        raise typer.BadParameter(str(exc), param_hint="--pet") from exc


def _check_library(
    library: PetLibrary, chosen: PetSummary | None, *, species: str | None, new: bool
) -> None:
    if new and not library.can_add():
        typer.echo("tama: you have nine pets; archive one that has passed away first.", err=True)
        raise typer.Exit(code=EXIT_ERROR)
    if chosen is not None and chosen.pet is not None and species not in (None, chosen.pet.species):
        _wrong_species(chosen.pet.name, chosen.pet.species, species)


def _report(report: Report) -> NoReturn:
    for line in report.out:
        typer.echo(line)
    for line in report.err:
        typer.echo(line, err=True)
    raise typer.Exit(code=report.code)


def _print_status(options: _Options) -> NoReturn:
    """Print each pet's status line as of now; never changes a save."""
    settings = _settings(_load_config())
    single = single_save_path(options.save_path)
    if single is not None:
        session = _load_single(single, settings)
        typer.echo(status_line(session.pet, session.balance, session.tz))
        raise typer.Exit
    library = _library(SystemClock(), settings)
    try:
        _report(status_report(library, options.pet))
    except UnknownPetError as exc:
        raise typer.BadParameter(str(exc), param_hint="--pet") from exc


def _holiday(options: _Options, *, pausing: bool) -> NoReturn:
    """Pause or resume pets, one line each (SPEC §2.6)."""
    configure_logging(log_dir())
    settings = _settings(_load_config())
    single = single_save_path(options.save_path)
    if single is not None:
        session = _load_single(single, settings)
        line, failed = pause_or_resume(session, pausing=pausing)
        _report(Report([f"{session.pet.name}: {line}"], code=EXIT_ERROR if failed else 0))
    library = _library(SystemClock(), settings)
    try:
        _report(holiday_report(library, options.pet, pausing=pausing))
    except UnknownPetError as exc:
        raise typer.BadParameter(str(exc), param_hint="--pet") from exc


# --- One save file ------------------------------------------------------------------------


def _load_single(path: Path, settings: SessionSettings) -> GameSession:
    """The pet in ``path``, caught up to now; exits with a message if there is none."""
    try:
        return GameSession.load(
            repo=JsonSaveRepository(path), clock=SystemClock(), settings=settings
        ).session
    except SaveNotFoundError as exc:
        typer.echo(NO_PET)
        raise typer.Exit(code=EXIT_NO_PET) from exc
    except SaveError as exc:
        typer.echo(f"tama: could not load your pet: {exc}", err=True)
        raise typer.Exit(code=EXIT_ERROR) from exc


def _check_single(repo: JsonSaveRepository, *, species: str | None, new: bool) -> None:
    """``--new`` replaces the one pet (after asking); ``--species`` can't change its animal."""
    if new and repo.exists():
        replace = typer.confirm(
            "Start over? Your current pet will be replaced (the old save is kept as a backup).",
            default=False,
        )
        if not replace:
            raise typer.Exit
    if species is None or new or not repo.exists():
        return
    try:
        pet = repo.load().game.pet
    except SaveError:
        return  # the TUI explains unreadable saves
    if pet.species != species:
        _wrong_species(pet.name, pet.species, species)


def _wrong_species(name: str, has: str, asked: str) -> NoReturn:
    typer.echo(
        f"{name} is a {has}; an animal can't change species.\n"
        f"To hatch a new {asked} egg: tama --new --species {asked}",
        err=True,
    )
    raise typer.Exit(code=EXIT_ERROR)


@app.command()
def status(ctx: typer.Context) -> None:
    """Same as --status: one line per pet, as of now (handy for shell prompts)."""
    _print_status(ctx.obj)


@app.command()
def journal(
    ctx: typer.Context,
    pet: Annotated[
        str | None,
        typer.Option("--pet", help="Whose journal (default: the pet played last)."),
    ] = None,
) -> None:
    """Print a pet's journal as of now: tallies, then entries newest first (read-only)."""
    options: _Options = ctx.obj
    query = pet if pet is not None else options.pet
    settings = _settings(_load_config())
    single = single_save_path(options.save_path)
    if single is not None:
        session = _load_single(single, settings)
        _report(Report(journal_lines(session.pet.name, session.journal, session.tz)))
    library = _library(SystemClock(), settings)
    try:
        _report(journal_report(library, query))
    except UnknownPetError as exc:
        raise typer.BadParameter(str(exc), param_hint="--pet") from exc


def main() -> None:
    """Run the CLI."""
    app()
