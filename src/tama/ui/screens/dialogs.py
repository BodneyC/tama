"""Small modal dialogs: help, status, feeding and the Left/Right mini-game."""

from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from tama.domain.animation import AnimationKey
from tama.domain.events import Action
from tama.domain.minigames import GameResult
from tama.domain.minigames.left_right import Direction, LeftRightGame
from tama.domain.pet import Pet
from tama.domain.stats import STAT_MAX, Stat
from tama.services.describe import format_age
from tama.services.session import GameSession
from tama.ui.sprites import load_overlay, load_sprite, species_of
from tama.ui.widgets.pet_view import PetView, ViewOptions

HELP_TEXT = """\
f  Feed (meal or snack)      l  Lights on/off
p  Play Left or Right        d  Discipline
c  Clean up                  s  Status
m  Medicine                  ?  This help
                             q  Save and quit

Keep your pet fed, happy and clean. Turn the lights
off when it sleeps, give medicine when it's sick, and
discipline it only when it misbehaves."""

BAR_WIDTH = 20
_STAT_LABELS = {
    Stat.HUNGER: "Hunger",
    Stat.HAPPINESS: "Happiness",
    Stat.ENERGY: "Energy",
    Stat.HYGIENE: "Hygiene",
    Stat.HEALTH: "Health",
    Stat.DISCIPLINE: "Discipline",
}


def stat_bar(value: int, width: int = BAR_WIDTH) -> str:
    """A text bar like ``███████░░░`` for a stat value."""
    filled = round(value / STAT_MAX * width)
    return "█" * filled + "░" * (width - filled)


def status_text(pet: Pet) -> str:
    """The body of the status dialog."""
    bars = [
        f"{label:<11}{stat_bar(pet.stats[stat])} {pet.stats[stat]:>3}"
        for stat, label in _STAT_LABELS.items()
    ]
    details = [
        f"{'Species':<11}{pet.species}",
        f"{'Stage':<11}{pet.stage.value}",
        f"{'Age':<11}{format_age(pet.age)}",
        f"{'Weight':<11}{pet.weight} g",
        f"{'Mistakes':<11}{pet.care_mistakes}",
    ]
    return "\n".join([f"{pet.name}", "", *bars, "", *details])


class HelpScreen(ModalScreen[None]):
    """Key bindings and a few tips."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss", "Close"),
        Binding("question_mark", "dismiss", "Close", show=False),
    ]

    @override
    def compose(self) -> ComposeResult:
        """Build the dialog."""
        with Vertical(classes="dialog"):
            yield Static("Help", classes="dialog-title")
            yield Static(HELP_TEXT, markup=False)


class StatusScreen(ModalScreen[None]):
    """Detailed stats for the pet."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss", "Close"),
        Binding("s", "dismiss", "Close", show=False),
    ]

    def __init__(self, pet: Pet) -> None:
        """Show ``pet``'s status."""
        super().__init__()
        self._pet = pet

    @override
    def compose(self) -> ComposeResult:
        """Build the dialog."""
        with Vertical(classes="dialog"):
            yield Static("Status", classes="dialog-title")
            yield Static(status_text(self._pet), id="status-body", markup=False)


class FeedMenu(ModalScreen[Action | None]):
    """Choose a meal or a snack (each drawn as a little animated sprite)."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("m", "choose('meal')", "Meal"),
        Binding("s", "choose('snack')", "Snack"),
        Binding("escape", "dismiss", "Cancel"),
    ]

    def __init__(self, view: ViewOptions | None = None) -> None:
        """Create the menu, drawing the food with ``view`` options."""
        super().__init__()
        self._view = view or ViewOptions()

    @override
    def compose(self) -> ComposeResult:
        """Build the dialog."""
        with Vertical(classes="dialog"):
            yield Static("Feed", classes="dialog-title")
            with Horizontal(id="foods"):
                for food, label in (
                    ("meal", "m  Meal\nfills hunger"),
                    ("snack", "s  Snack\ncheers up"),
                ):
                    with Vertical(classes="food"):
                        yield PetView(self._view, id=food)
                        yield Static(label, markup=False)

    def on_mount(self) -> None:
        """Start the food animations."""
        for food in ("meal", "snack"):
            self.query_one(f"#{food}", PetView).set_loop(load_overlay(food))

    def action_choose(self, food: str) -> None:
        """Close the menu with the chosen food."""
        self.dismiss(Action(food))


class MiniGameScreen(ModalScreen[GameResult | None]):
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
