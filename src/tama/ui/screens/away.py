"""The "While you were away" summary: what happened since the game was last open."""

from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from tama.domain.events import Died
from tama.services.describe import format_age
from tama.services.session import CatchUp


def away_text(name: str, away: CatchUp) -> str:
    """The summary: how long the player was gone, what happened, and any pet-sitting."""
    lines = [f"{name}, while you were away ({format_age(away.away_for)}):", ""]
    lines += [f"• {line}" for line in away.summary] or ["• Nothing much happened."]
    died = any(isinstance(event, Died) for event in away.events)
    if away.pet_sitter and not died:
        sat = format_age(away.away_for - away.simulated)
        lines += ["", f"A pet sitter looked after {name} for the last {sat}."]
    return "\n".join(lines)


class AwaySummaryScreen(ModalScreen[None]):
    """What happened while tama was closed (shown on launch when anything did)."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "dismiss", "Close"),
        Binding("escape", "dismiss", "Close", show=False),
    ]

    def __init__(self, name: str, away: CatchUp) -> None:
        """Summarise ``away`` for the pet called ``name``."""
        super().__init__()
        self._text = away_text(name, away)

    @override
    def compose(self) -> ComposeResult:
        """Build the dialog."""
        with Vertical(classes="dialog"):
            yield Static("Welcome back!", classes="dialog-title")
            yield Static(self._text, id="away-body", markup=False)
            yield Static("Press Enter to continue.", classes="dialog-hint")
