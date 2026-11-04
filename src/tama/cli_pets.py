"""What ``tama --status`` and ``tama --pause``/``--resume`` print (SPEC §6.1, §8).

Each function returns the lines to print and the exit code, so the Typer layer in ``cli.py``
only parses options and echoes.
"""

from dataclasses import dataclass, field
from datetime import tzinfo

from tama.domain.events import PauseRefused
from tama.domain.journal import Journal
from tama.errors import PetLockedError, SaveError
from tama.services.describe import (
    describe_event,
    holiday_since,
    journal_entries,
    status_line,
    tally_lines,
)
from tama.services.library import PetLibrary
from tama.services.roster import PetSummary, find_pet
from tama.services.session import GameSession

EXIT_OK = 0
EXIT_NO_PET = 1
EXIT_ERROR = 2
NO_PET = "No pet yet. Run `tama` to hatch one."


@dataclass(frozen=True, slots=True)
class Report:
    """Lines for stdout, lines for stderr, and the exit code."""

    out: list[str] = field(default_factory=list)
    err: list[str] = field(default_factory=list)
    code: int = EXIT_OK


def pause_or_resume(session: GameSession, *, pausing: bool) -> tuple[str, bool]:
    """Pause or resume ``session``'s pet: the line to print and whether it failed.

    Pausing a pet that is already on holiday isn't a failure.
    """
    pet = session.pet
    if pausing and pet.paused_since is not None:
        return f"already on holiday since {holiday_since(pet.paused_since, session.tz)}", False
    outcome = session.pause() if pausing else session.resume()
    line = "; ".join(map(describe_event, outcome.events)) or "not on holiday"
    failed = any(isinstance(event, PauseRefused) for event in outcome.events)
    if session.save_error is not None:
        line += f" (but couldn't save: {session.save_error})"
        failed = True
    return line, failed


def status_report(library: PetLibrary, query: str | None = None) -> Report:
    """One line per pet as of now, the last played first and marked ``*`` (read-only).

    Raises:
        UnknownPetError: If ``query`` doesn't name exactly one pet.
    """
    rows = library.summaries()
    if not rows:
        return Report([NO_PET], code=EXIT_NO_PET)
    chosen = [find_pet(rows, query)] if query is not None else rows
    out = []
    for row in chosen:
        marker = "" if query is not None else ("* " if row.last else "  ")
        out.append(marker + _status(library, row))
    unreadable = any(row.pet is None for row in chosen)
    return Report(out, code=EXIT_ERROR if unreadable else EXIT_OK)


def journal_lines(name: str, journal: Journal, tz: tzinfo) -> list[str]:
    """``name``'s journal as plain text: tallies, a blank line, then entries newest first."""
    return [f"{name}'s journal", *tally_lines(journal.tallies), "", *journal_entries(journal, tz)]


def journal_report(library: PetLibrary, query: str | None = None) -> Report:
    """One pet's journal as of now (read-only): ``query``'s, else the last played pet's.

    Raises:
        UnknownPetError: If ``query`` doesn't name exactly one pet.
    """
    rows = library.summaries()
    if not rows:
        return Report([NO_PET], code=EXIT_NO_PET)
    row = find_pet(rows, query) if query is not None else rows[0]  # last played comes first
    if row.pet is None:
        return Report(err=[f"tama: {row.name} can't be read ({row.error})"], code=EXIT_ERROR)
    return Report(journal_lines(row.pet.name, row.journal, library.tz))


def holiday_report(library: PetLibrary, query: str | None, *, pausing: bool) -> Report:
    """Pause (or resume) one pet, or every pet that can be: one line each.

    Pets open in another tama are skipped and make the exit code 2, as do refusals.

    Raises:
        UnknownPetError: If ``query`` doesn't name exactly one pet.
    """
    rows = library.summaries()
    if not rows:
        return Report([NO_PET], code=EXIT_NO_PET)
    if query is not None:
        targets = [find_pet(rows, query)]
    elif pausing:
        targets = [row for row in rows if row.alive]
    else:
        targets = [row for row in rows if row.pet is not None and row.pet.on_holiday]
    if not targets:
        return Report(["No pets to put on holiday." if pausing else "No pets are on holiday."])
    out, code = [], EXIT_OK
    for row in targets:
        line, failed = _pause_or_resume(library, row, pausing=pausing)
        out.append(f"{row.name}: {line}")
        code = EXIT_ERROR if failed else code
    return Report(out, code=code)


def _pause_or_resume(library: PetLibrary, row: PetSummary, *, pausing: bool) -> tuple[str, bool]:
    try:
        with library.borrow(row.file) as session:
            return pause_or_resume(session, pausing=pausing)
    except PetLockedError:
        return "open in another tama; skipped", True
    except SaveError as exc:
        return f"can't be read ({exc})", True


def _status(library: PetLibrary, row: PetSummary) -> str:
    if row.pet is None:
        return f"{row.name} · can't be read ({row.error})"
    return status_line(row.pet, library.balance, library.tz)
