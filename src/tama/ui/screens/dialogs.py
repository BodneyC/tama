"""Small modal dialogs: help, status and feeding."""

from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.content import Content
from textual.screen import ModalScreen
from textual.widgets import Static

from tama.domain.balance import DEFAULT_BALANCE, Balance
from tama.domain.events import Action
from tama.domain.pet import Pet
from tama.domain.stage import LifeStage
from tama.domain.stats import STAT_MAX, Stat
from tama.domain.weight import WeightStatus, weight_status
from tama.services.describe import format_age, lineage_text, tricks_text
from tama.ui.sprites import load_overlay
from tama.ui.widgets.pet_view import PetView, ViewOptions

HELP_TEXT = """\
f  Feed (meal or snack)      l  Lights on/off
p  Play a game               d  Discipline
c  Clean up                  s  Status
m  Medicine                  ?  This help
h  Holiday (pause/resume)    t  Switch pets
w  Wake it up (it'll sulk)   q  Save and quit
j  Journal (its life story)  v  Invite a pet over

Keep your pet fed, happy and clean. Turn the lights
off when it sleeps, give medicine when it's sick, and
discipline it only when it misbehaves. Snacks cheer it
up but fatten it; games keep it trim (weight: s).
Waking it up makes it grumpy and tired. Going away?
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


_WEIGHT_MARKS = {WeightStatus.OVER: " ▲", WeightStatus.UNDER: " ▼", WeightStatus.HEALTHY: ""}


def weight_content(pet: Pet, balance: Balance) -> Content:
    """``23 g (12-44)``, marked ``▲``/``▼`` in the warning colour when outside the band."""
    grams = f"{pet.weight} g"
    if pet.stage in (LifeStage.EGG, LifeStage.DEAD):
        return Content(grams)
    low, high = balance.weight_band(pet.stage)
    status = weight_status(pet, balance)
    if status is WeightStatus.HEALTHY:
        return Content(f"{grams} ({low}-{high})")
    warning = "$tama-stat-warning"
    return Content.assemble((grams, warning), f" ({low}-{high})", (_WEIGHT_MARKS[status], warning))


def status_text(pet: Pet, balance: Balance) -> Content:
    """The body of the status dialog (its title is the pet's name)."""
    bars = [
        f"{label:<11}{stat_bar(pet.stats[stat])} {pet.stats[stat]:>3}"
        for stat, label in _STAT_LABELS.items()
    ]
    before_weight = [
        f"{'Species':<11}{pet.species}",
        f"{'Stage':<11}{pet.stage.value}",
        f"{'Age':<11}{format_age(pet.age)}",
    ]
    lineage = lineage_text(pet)
    if lineage is not None:
        before_weight.append(f"{'Family':<11}{lineage}")
    lines = [
        *map(Content, [*bars, "", *before_weight]),
        Content(f"{'Weight':<11}") + weight_content(pet, balance),
        Content(f"{'Mistakes':<11}{pet.care_mistakes}"),
    ]
    tricks = tricks_text(pet, balance)
    if tricks is not None:
        lines.append(Content(f"{'Tricks':<11}{tricks}"))
    return Content("\n").join(lines)


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

    def __init__(self, pet: Pet, balance: Balance = DEFAULT_BALANCE) -> None:
        """Show ``pet``'s status; ``balance`` sets its healthy weight."""
        super().__init__()
        self._pet = pet
        self._balance = balance

    @override
    def compose(self) -> ComposeResult:
        """Build the dialog."""
        with Vertical(classes="dialog"):
            # Titled with the name rather than "Status", so an heir's fits 60x20 (SPEC §5.1).
            yield Static(self._pet.name, classes="dialog-title", markup=False)
            yield Static(status_text(self._pet, self._balance), id="status-body")


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
