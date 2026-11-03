"""Choosing which pet to play (SPEC §6.1).

Each row is one pet as of now: its name, stage and age, and a mark for how it is doing. The
highlighted pet's sprite and details show beside the list, which fits nine pets in 60×20.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, tzinfo
from enum import StrEnum
from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, OptionList, Static
from textual.widgets.option_list import Option

from tama.domain.attention import AttentionReason
from tama.domain.stage import LifeStage
from tama.persistence.roster import PetFile
from tama.services.describe import format_age, holiday_since
from tama.services.roster import PetSummary
from tama.ui.widgets.pet_view import PetView, ViewOptions

NAME_WIDTH = 16


class PetAction(StrEnum):
    """What the player asked for on the pet select screen."""

    PLAY = "play"
    NEW = "new"
    ARCHIVE = "archive"


@dataclass(frozen=True, slots=True)
class PetChoice:
    """The pet select screen's result (``None`` means quit)."""

    action: PetAction
    file: PetFile | None = None


def mark(row: PetSummary) -> str:
    """A one-character summary: needs care, on holiday, passed away, or unreadable."""
    if row.pet is None:
        return "?"
    if not row.pet.is_alive:
        return "✝"
    if row.pet.on_holiday:
        return "⏸"
    return "⚠" if row.needs_care else " "


def row_text(number: int, row: PetSummary) -> str:
    """``1 Mochi            child   1d 2h ⚠``."""
    name = row.name if len(row.name) <= NAME_WIDTH else row.name[: NAME_WIDTH - 1] + "…"
    if row.pet is None:
        return f"{number} {name:<{NAME_WIDTH}} {'':<6} {'':>6} {mark(row)}"
    stage = "egg" if row.pet.stage is LifeStage.EGG else row.pet.stage.value
    return f"{number} {name:<{NAME_WIDTH}} {stage:<6} {format_age(row.pet.age):>6} {mark(row)}"


def detail_text(row: PetSummary, tz: tzinfo = UTC) -> str:
    """The highlighted pet's details, beside its sprite."""
    pet = row.pet
    if pet is None:
        return f"{row.name}\ncan't be read"
    lines = [pet.name, f"{pet.stage.value} {pet.species}"]
    if not pet.is_alive:
        cause = str(pet.cause_of_death).replace("_", " ")
        lines.append(f"passed away ({cause}) at {format_age(pet.age)}")
    elif pet.paused_since is not None:
        lines.append(f"⏸ on holiday since {holiday_since(pet.paused_since, tz)}")
    elif row.needs:
        reasons = [reason.value for reason in AttentionReason if reason in row.needs]
        lines.append("⚠ " + ", ".join(reasons))
    else:
        lines.append("content")
    return "\n".join(lines)


class PetSelectScreen(Screen[PetChoice | None]):
    """Every pet; dismisses with what to do next, or ``None`` to quit."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter", "play", "Play", show=False),
        Binding("n", "new", "New egg"),
        Binding("a", "archive", "Archive"),
        Binding("q", "quit", "Quit"),
        Binding("escape", "quit", "Quit", show=False),
        *(Binding(str(n), f"pick({n})", show=False) for n in range(1, 10)),
    ]

    def __init__(
        self,
        rows: Sequence[PetSummary],
        view: ViewOptions | None = None,
        *,
        tz: tzinfo = UTC,
        selected: PetFile | None = None,
    ) -> None:
        """List ``rows`` with ``selected`` (else the first, i.e. the last played) highlighted."""
        super().__init__()
        self.rows = list(rows)
        self._view = view or ViewOptions()
        self._tz = tz
        keys = [row.file for row in self.rows]
        self._start = keys.index(selected) if selected in keys else 0

    @override
    def compose(self) -> ComposeResult:
        """Build the screen."""
        with Vertical(id="pet-select"):
            yield Static("Your pets", classes="dialog-title")
            with Horizontal(id="pet-select-body"):
                yield OptionList(
                    *(Option(row_text(n, row)) for n, row in enumerate(self.rows, start=1)),
                    id="pets",
                )
                with Vertical(id="pet-preview"):
                    yield PetView(self._view, id="preview-sprite")
                    yield Static(id="preview-detail", markup=False)
        yield Footer(compact=True)

    def on_mount(self) -> None:
        """Highlight the last pet played."""
        pets = self.query_one(OptionList)
        pets.highlighted = self._start
        pets.focus()
        self._preview(self._start)

    @property
    def selected(self) -> PetSummary:
        """The highlighted pet."""
        index = self.query_one(OptionList).highlighted
        return self.rows[index if index is not None else 0]

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """Show the highlighted pet beside the list."""
        self._preview(event.option_index)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Play the chosen pet."""
        self.dismiss(PetChoice(PetAction.PLAY, self.rows[event.option_index].file))

    def action_play(self) -> None:
        """Play the highlighted pet."""
        self.dismiss(PetChoice(PetAction.PLAY, self.selected.file))

    def action_pick(self, number: int) -> None:
        """Play pet number ``number``."""
        if number <= len(self.rows):
            self.dismiss(PetChoice(PetAction.PLAY, self.rows[number - 1].file))

    def action_new(self) -> None:
        """Hatch another egg."""
        self.dismiss(PetChoice(PetAction.NEW))

    def action_archive(self) -> None:
        """Archive the highlighted pet; only the dead can be archived."""
        row = self.selected
        if row.pet is None or row.pet.is_alive:
            self.notify("Only pets that have passed away can be archived.", severity="warning")
            return
        self.dismiss(PetChoice(PetAction.ARCHIVE, row.file))

    def action_quit(self) -> None:
        """Leave tama."""
        self.dismiss(None)

    def _preview(self, index: int | None) -> None:
        if index is None or not self.rows:
            return
        row = self.rows[index]
        sprite = self.query_one(PetView)
        if row.pet is not None:
            sprite.show(row.pet)
        sprite.display = row.pet is not None
        self.query_one("#preview-detail", Static).update(detail_text(row, self._tz))
