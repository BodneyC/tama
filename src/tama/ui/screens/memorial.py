"""The memorial: a dead pet's gravestone, life story and highlights, and a fresh egg (SPEC §2)."""

from datetime import UTC, tzinfo
from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from tama.domain.events import Died
from tama.domain.journal import EntryKind, Journal, Topic
from tama.domain.pet import Pet
from tama.services.describe import describe_entry, describe_event, format_age, life_in_numbers
from tama.ui.screens.journal import JournalScreen
from tama.ui.widgets.pet_view import PetView, ViewOptions

MAX_FIRSTS = 3
_STORY = (Topic.HATCHED, Topic.EVOLVED)
"""Life entries told on the memorial (the death is said above them; holidays are left out)."""
_HAPPY_FIRSTS = (Topic.MEAL, Topic.SNACK, Topic.WIN, Topic.TANTRUM, Topic.SICKNESS)
"""Firsts worth remembering on a gravestone (not the first care mistake)."""


def highlights(journal: Journal) -> list[str]:
    """The life story, its first few firsts, and the life in numbers (SPEC §2.9)."""
    story = [e for e in journal.entries if e.kind is EntryKind.LIFE and e.topic in _STORY]
    firsts = [e for e in journal.entries if e.kind is EntryKind.FIRST and e.topic in _HAPPY_FIRSTS][
        :MAX_FIRSTS
    ]
    return [*map(describe_entry, story + firsts), life_in_numbers(journal.tallies)]


def memorial_text(pet: Pet, journal: Journal | None = None) -> str:
    """Who the pet was and how its life went."""
    lines = [f"{pet.name} the {pet.species}"]
    if pet.cause_of_death is not None:
        lines.append(describe_event(Died(pet.age, pet.cause_of_death)))
    mistakes = "1 mistake" if pet.care_mistakes == 1 else f"{pet.care_mistakes} mistakes"
    lines.append(f"Lived {format_age(pet.age)} · {mistakes} · {pet.weight} g")
    if journal is not None:
        lines += ["", *highlights(journal)]
    return "\n".join(lines)


class MemorialScreen(Screen[bool]):
    """Shown once the pet has died. Dismisses with True to hatch a new egg, False to quit."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("n", "new_egg", "New egg"),
        Binding("j", "journal", "Journal"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        pet: Pet,
        view: ViewOptions | None = None,
        journal: Journal | None = None,
        tz: tzinfo = UTC,
    ) -> None:
        """Remember ``pet`` and its ``journal``, drawing its gravestone with ``view`` options."""
        super().__init__()
        self._pet = pet
        self._view = view or ViewOptions()
        self._journal = journal or Journal()
        self._tz = tz

    @override
    def compose(self) -> ComposeResult:
        """Build the screen."""
        with Vertical(id="memorial", classes="dialog"):
            yield Static("In loving memory", classes="dialog-title")
            with Horizontal(id="memorial-row"):
                yield PetView(self._view, id="grave")
                yield Static(
                    memorial_text(self._pet, self._journal), id="memorial-body", markup=False
                )
        yield Footer(compact=True)

    def on_mount(self) -> None:
        """Show the gravestone."""
        self.query_one(PetView).show(self._pet)

    def action_new_egg(self) -> None:
        """Start again with a new egg."""
        self.dismiss(True)  # noqa: FBT003 - the screen's result, not a flag

    def action_journal(self) -> None:
        """Read the whole journal."""
        self.app.push_screen(JournalScreen(self._pet.name, self._journal, self._tz))

    def action_quit(self) -> None:
        """Save and exit."""
        self.dismiss(False)  # noqa: FBT003 - the screen's result, not a flag
