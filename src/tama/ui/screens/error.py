"""The save could not be loaded: start a new pet, or quit (SPEC §6)."""

from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from tama.errors import SaveError, UnsupportedSaveVersionError


def error_text(error: SaveError) -> str:
    """What went wrong and what the player can do about it."""
    if isinstance(error, UnsupportedSaveVersionError):
        return (
            f"{error}\n\n"
            "This save is from a newer version of tama, so this\n"
            "version won't touch it. Please upgrade tama to keep\n"
            "playing."
        )
    return (
        f"{error}\n\n"
        "Neither the save nor its backup could be read.\n"
        "Starting a new pet keeps both files, renamed to\n"
        "<name>.corrupt-<time>."
    )


class ErrorScreen(Screen[bool]):
    """Explains why the save can't be loaded. Dismisses with True to start a new pet.

    A save from a newer version of tama only offers quitting: it must never be replaced.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("n", "start_new", "New pet"),
        Binding("q", "quit", "Quit"),
        Binding("escape", "quit", "Quit", show=False),
    ]

    def __init__(self, error: SaveError) -> None:
        """Explain ``error``."""
        super().__init__()
        self.error = error

    @property
    def can_start_new(self) -> bool:
        """Whether replacing the save is allowed."""
        return not isinstance(self.error, UnsupportedSaveVersionError)

    @override
    def compose(self) -> ComposeResult:
        """Build the screen."""
        with Vertical(classes="dialog"):
            yield Static("Your pet couldn't be loaded", classes="dialog-title")
            yield Static(error_text(self.error), id="error-body", markup=False)
        yield Footer(compact=True)

    @override
    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Hide "New pet" when the save must not be replaced."""
        if action == "start_new":
            return self.can_start_new
        return True

    def action_start_new(self) -> None:
        """Move the bad files aside and hatch a new pet."""
        self.dismiss(True)  # noqa: FBT003 - the screen's result, not a flag

    def action_quit(self) -> None:
        """Leave the save alone and exit."""
        self.dismiss(False)  # noqa: FBT003 - the screen's result, not a flag


class PetErrorScreen(ErrorScreen):
    """One unreadable pet among several: going back returns to the pet list (SPEC §6.1)."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("n", "start_new", "Set aside + new pet"),
        Binding("q", "quit", "Back to pets"),
        Binding("escape", "quit", "Back to pets", show=False),
    ]
