"""Small modal dialogs: help, status and feeding."""

from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from tama.domain.events import Action
from tama.domain.pet import Pet
from tama.domain.stats import STAT_MAX, Stat
from tama.services.describe import format_age
from tama.ui.sprites import load_overlay
from tama.ui.widgets.pet_view import PetView, ViewOptions

HELP_TEXT = """\
f  Feed (meal or snack)      l  Lights on/off
p  Play a game               d  Discipline
c  Clean up                  s  Status
m  Medicine                  ?  This help
h  Holiday (pause/resume)    q  Save and quit

Keep your pet fed, happy and clean. Turn the lights
off when it sleeps, give medicine when it's sick, and
discipline it only when it misbehaves. Going away?
Put a settled pet on holiday and nothing happens to it."""

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
