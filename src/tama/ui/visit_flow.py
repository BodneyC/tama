"""Inviting another pet over, and seeing it home again (SPEC §3.2, ADR 0011).

``v`` on the main screen checks the host can have a visit, then offers the visit picker; the
chosen pet is borrowed through the library and the visit screen shown. Every way out goes
through ``end_visit``, which saves and unlocks the guest exactly once.
"""

import logging
from functools import partial
from typing import TYPE_CHECKING

from tama.domain.visit import visit_refusals
from tama.errors import (
    InvalidArgumentError,
    PetLockedError,
    SaveError,
    SaveWriteError,
    VisitRefusedError,
)
from tama.persistence.roster import PetFile
from tama.services.describe import visit_refusal_text
from tama.ui.screens.visit import VisitPickerScreen, VisitScreen

if TYPE_CHECKING:
    from tama.ui.app import TamaApp

logger = logging.getLogger(__name__)

NO_OTHER_PETS = "There are no other pets to invite."


def invite(app: "TamaApp") -> None:
    """Offer the other pets to visit the open one, or say why it can't have a visit."""
    session = app.session
    if session is None or app.visit is not None:
        return
    pet = session.pet
    refusals = visit_refusals(pet, session.balance)
    if refusals:
        reason = visit_refusal_text(refusals[0])
        app.notify(f"Can't have a visit: {reason}", title=pet.name, severity="warning")
        return
    candidates = app.library.visit_candidates() if app.library is not None else []
    if not candidates:
        app.notify(NO_OTHER_PETS, title=pet.name)
        return
    app.push_screen(VisitPickerScreen(pet.name, candidates), partial(_chosen, app))


def _chosen(app: "TamaApp", file: PetFile | None) -> None:
    if file is None or app.library is None or app.session is None:
        return
    try:
        visit = app.library.borrow_for_visit(file, app.session)
    except (PetLockedError, VisitRefusedError, InvalidArgumentError) as exc:
        app.notify(str(exc), severity="warning")
        return
    except SaveError as exc:
        logger.exception("Could not load the guest")
        app.notify(f"Couldn't load that pet: {exc}", severity="error")
        return
    app.visit = visit
    app.push_screen(VisitScreen(visit, view=app.view, tick_interval=app.tick_interval))


def end_visit(app: "TamaApp", reason: str | None = None, *, quiet: bool = False) -> None:
    """Send the guest home: saved and unlocked; the visit screen (and anything on it) closes.

    ``reason`` is why it ended by itself; ``quiet`` (quitting, switching pets) says nothing
    unless saving failed. Does nothing if there is no visit.
    """
    visit, app.visit = app.visit, None
    if visit is None:
        return
    guest = visit.guest.pet.name
    try:
        visit.close()
    except SaveWriteError as exc:
        app.notify(f"Couldn't save {guest}: {exc}", severity="error")
    stack = app.screen_stack
    if any(isinstance(screen, VisitScreen) for screen in stack):
        while not isinstance(app.screen, VisitScreen):
            app.pop_screen()
        app.pop_screen()
    if not quiet:
        app.notify(reason or f"{guest} went home", title=guest)
    if app.main is not None:
        app.main.refresh_pet()
