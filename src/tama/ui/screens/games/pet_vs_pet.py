"""Watching two pets play a board game during a visit (SPEC §3.2).

The host plays the first side (its pieces in ``$tama-piece-player``), the guest the second
(``$tama-piece-pet``); each move comes from ``VisitSession.move``, so each pet uses its own
RNG and stage. The screen only paces the moves and draws the board between the two pets.
"""

from typing import TYPE_CHECKING, ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from tama.domain.animation import AnimationKey
from tama.domain.minigames import GameKind, GameResult, Side
from tama.domain.minigames.four_in_a_row import FourInARow
from tama.domain.minigames.tic_tac_toe import TicTacToe
from tama.domain.pet import Pet
from tama.services.describe import GAME_NAMES
from tama.services.visit import VisitSession
from tama.ui.screens.games.four_in_a_row import four_in_a_row_markup
from tama.ui.screens.games.tic_tac_toe import tic_tac_toe_markup
from tama.ui.widgets.pet_view import PetView, ViewOptions

if TYPE_CHECKING:
    from textual.timer import Timer

MOVE_SECONDS = 0.8
"""How long each move is shown before the next pet moves."""
BOARD_GAMES = (GameKind.FOUR_IN_A_ROW, GameKind.TIC_TAC_TOE)
"""The games two pets can play (Left or Right needs a player)."""

type PetGame = FourInARow | TicTacToe


def new_game(kind: GameKind) -> PetGame:
    """An empty board for ``kind`` (a board game)."""
    return FourInARow() if kind is GameKind.FOUR_IN_A_ROW else TicTacToe()


class PetVsPetScreen(ModalScreen[GameResult | None]):
    """A game between the host and the guest. Dismisses with its result (the host's side).

    ``Space`` skips to the end, ``Enter`` closes the finished game, ``Esc`` abandons it.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("space", "skip", "Skip"),
        Binding("enter", "confirm", "Close", show=False),
        Binding("escape", "dismiss", "Stop"),
    ]

    def __init__(
        self,
        kind: GameKind,
        visit: VisitSession,
        view: ViewOptions | None = None,
        *,
        game: PetGame | None = None,
    ) -> None:
        """Start ``kind`` between ``visit``'s pets (or carry on from ``game``, for tests)."""
        super().__init__()
        self.kind = kind
        self.game: PetGame = game or new_game(kind)
        self._visit = visit
        self._view = view or ViewOptions()
        self._timer: Timer | None = None

    @property
    def animated(self) -> bool:
        """Whether the moves are paced (else the game plays out at once)."""
        return self._view.animate and not self._view.reduced_motion

    @override
    def compose(self) -> ComposeResult:
        """Build the dialog: host, board, guest; then the score line."""
        host, guest = self._visit.host.pet.name, self._visit.guest.pet.name
        with Vertical(classes="dialog"):
            yield Static(f"{GAME_NAMES[self.kind]}: {host} vs {guest}", classes="dialog-title")
            with Horizontal(id="game-area"):
                yield PetView(self._view, small=True, id="host-pet")
                yield Static(id="board")
                yield PetView(self._view, small=True, id="guest-pet")
            yield Static(id="game-status", markup=False)
            yield Static("Space skip to the end · Enter close · Esc stop", classes="dialog-hint")

    def on_mount(self) -> None:
        """Show both pets and the board, and start the moves (or play it all out)."""
        self.query_one("#host-pet", PetView).show(self._visit.host.pet)
        self.query_one("#guest-pet", PetView).show(self._visit.guest.pet)
        if self.game.result is not None:
            self._finish()
        elif not self.animated:
            self.action_skip()
        else:
            self.redraw()
            self._timer = self.set_interval(MOVE_SECONDS, self.step)

    def board_markup(self) -> str:
        """The board, host pieces as the player's colour and guest pieces as the pet's."""
        mono = self._view.monochrome
        if isinstance(self.game, FourInARow):
            return four_in_a_row_markup(self.game, None, mono=mono)
        return tic_tac_toe_markup(self.game, None, mono=mono)

    def status_text(self) -> str:
        """Whose move it is, or how the game ended."""
        host, guest = self._visit.host.pet.name, self._visit.guest.pet.name
        match self.game.result:
            case GameResult.WIN:
                return f"{host} won! Press Enter."
            case GameResult.LOSS:
                return f"{guest} won! Press Enter."
            case GameResult.DRAW:
                return "It's a draw! Press Enter."
            case None:
                return f"{host if self.game.to_move is Side.PLAYER else guest}'s move…"

    def redraw(self) -> None:
        """Draw the board and the status line."""
        self.query_one("#board", Static).update(self.board_markup())
        self.query_one("#game-status", Static).update(self.status_text())

    def step(self) -> None:
        """The next pet makes its move."""
        if self.game.result is None:
            self.game = self._visit.move(self.game)
        if self.game.result is not None:
            self._finish()
        else:
            self.redraw()

    def action_skip(self) -> None:
        """Play every remaining move at once."""
        if self.game.result is None:
            self.game = self._visit.play_out(self.game)
            self._finish()

    def action_confirm(self) -> None:
        """Close the finished game with its result."""
        if self.game.result is not None:
            self.dismiss(self.game.result)

    def _finish(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        result = self.game.result
        self._react("#host-pet", self._visit.host.pet, result is GameResult.WIN)
        self._react("#guest-pet", self._visit.guest.pet, result is GameResult.LOSS)
        self.redraw()

    def _react(self, selector: str, pet: Pet, won: bool) -> None:  # noqa: FBT001 - internal
        view = self.query_one(selector, PetView)
        view.set_loop(view.sprite(pet, AnimationKey.HAPPY if won else AnimationKey.PLAY))
