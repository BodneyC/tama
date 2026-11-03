"""Left or Right: guess which way the pet will look (SPEC §3.1)."""

from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from tama.domain.animation import AnimationKey
from tama.domain.minigames import GameResult
from tama.domain.minigames.left_right import Direction, LeftRightGame
from tama.services.session import GameSession
from tama.ui.sprites import load_sprite, species_of
from tama.ui.widgets.pet_view import PetView, ViewOptions


class LeftRightScreen(ModalScreen[GameResult | None]):
    """Left or Right: guess which way the pet will look. Dismisses with the result."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("left", "guess('left')", "Left"),
        Binding("right", "guess('right')", "Right"),
        Binding("enter", "finish", "Done"),
        Binding("escape", "dismiss", "Give up"),
    ]

    def __init__(self, session: GameSession, view: ViewOptions | None = None) -> None:
        """Start a new game for ``session``'s pet, drawn with ``view`` options."""
        super().__init__()
        self._session = session
        self._view = view or ViewOptions()
        self.game = LeftRightGame()

    @override
    def compose(self) -> ComposeResult:
        """Build the dialog."""
        with Vertical(classes="dialog"):
            yield Static("Left or Right?", classes="dialog-title")
            yield PetView(self._view, id="game-pet")
            yield Static(id="game-body", markup=False)

    def on_mount(self) -> None:
        """Show the pet and the first round."""
        self.query_one(PetView).show(self._session.pet)
        self._render_game()

    def action_guess(self, direction: str) -> None:
        """Play a round: the pet turns the way it looked."""
        if not self.game.is_over:
            self.game = self._session.guess(self.game, Direction(direction))
            last = self.game.last_result
            if last is not None:
                pet = self._session.pet
                key = AnimationKey(f"look_{last.pet_looked.value}")
                pose = load_sprite(species_of(pet), pet.variant, pet.stage, key)
                self.query_one(PetView).set_loop(pose, key)
            self._render_game()

    def action_finish(self) -> None:
        """Close once the game is over."""
        if self.game.result is not None:
            self.dismiss(self.game.result)

    def _render_game(self) -> None:
        name = self._session.pet.name
        game = self.game
        lines = [f"Round {game.round_number}/{game.rounds} · {game.wins} right so far", ""]
        last = game.last_result
        if last is not None:
            verdict = "Right!" if last.correct else "Wrong!"
            lines.append(f"{name} looked {last.pet_looked.value}. {verdict}")
        if game.result is not None:
            outcome = "You won!" if game.result is GameResult.WIN else "You lost."
            lines += ["", f"{outcome} Press Enter."]
        else:
            lines += ["", f"Which way will {name} look?  ←  →"]
        self.query_one("#game-body", Static).update("\n".join(lines))
