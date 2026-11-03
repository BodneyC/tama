"""The main screen: the pet, its header, and every care action."""

from collections.abc import Iterable
from typing import TYPE_CHECKING, ClassVar, override

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.screen import Screen
from textual.widgets import Footer, Static

from tama.domain.events import (
    Action,
    CareMistake,
    Died,
    Event,
    Evolved,
    FellAsleep,
    GotSick,
    Misbehaved,
    Outcome,
    Refused,
    WokeUp,
)
from tama.services.describe import describe_event
from tama.services.session import GameSession
from tama.ui.screens.dialogs import FeedMenu, HelpScreen, MiniGameScreen, StatusScreen
from tama.ui.widgets.pet_header import PetHeader
from tama.ui.widgets.pet_stage import PetStage

if TYPE_CHECKING:
    from textual.notifications import SeverityLevel

MIN_WIDTH = 60
MIN_HEIGHT = 20

NOTABLE_EVENTS = (Evolved, Died, GotSick, Misbehaved, CareMistake, FellAsleep, WokeUp)
"""Things worth a toast when they happen by themselves (the rest is visible on screen)."""


class MainScreen(Screen[None]):
    """Shows the pet and handles the care actions."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("f", "feed", "Feed"),
        Binding("p", "play", "Play"),
        Binding("c", "act('clean')", "Clean"),
        Binding("m", "act('medicine')", "Medicine"),
        Binding("l", "act('lights')", "Lights"),
        Binding("d", "act('discipline')", "Discipline"),
        Binding("s", "status", "Status"),
        Binding("question_mark", "help", "Help", key_display="?"),
        Binding("q", "app.quit_game", "Quit"),
    ]

    def __init__(self, session: GameSession) -> None:
        """Show ``session``'s pet."""
        super().__init__()
        self.session = session

    @override
    def compose(self) -> ComposeResult:
        """Build the screen."""
        yield PetHeader()
        yield PetStage()
        yield Static(
            f"Terminal too small: tama needs at least {MIN_WIDTH}x{MIN_HEIGHT}.",
            id="too-small",
            markup=False,
        )
        yield Footer()

    def on_mount(self) -> None:
        """Draw the pet."""
        self._draw()

    def on_resize(self, event: events.Resize) -> None:
        """Swap to the too-small notice when the terminal can't fit the layout."""
        small = event.size.width < MIN_WIDTH or event.size.height < MIN_HEIGHT
        self.set_class(small, "-too-small")

    def refresh_pet(self, new_events: Iterable[Event] = ()) -> None:
        """Redraw the pet and announce notable events that just happened.

        A tick can arrive before the screen has mounted (or while it is being removed); the
        pet is drawn on mount anyway, so drawing is skipped until then.
        """
        if not self.is_mounted:
            return
        self._draw()
        pet = self.session.pet
        for event in new_events:
            if isinstance(event, NOTABLE_EVENTS):
                urgent = isinstance(event, Died | GotSick | CareMistake)
                severity: SeverityLevel = "warning" if urgent else "information"
                self.notify(describe_event(event), title=pet.name, severity=severity)

    def _draw(self) -> None:
        pet = self.session.pet
        self.query_one(PetHeader).show(pet, self.session.balance)
        self.query_one(PetStage).show(pet)

    # --- Actions --------------------------------------------------------------------------

    def action_act(self, action: str) -> None:
        """Perform a simple care action."""
        self._report(self.session.act(Action(action)))

    def action_feed(self) -> None:
        """Ask meal or snack, then feed."""

        def fed(food: Action | None) -> None:
            if food is not None:
                self._report(self.session.act(food))

        self.app.push_screen(FeedMenu(), fed)

    def action_play(self) -> None:
        """Start the mini-game if the pet is willing."""
        outcome = self.session.act(Action.PLAY)
        if outcome.refusal is not None:
            self._report(outcome)
            return

        def played(won: bool | None) -> None:  # noqa: FBT001 - dismiss result, not a flag
            if won is not None:
                self._report(self.session.finish_game(won=won))

        self.app.push_screen(MiniGameScreen(self.session), played)

    def action_status(self) -> None:
        """Show detailed stats."""
        self.app.push_screen(StatusScreen(self.session.pet))

    def action_help(self) -> None:
        """Show key bindings."""
        self.app.push_screen(HelpScreen())

    def _report(self, outcome: Outcome) -> None:
        for event in outcome.events:
            severity: SeverityLevel = "warning" if isinstance(event, Refused) else "information"
            self.notify(describe_event(event), title=self.session.pet.name, severity=severity)
        self.refresh_pet()
        if self.session.save_error is not None:
            self.notify(f"Couldn't save: {self.session.save_error}", severity="error")
