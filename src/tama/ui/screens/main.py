"""The main screen: the pet, its header, and every care action."""

from collections.abc import Callable, Iterable
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
    LearnedTrick,
    Misbehaved,
    Outcome,
    PauseRefused,
    Refused,
    WeightLeftBand,
    WokeUp,
)
from tama.domain.minigames import GameKind, GameResult
from tama.services.describe import describe_event
from tama.services.session import GameSession
from tama.ui.screens.dialogs import FeedMenu, HelpScreen, StatusScreen
from tama.ui.screens.games import game_screen
from tama.ui.screens.games.select import GameSelectScreen
from tama.ui.screens.journal import JournalScreen
from tama.ui.widgets.pet_header import PetHeader
from tama.ui.widgets.pet_stage import PetStage
from tama.ui.widgets.pet_view import ViewOptions

if TYPE_CHECKING:
    from textual.notifications import SeverityLevel

OTHERS_EVERY_SECONDS = 60
"""How often the other pets are re-checked for the header's ``⚠ +N``."""
MIN_WIDTH = 60
MIN_HEIGHT = 20

NOTABLE_EVENTS = (
    Evolved,
    Died,
    GotSick,
    Misbehaved,
    CareMistake,
    FellAsleep,
    WokeUp,
    WeightLeftBand,
    LearnedTrick,  # an heir growing into a child
)
"""Things worth a toast when they happen by themselves (the rest is visible on screen)."""


class MainScreen(Screen[None]):
    """Shows the pet and handles the care actions."""

    class PetDied(Message):
        """The pet has just died: time for the memorial."""

    class SwitchPet(Message):
        """The player wants to pick another pet (``t``)."""

    class Visit(Message):
        """The player wants to invite another pet over (``v``)."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("f", "feed", "Feed"),
        Binding("p", "play", "Play"),
        Binding("c", "act('clean')", "Clean"),
        Binding("m", "act('medicine')", "Medicine"),
        Binding("l", "act('lights')", "Lights"),
        Binding("d", "act('discipline')", "Discipline"),
        # Rarely needed, and the footer has no room for it at 60 columns: listed in Help.
        Binding("w", "act('wake')", "Wake", show=False),
        Binding("j", "journal", "Journal", show=False),
        Binding("v", "visit", "Visit", show=False),
        Binding("h", "holiday", "Holiday"),
        Binding("t", "switch", "Pets"),
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
        others: Callable[[], int] | None = None,
    ) -> None:
        """Show ``session``'s pet, ticking it every ``tick_interval`` seconds (if given).

        The screen owns the timer so ticking stops as soon as the screen goes away. With
        ``bell``, each new attention call rings the terminal bell once. With several pets,
        ``others`` counts the other pets needing care (checked every minute), and ``t``
        switches pets.
        """
        super().__init__()
        self.session = session
        self._tick_interval = tick_interval
        self._view = view or ViewOptions()
        self._bell = bell
        self._others = others
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
        if self._others is not None:
            self.check_others()
            if self._tick_interval is not None:
                self.set_interval(OTHERS_EVERY_SECONDS, self.check_others)

    def check_others(self) -> None:
        """Show how many other pets need care (read-only; the bell never rings for them)."""
        if self._others is not None:
            self.query_one(PetHeader).show_others(self._others())

    @override
    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Offer ``t`` only when there are other pets to switch to."""
        if action == "switch":
            return self._others is not None
        return True

    def action_switch(self) -> None:
        """Save and go back to the pet list."""
        self.post_message(self.SwitchPet())

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
                urgent = isinstance(event, Died | GotSick | CareMistake | WeightLeftBand)
                severity: SeverityLevel = "warning" if urgent else "information"
                self.notify(describe_event(event), title=pet.name, severity=severity)
        if any(isinstance(event, Died) for event in events):
            self.post_message(self.PetDied())

    def _draw(self, events: Iterable[Event] = ()) -> None:
        pet = self.session.pet
        self.query_one(PetHeader).show(pet, self.session.balance, self.session.tz)
        self.query_one(PetStage).show(pet, events, self.session.balance)
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

        def chosen(kind: GameKind | None) -> None:
            if kind is None:
                return
            self.last_game = kind

            def played(result: GameResult | None) -> None:
                if result is not None:
                    self._report(self.session.finish_game(result, kind))

            self.app.push_screen(game_screen(kind, self.session, self._view), played)

        self.app.push_screen(GameSelectScreen(self.last_game), chosen)

    def action_status(self) -> None:
        """Show detailed stats."""
        self.app.push_screen(StatusScreen(self.session.pet, self.session.balance))

    def action_journal(self) -> None:
        """Read the pet's journal (SPEC §2.9)."""
        self.app.push_screen(
            JournalScreen(self.session.pet.name, self.session.journal, self.session.tz)
        )

    def action_visit(self) -> None:
        """Invite another pet over to play (SPEC §3.2)."""
        self.post_message(self.Visit())

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
