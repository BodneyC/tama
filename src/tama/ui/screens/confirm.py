"""A yes/no question."""

from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static


class ConfirmScreen(ModalScreen[bool]):
    """Asks ``question``; dismisses with True for ``y`` and False for ``n`` or ``Esc``."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("y", "answer(True)", "Yes"),
        Binding("n", "answer(False)", "No"),
        Binding("escape", "answer(False)", "No", show=False),
    ]

    def __init__(self, title: str, question: str) -> None:
        """Ask ``question`` under ``title``."""
        super().__init__()
        self._title = title
        self._question = question

    @override
    def compose(self) -> ComposeResult:
        """Build the dialog."""
        with Vertical(classes="dialog"):
            yield Static(self._title, classes="dialog-title", markup=False)
            yield Static(self._question, markup=False)
            yield Static("y  Yes    n  No", classes="dialog-hint")

    def action_answer(self, yes: bool) -> None:  # noqa: FBT001 - bound to keys
        """Close with the answer."""
        self.dismiss(yes)
