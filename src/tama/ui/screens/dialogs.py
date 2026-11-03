"""Small modal dialogs: help, status, feeding and the Left/Right mini-game."""

from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from tama.domain.events import Action
from tama.domain.minigame import Direction, LeftRightGame
from tama.domain.pet import Pet
from tama.domain.stats import STAT_MAX, Stat
from tama.services.describe import format_age
from tama.services.session import GameSession

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
    """Choose a meal or a snack."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("m", "choose('meal')", "Meal"),
        Binding("s", "choose('snack')", "Snack"),
        Binding("escape", "dismiss", "Cancel"),
    ]

    @override
    def compose(self) -> ComposeResult:
        """Build the dialog."""
        with Vertical(classes="dialog"):
            yield Static("Feed", classes="dialog-title")
            yield Static("m  Meal    (fills hunger)\ns  Snack   (cheers up)", markup=False)

    def action_choose(self, food: str) -> None:
        """Close the menu with the chosen food."""
        self.dismiss(Action(food))


class MiniGameScreen(ModalScreen[bool | None]):
    """Left or Right: guess which way the pet will look. Dismisses with whether you won."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("left", "guess('left')", "Left"),
        Binding("right", "guess('right')", "Right"),
        Binding("enter", "finish", "Done"),
        Binding("escape", "dismiss", "Give up"),
    ]

    def __init__(self, session: GameSession) -> None:
        """Start a new game for ``session``'s pet."""
        super().__init__()
        self._session = session
        self.game = LeftRightGame()

    @override
    def compose(self) -> ComposeResult:
        """Build the dialog."""
        with Vertical(classes="dialog"):
            yield Static("Left or Right?", classes="dialog-title")
            yield Static(id="game-body", markup=False)

    def on_mount(self) -> None:
        """Show the first round."""
        self._render_game()

    def action_guess(self, direction: str) -> None:
        """Play a round."""
        if not self.game.is_over:
            self.game = self._session.guess(self.game, Direction(direction))
            self._render_game()

    def action_finish(self) -> None:
        """Close once the game is over."""
        if self.game.is_over:
            self.dismiss(self.game.won)

    def _render_game(self) -> None:
        name = self._session.pet.name
        game = self.game
        lines = [f"Round {game.round_number}/{game.rounds} · {game.wins} right so far", ""]
        last = game.last_result
        if last is not None:
            verdict = "Right!" if last.correct else "Wrong!"
            lines.append(f"{name} looked {last.pet_looked.value}. {verdict}")
        if game.is_over:
            outcome = "You won!" if game.won else "You lost."
            lines += ["", f"{outcome} Press Enter."]
        else:
            lines += ["", f"Which way will {name} look?  ←  →"]
        self.query_one("#game-body", Static).update("\n".join(lines))
