"""The main screen: the pet, its header, and every care action."""

from collections.abc import Iterable
from typing import TYPE_CHECKING, ClassVar, override

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Footer, Static

from tama.domain.attention import attention_reasons, new_attention_calls
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
    PauseRefused,
    Refused,
    WokeUp,
)
from tama.domain.minigames import GameKind, GameResult
from tama.services.describe import describe_event
from tama.services.session import GameSession
from tama.ui.screens.dialogs import FeedMenu, HelpScreen, StatusScreen
from tama.ui.screens.games import game_screen
from tama.ui.screens.games.select import GameSelectScreen
from tama.ui.widgets.pet_header import PetHeader
from tama.ui.widgets.pet_stage import PetStage
from tama.ui.widgets.pet_view import ViewOptions

if TYPE_CHECKING:
    from textual.notifications import SeverityLevel

MIN_WIDTH = 60
MIN_HEIGHT = 20

NOTABLE_EVENTS = (Evolved, Died, GotSick, Misbehaved, CareMistake, FellAsleep, WokeUp)
"""Things worth a toast when they happen by themselves (the rest is visible on screen)."""


class MainScreen(Screen[None]):
    """Shows the pet and handles the care actions."""

    class PetDied(Message):
        """The pet has just died: time for the memorial."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("f", "feed", "Feed"),
        Binding("p", "play", "Play"),
        Binding("c", "act('clean')", "Clean"),
        Binding("m", "act('medicine')", "Medicine"),
        Binding("l", "act('lights')", "Lights"),
        Binding("d", "act('discipline')", "Discipline"),
        Binding("h", "holiday", "Holiday"),
        Binding("s", "status", "Status"),
        Binding("question_mark", "help", "Help", key_display="?"),
        Binding("q", "app.quit_game", "Quit"),
    ]

    def __init__(
        self,
        session: GameSession,
        *,
        tick_interval: float | None = None,
        view: ViewOptions | None = None,
        bell: bool = False,
    ) -> None:
        """Show ``session``'s pet, ticking it every ``tick_interval`` seconds (if given).

        The screen owns the timer so ticking stops as soon as the screen goes away. With
        ``bell``, each new attention call rings the terminal bell once.
        """
        super().__init__()
        self.session = session
        self._tick_interval = tick_interval
        self._view = view or ViewOptions()
        self._bell = bell
        self.last_game: GameKind | None = None
        """The game chosen last time, pre-selected next time."""
        # Needs that are already there when the screen opens don't ring: the player is here.
        self._calls = attention_reasons(session.pet, session.balance)

    @override
    def compose(self) -> ComposeResult:
        """Build the screen."""
        yield PetHeader(self._view)
        yield PetStage(self._view)
        yield Static(
            f"Terminal too small: tama needs at least {MIN_WIDTH}x{MIN_HEIGHT}.",
            id="too-small",
            markup=False,
        )
        yield Footer(compact=True)

    def on_mount(self) -> None:
        """Draw the pet and start ticking."""
        self._draw()
        if self._tick_interval is not None:
            self.set_interval(self._tick_interval, self.tick)

    def tick(self) -> None:
        """Bring the pet up to date, redraw it, and report a newly failing autosave."""
        had_error = self.session.save_error is not None
        catch_up = self.session.tick()
        self.refresh_pet(catch_up.events)
        if self.session.save_error is not None and not had_error:
            self.notify(f"Couldn't save: {self.session.save_error}", severity="error")

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
        events = list(new_events)
        self._draw(events)
        pet = self.session.pet
        for event in events:
            if isinstance(event, NOTABLE_EVENTS):
                urgent = isinstance(event, Died | GotSick | CareMistake)
                severity: SeverityLevel = "warning" if urgent else "information"
                self.notify(describe_event(event), title=pet.name, severity=severity)
        if any(isinstance(event, Died) for event in events):
            self.post_message(self.PetDied())

    def _draw(self, events: Iterable[Event] = ()) -> None:
        pet = self.session.pet
        self.query_one(PetHeader).show(pet, self.session.balance, self.session.tz)
        self.query_one(PetStage).show(pet, events)
        calls = attention_reasons(pet, self.session.balance)
        if self._bell and new_attention_calls(self._calls, calls):
            self.app.bell()
        self._calls = calls

    # --- Actions --------------------------------------------------------------------------

    def action_act(self, action: str) -> None:
        """Perform a simple care action."""
        self._report(self.session.act(Action(action)))

    def action_holiday(self) -> None:
        """Put the pet on holiday, or bring it back (SPEC §2.6)."""
        pet = self.session.pet
        self._report(self.session.resume() if pet.on_holiday else self.session.pause())

    def action_feed(self) -> None:
        """Ask meal or snack, then feed."""
        if self.session.pet.on_holiday:  # say so straight away rather than after the menu
            self._report(self.session.act(Action.MEAL))
            return

        def fed(food: Action | None) -> None:
            if food is not None:
                self._report(self.session.act(food))

        self.app.push_screen(FeedMenu(self._view), fed)

    def action_play(self) -> None:
        """If the pet is willing to play, choose a game and play it."""
        outcome = self.session.act(Action.PLAY)
        if outcome.refusal is not None:
            self._report(outcome)
            return

        def played(result: GameResult | None) -> None:
            if result is not None:
                self._report(self.session.finish_game(result))

        def chosen(kind: GameKind | None) -> None:
            if kind is not None:
                self.last_game = kind
                self.app.push_screen(game_screen(kind, self.session, self._view), played)

        self.app.push_screen(GameSelectScreen(self.last_game), chosen)

    def action_status(self) -> None:
        """Show detailed stats."""
        self.app.push_screen(StatusScreen(self.session.pet))

    def action_help(self) -> None:
        """Show key bindings."""
        self.app.push_screen(HelpScreen())

    def _report(self, outcome: Outcome) -> None:
        for event in outcome.events:
            refused = isinstance(event, Refused | PauseRefused)
            severity: SeverityLevel = "warning" if refused else "information"
            self.notify(describe_event(event), title=self.session.pet.name, severity=severity)
        self._draw(outcome.events)
        if self.session.save_error is not None:
            self.notify(f"Couldn't save: {self.session.save_error}", severity="error")
