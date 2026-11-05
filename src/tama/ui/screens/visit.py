"""Visits (SPEC §3.2): choosing a pet to invite, and the two pets on the stage together."""

from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen, Screen
from textual.widgets import Footer, OptionList, Static
from textual.widgets.option_list import Option

from tama.domain.events import CareMistake, Died, Event, GotSick, Misbehaved, Outcome
from tama.domain.minigames import GameKind, GameResult
from tama.persistence.roster import PetFile
from tama.services.describe import describe_event, stage_phrase
from tama.services.visit import VisitCandidate, VisitSession
from tama.ui.screens.dialogs import StatusScreen
from tama.ui.screens.games.pet_vs_pet import BOARD_GAMES, PetVsPetScreen
from tama.ui.screens.games.select import GameSelectScreen
from tama.ui.widgets.pet_view import PetView, ViewOptions

if TYPE_CHECKING:
    from textual.notifications import SeverityLevel

GUEST_NEWS = (Died, GotSick, Misbehaved, CareMistake)
"""What happens to the guest by itself worth a toast (the host's news comes from the main
screen, which keeps ticking underneath)."""


def _detail(candidate: VisitCandidate) -> str:
    pet = candidate.summary.pet
    if candidate.reason is not None or pet is None:
        return candidate.reason or ""
    return f"{stage_phrase(pet.stage, pet.variant).split(' ', 1)[1]} {pet.species}"


class VisitPickerScreen(ModalScreen[PetFile | None]):
    """The other pets; those that can't come are greyed out with the reason (SPEC §3.2)."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss", "Close"),
        *(Binding(str(n), f"choose({n})", show=False) for n in range(1, 10)),
    ]

    def __init__(self, host: str, candidates: Sequence[VisitCandidate]) -> None:
        """List ``candidates`` to visit ``host``."""
        super().__init__()
        self._host = host
        self._candidates = list(candidates)

    @override
    def compose(self) -> ComposeResult:
        """Build the dialog."""
        with Vertical(classes="dialog"):
            yield Static(f"Who should visit {self._host}?", classes="dialog-title", markup=False)
            yield OptionList(
                *(
                    Option(
                        f"{n}  {c.summary.name:<16} {_detail(c)}",
                        id=str(n),
                        disabled=not c.can_come,
                    )
                    for n, c in enumerate(self._candidates, start=1)
                ),
                id="visitors",
            )
            yield Static("↑↓ Enter or 1-9 to invite · Esc to close", classes="dialog-hint")

    def on_mount(self) -> None:
        """Highlight the first pet that can come."""
        visitors = self.query_one(OptionList)
        first = next((i for i, c in enumerate(self._candidates) if c.can_come), None)
        visitors.highlighted = first
        visitors.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Invite the selected pet."""
        self.action_choose(int(str(event.option.id)))

    def action_choose(self, number: int) -> None:
        """Invite the pet with this number, or say why it can't come."""
        if number > len(self._candidates):
            return
        candidate = self._candidates[number - 1]
        if candidate.can_come:
            self.dismiss(candidate.summary.file)
        else:
            self.notify(
                f"{candidate.summary.name} can't come: {candidate.reason}", severity="warning"
            )


class WhoseStatusScreen(ModalScreen[int | None]):
    """Pick the host (0) or the guest (1) to see their stats."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss", "Close"),
        Binding("1", "dismiss(0)", show=False),
        Binding("2", "dismiss(1)", show=False),
    ]

    def __init__(self, names: tuple[str, str]) -> None:
        """Offer the two pets' ``names``."""
        super().__init__()
        self._names = names

    @override
    def compose(self) -> ComposeResult:
        """Build the dialog."""
        with Vertical(classes="dialog"):
            yield Static("Whose status?", classes="dialog-title")
            yield OptionList(
                *(Option(f"{n}  {name}", id=str(n - 1)) for n, name in enumerate(self._names, 1)),
                id="whose",
            )
            yield Static("↑↓ Enter or 1-2 · Esc to close", classes="dialog-hint")

    def on_mount(self) -> None:
        """Focus the list."""
        self.query_one(OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Show the chosen pet."""
        self.dismiss(int(str(event.option.id)))


class VisitScreen(Screen[None]):
    """The host (left) and the guest (right) on the stage, each named underneath."""

    class End(Message):
        """The visit is over: the player ended it, or a pet couldn't carry on (``reason``)."""

        def __init__(self, reason: str | None = None, *, switch: bool = False) -> None:
            """``reason`` says why it ended by itself; ``switch`` goes on to the pet list."""
            super().__init__()
            self.reason = reason
            self.switch = switch

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("g", "play", "Play"),
        Binding("enter", "play", "Play", show=False),
        Binding("s", "status", "Status"),
        Binding("v", "end", "End visit"),
        Binding("escape", "end", "End visit", show=False),
        Binding("t", "switch", "Pets", show=False),
        Binding("q", "app.quit_game", "Quit"),
    ]

    def __init__(
        self,
        visit: VisitSession,
        *,
        view: ViewOptions | None = None,
        tick_interval: float | None = None,
    ) -> None:
        """Show ``visit``'s two pets, ticking them every ``tick_interval`` seconds (if given)."""
        super().__init__()
        self.visit = visit
        self._view = view or ViewOptions()
        self._tick_interval = tick_interval
        self.last_game: GameKind | None = None
        self.game_screen: PetVsPetScreen | None = None
        self._ending = False

    @override
    def compose(self) -> ComposeResult:
        """Build the screen."""
        host, guest = self.visit.host.pet.name, self.visit.guest.pet.name
        yield Static(f"{guest} is visiting {host}", id="visit-title", markup=False)
        with Horizontal(id="visit-stage"):
            for side, name in (("host", host), ("guest", guest)):
                with Vertical(classes="visit-half"):
                    yield PetView(self._view, id=f"{side}-sprite")
                    yield Static(name, classes="visit-name", markup=False)
        yield Footer(compact=True)

    def on_mount(self) -> None:
        """Draw both pets greeting each other and start ticking."""
        greetings = self.visit.greetings or (Outcome(self.visit.host.pet),) * 2
        self.draw(greetings[0].events, greetings[1].events)
        if self._tick_interval is not None:
            self.set_interval(self._tick_interval, self.tick)

    def draw(self, host_events: Iterable[Event] = (), guest_events: Iterable[Event] = ()) -> None:
        """Show both pets as they are now, reacting to what just happened to each."""
        for side, pet, events in (
            ("host", self.visit.host.pet, host_events),
            ("guest", self.visit.guest.pet, guest_events),
        ):
            sprite = self.query_one(f"#{side}-sprite", PetView)
            sprite.show(pet)
            sprite.react(events)

    def tick(self) -> None:
        """Bring both pets up to date; end the visit if either can't go on."""
        if self._ending or not self.is_mounted:
            return
        result = self.visit.tick()
        self.draw(result.host.events, result.guest.events)
        guest = self.visit.guest.pet.name
        for event in result.guest.events:
            if isinstance(event, GUEST_NEWS):
                self.notify(describe_event(event), title=guest, severity="warning")
        if result.ended is not None:
            self.end(result.ended.text)

    def end(self, reason: str | None = None, *, switch: bool = False) -> None:
        """Ask for the visit to be ended (once), saying why if it ended by itself."""
        if not self._ending:
            self._ending = True
            self.post_message(self.End(reason, switch=switch))

    def action_end(self) -> None:
        """End the visit: the guest goes home."""
        self.end()

    def action_switch(self) -> None:
        """End the visit and go to the pet list."""
        self.end(switch=True)

    def action_status(self) -> None:
        """Show either pet's stats."""
        sessions = (self.visit.host, self.visit.guest)

        def chosen(index: int | None) -> None:
            if index is not None:
                session = sessions[index]
                self.app.push_screen(StatusScreen(session.pet, session.balance))

        self.app.push_screen(
            WhoseStatusScreen((sessions[0].pet.name, sessions[1].pet.name)), chosen
        )

    def action_play(self) -> None:
        """Choose a board game and watch the two pets play it."""
        if not self.visit.can_play():  # pragma: no cover - the tick ends the visit first
            return

        def chosen(kind: GameKind | None) -> None:
            if kind is None or self._ending:
                return
            self.last_game = kind
            self.game_screen = PetVsPetScreen(kind, self.visit, self._view)
            self.app.push_screen(self.game_screen, lambda result: self._played(kind, result))

        select = GameSelectScreen(self.last_game, kinds=BOARD_GAMES, title="Watch them play")
        self.app.push_screen(select, chosen)

    def _played(self, kind: GameKind, result: GameResult | None) -> None:
        self.game_screen = None
        if result is None or self._ending:
            return  # abandoned: no effect on either pet
        host, guest = self.visit.finish_game(kind, result)
        for outcome, session in ((host, self.visit.host), (guest, self.visit.guest)):
            for event in outcome.events:
                severity: SeverityLevel = "information"
                self.notify(describe_event(event), title=session.pet.name, severity=severity)
        self.draw(host.events, guest.events)
        ended = self.visit.ended()
        if ended is not None:
            self.end(ended.text)
