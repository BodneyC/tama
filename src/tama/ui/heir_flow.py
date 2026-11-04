"""Hatching the egg a pet left when it died of old age (SPEC §2.8, ADR 0010).

From the memorial (the open pet's egg) or the pet list (any dead pet's egg): the name prompt,
filled in with the next name in the line and locked to the parent's species, then the heir.
"""

import logging
from functools import partial
from typing import TYPE_CHECKING

from tama.domain.lineage import heir_name
from tama.domain.pet import Pet
from tama.errors import (
    InvalidArgumentError,
    NoEggError,
    PetLockedError,
    RosterFullError,
    SaveError,
)
from tama.persistence.roster import PetFile
from tama.ui.screens.new_pet import NewPet, NewPetScreen

if TYPE_CHECKING:
    from tama.ui.app import TamaApp

logger = logging.getLogger(__name__)

EXIT_ERROR = 2


def ask_for_heir(app: "TamaApp", parent: Pet, file: PetFile | None) -> None:
    """Ask for the name of ``parent``'s heir (``file`` is its save in a pet list)."""
    library = app.library
    screen = NewPetScreen(
        app.view,
        parent.species,
        taken=library.name_taken if library is not None else None,
        name=heir_name(parent.name) or "",
        title=f"{parent.name}'s egg is hatching!",
        locked=True,
    )
    app.push_screen(screen, partial(_named, app, file))


def _named(app: "TamaApp", file: PetFile | None, chosen: NewPet | None) -> None:
    if chosen is None:
        _back(app, file)
        return
    try:
        if app.library is not None and file is not None:
            session = app.library.hatch_heir(file, chosen.name)
        elif app.session is not None:
            session = app.session.hand_over(chosen.name)
        else:  # pragma: no cover - the memorial and the pet list always give one
            return
    except (NoEggError, RosterFullError, InvalidArgumentError, PetLockedError) as exc:
        app.notify(str(exc), severity="warning")
        _back(app, file)
        return
    except SaveError as exc:
        logger.exception("Could not hatch the heir")
        app.exit(return_code=EXIT_ERROR, message=f"tama: could not hatch the egg: {exc}")
        return
    app.start(session)


def _back(app: "TamaApp", file: PetFile | None) -> None:
    """Back to where the egg was offered: the memorial, or the pet list."""
    if app.session is not None and not app.session.pet.is_alive:
        app.show_memorial()
    elif app.flow is not None:
        app.flow.show_pets(selected=file)
