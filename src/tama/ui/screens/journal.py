"""The journal: a pet's life in numbers, then its entries, newest first (SPEC §2.9)."""

from datetime import UTC, tzinfo
from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from tama.domain.journal import Journal
from tama.services.describe import journal_entries, tally_lines

HINT = "↑↓ PgUp PgDn scroll · Esc close"


class JournalScreen(ModalScreen[None]):
    """A scrollable view of one pet's journal; works for living and dead pets alike."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss", "Close"),
        Binding("j", "dismiss", "Close", show=False),
    ]

    def __init__(self, name: str, journal: Journal, tz: tzinfo = UTC) -> None:
        """Show ``name``'s ``journal``, with times in ``tz``."""
        super().__init__()
        self._name = name
        self._journal = journal
        self._tz = tz

    @override
    def compose(self) -> ComposeResult:
        """Build the dialog."""
        with Vertical(id="journal", classes="dialog"):
            yield Static(f"{self._name}'s journal", classes="dialog-title", markup=False)
            yield Static("\n".join(tally_lines(self._journal.tallies)), id="journal-tallies")
            with VerticalScroll(id="journal-scroll"):
                entries = "\n".join(journal_entries(self._journal, self._tz))
                yield Static(entries, id="journal-entries", markup=False)
            yield Static(HINT, classes="dialog-hint")

    def on_mount(self) -> None:
        """Let the arrow and page keys scroll the entries straight away."""
        self.query_one("#journal-scroll").focus()
