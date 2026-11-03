"""What the board games share: the board beside the pet, turns, the pet "thinking", the end.

The rules live in ``tama.domain.minigames``; a screen only draws a game state and turns keys
into moves. The pet's moves come from ``GameSession.pet_move`` so they use the saved RNG.
"""

from collections.abc import Callable
from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from tama.domain.animation import AnimationKey
from tama.domain.minigames import GameResult, Side
from tama.domain.minigames.opponent import BoardGame
from tama.services.session import GameSession
from tama.ui.sprites import load_sprite, species_of
from tama.ui.widgets.pet_view import PetView, ViewOptions

THINK_SECONDS = 0.6
"""How long the pet "thinks" before its move (skipped with reduced motion)."""


def piece_markup(side: Side, *, mono: bool) -> str:
    """A piece as content markup: coloured circles, or ``●``/``○`` in monochrome."""
    if mono:
        return "●" if side is Side.PLAYER else "○"
    return f"[$tama-piece-{side.value}]●[/]"


def highlight(cell: str, *, mono: bool) -> str:
    """A cell picked out (the cursor, or a winning line): a soft background, or reversed."""
    return f"[reverse]{cell}[/]" if mono else f"[bold on $foreground 20%]{cell}[/]"


class BoardGameScreen[G: BoardGame](ModalScreen[GameResult | None]):
    """A board game against the pet. Dismisses with the result, or ``None`` if given up."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "confirm", "Play", show=False),
        Binding("escape", "dismiss", "Give up"),
    ]
    GAME_TITLE: ClassVar[str] = ""
    HINT: ClassVar[str] = ""

    def __init__(self, game: G, session: GameSession, view: ViewOptions | None = None) -> None:
        """Play ``game`` against ``session``'s pet, drawn with ``view`` options."""
        super().__init__()
        self.game = game
        self.busy = False
        """Whether a move is being shown or the pet is thinking (keys are ignored)."""
        self._session = session
        self._view = view or ViewOptions()

    @property
    def mono(self) -> bool:
        """Whether to draw without colour."""
        return self._view.monochrome

    @property
    def animated(self) -> bool:
        """Whether pauses and moving pieces are shown."""
        return self._view.animate and not self._view.reduced_motion

    @override
    def compose(self) -> ComposeResult:
        """Build the dialog: the pet beside the board, then whose turn it is."""
        with Vertical(classes="dialog"):
            yield Static(self.GAME_TITLE, classes="dialog-title")
            with Horizontal(id="game-area"):
                yield PetView(self._view, id="board-pet")
                yield Static(id="board")
            yield Static(id="game-status", markup=False)
            yield Static(self.HINT, classes="dialog-hint", markup=False)

    def on_mount(self) -> None:
        """Show the pet and the empty board."""
        self.query_one(PetView).show(self._session.pet)
        self.redraw()

    def board_markup(self) -> str:
        """The board as content markup."""
        raise NotImplementedError

    def status_text(self) -> str:
        """Whose turn it is, or how the game ended."""
        name = self._session.pet.name
        match self.game.result:
            case GameResult.WIN:
                return "You won! Press Enter."
            case GameResult.DRAW:
                return "It's a draw! Press Enter."
            case GameResult.LOSS:
                return f"{name} won! Press Enter."
            case None if self.game.to_move is Side.PET:
                return f"{name} is thinking…"
            case _:
                return "Your move."

    def redraw(self) -> None:
        """Draw the board and the status line."""
        self.query_one("#board", Static).update(self.board_markup())
        self.query_one("#game-status", Static).update(self.status_text())

    def show(self, game: G) -> None:
        """Show ``game`` as the current state, ending it if it is over."""
        self.game = game
        self.busy = False
        if game.result is not None:
            self._finish()
        else:
            self.redraw()

    def player_move(self, move: int) -> None:
        """Make the player's move if it's their turn and legal, then let the pet answer."""
        if self.busy or move not in self.game.legal_moves() or self.game.to_move is Side.PET:
            return
        self.busy = True
        self.animate_move(self.game.play(move), self._pet_turn)

    def animate_move(self, after: G, done: Callable[[], None]) -> None:
        """Show the move that led to ``after``, then call ``done``. Subclasses may animate."""
        self.game = after
        self.redraw()
        done()

    def after(self, seconds: float, callback: Callable[[], None]) -> None:
        """Call ``callback`` in ``seconds``, or straight away without animation."""
        if self.animated:
            self.set_timer(seconds, callback)
        else:
            callback()

    def player_turn_started(self) -> None:
        """Hook: the pet has moved and the game goes on (e.g. move a cursor off a full column)."""

    def action_confirm(self) -> None:
        """Close the finished game with its result."""
        if self.game.result is not None:
            self.dismiss(self.game.result)

    def _pet_turn(self) -> None:
        if self.game.result is not None:
            self._finish()
            return
        self.after(THINK_SECONDS, self._pet_moves)

    def _pet_moves(self) -> None:
        self.animate_move(self._session.pet_move(self.game), self._player_turn)

    def _player_turn(self) -> None:
        self.busy = False
        if self.game.result is not None:
            self._finish()
            return
        self.player_turn_started()
        self.redraw()

    def _finish(self) -> None:
        self.busy = False
        pet = self._session.pet
        key = AnimationKey.HAPPY if self.game.result is GameResult.WIN else AnimationKey.PLAY
        self.query_one(PetView).set_loop(load_sprite(species_of(pet), pet.variant, pet.stage, key))
        self.redraw()
