"""The several-pets flow (SPEC §6.1): launching into the right pet, the pet list, archiving.

Kept apart from ``TamaApp`` so the app stays about playing one pet; this drives the app's
screens for a ``PetLibrary``.
"""

import logging
from functools import partial
from typing import TYPE_CHECKING

from tama.errors import PetLockedError, SaveError, SaveWriteError
from tama.persistence.roster import PetFile
from tama.services.library import PetLibrary
from tama.services.roster import PetSummary
from tama.ui.heir_flow import ask_for_heir
from tama.ui.screens.confirm import ConfirmScreen
from tama.ui.screens.error import PetErrorScreen
from tama.ui.screens.pet_select import PetAction, PetChoice, PetSelectScreen

if TYPE_CHECKING:
    from tama.ui.app import TamaApp

logger = logging.getLogger(__name__)

EXIT_ERROR = 2
ROSTER_FULL = "You have nine pets already; archive one that has passed away to make room."


class LibraryFlow:
    """Which pet to open, and what to do from the pet list."""

    def __init__(self, app: "TamaApp", library: PetLibrary) -> None:
        """Drive ``app``'s screens for ``library``."""
        self.app = app
        self.library = library

    def launch(self) -> None:
        """Open the pet asked for, the only pet, or the pet list (or ask for a first pet)."""
        if self.app.start_new:
            self.new_pet_if_room()
            return
        if self.app.open_pet is not None:
            self.open(self.app.open_pet, from_list=False)
            return
        rows = self.library.summaries()
        if not rows:
            self.app.ask_for_new_pet()
        elif len(rows) == 1:
            self.open(rows[0].file, from_list=False)
        else:
            self.show_pets()

    def show_pets(self, selected: PetFile | None = None) -> None:
        """Show the pet list, with ``selected`` highlighted (or the name prompt if it's empty)."""
        rows = self.library.summaries()
        if not rows:
            self.app.ask_for_new_pet()
            return
        screen = PetSelectScreen(rows, self.app.view, tz=self.library.tz, selected=selected)
        self.app.push_screen(screen, self.chosen)

    def chosen(self, choice: PetChoice | None) -> None:
        """Act on the pet list's result."""
        if choice is None:
            self.app.exit()
        elif choice.action is PetAction.NEW:
            self.new_pet_if_room()
        elif choice.file is not None and choice.action is PetAction.ARCHIVE:
            question = "Move this pet to the archive? It won't be listed any more."
            if self._row(choice.file).egg_waiting:
                question += " Its egg will be archived with it."
            self.app.push_screen(
                ConfirmScreen("Archive", question), partial(self.archive, choice.file)
            )
        elif choice.file is not None and choice.action is PetAction.HEIR:
            self.heir_if_room(choice.file)
        elif choice.file is not None:
            self.open(choice.file, from_list=True)

    def heir_if_room(self, file: PetFile) -> None:
        """Ask for the name of ``file``'s heir, unless there are nine pets already."""
        row = self._row(file)
        if not self.library.can_add():
            self.app.notify(ROSTER_FULL, severity="warning")
            self.show_pets(selected=file)
        elif row.pet is not None:
            ask_for_heir(self.app, row.pet, file)

    def _row(self, file: PetFile) -> PetSummary:
        return next(row for row in self.library.summaries() if row.file == file)

    def archive(self, file: PetFile, yes: bool | None) -> None:  # noqa: FBT001 - screen result
        """Archive ``file`` if the player said yes, then show the list again."""
        if yes:
            try:
                self.library.archive(file)
            except SaveWriteError as exc:
                self.app.notify(f"Couldn't archive: {exc}", severity="error")
        self.show_pets()

    def new_pet_if_room(self) -> None:
        """Ask for a new pet's name, unless there are nine pets already."""
        if self.library.can_add():
            self.app.ask_for_new_pet()
            return
        message = ROSTER_FULL
        if self.app.session is None and self.library.summaries():
            self.app.notify(message, severity="warning")
            self.show_pets()
        else:
            self.app.exit(return_code=EXIT_ERROR, message=f"tama: {message}")

    def open(self, file: PetFile, *, from_list: bool) -> None:
        """Lock and load ``file``'s pet; ``from_list`` decides where a failure goes back to."""
        try:
            loaded = self.library.open(file)
        except PetLockedError as exc:
            if from_list:
                self.app.notify(str(exc), severity="warning")
                self.show_pets(selected=file)
            else:
                self.app.exit(return_code=EXIT_ERROR, message=f"tama: {exc}")
            return
        except SaveError as exc:
            logger.exception("Could not load %s", file.path)
            self.app.push_screen(PetErrorScreen(exc), partial(self.recover_pet, file))
            return
        self.app.show_loaded(loaded)

    def recover_pet(self, file: PetFile, start_new: bool | None) -> None:  # noqa: FBT001 - screen result
        """After an unreadable pet's error screen: go back, or set it aside for a new pet."""
        if not start_new:
            self.library.close()
            self.show_pets(selected=file)
            return
        try:
            self.library.set_aside()
        except SaveWriteError as exc:
            self.app.notify(f"Couldn't move the files aside: {exc}", severity="error")
            self.show_pets()
            return
        self.new_pet_if_room()
