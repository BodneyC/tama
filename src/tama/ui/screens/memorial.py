"""The memorial: a dead pet's gravestone, life story and highlights, and a fresh egg (SPEC §2)."""

from datetime import UTC, tzinfo
from enum import StrEnum
from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from tama.domain.events import Died
from tama.domain.journal import EntryKind, Journal, Topic
from tama.domain.pet import Pet
from tama.services.describe import describe_event, family_line, format_age
from tama.services.describe_journal import describe_entry, life_in_numbers
from tama.ui.screens.journal import JournalScreen
from tama.ui.widgets.pet_view import PetView, ViewOptions

MAX_FIRSTS = 3
_STORY = (Topic.HATCHED, Topic.EVOLVED)
"""Life entries told on the memorial (the death is said above them; holidays are left out)."""
_HAPPY_FIRSTS = (Topic.MEAL, Topic.SNACK, Topic.WIN, Topic.TANTRUM, Topic.SICKNESS)
"""Firsts worth remembering on a gravestone (not the first care mistake)."""


class MemorialChoice(StrEnum):
    """What the player chose on the memorial."""

    NEW_EGG = "new_egg"
    HEIR = "heir"
    QUIT = "quit"


def highlights(journal: Journal, firsts_shown: int = MAX_FIRSTS) -> list[str]:
    """The life story, its first few firsts, and the life in numbers (SPEC §2.9)."""
    story = [e for e in journal.entries if e.kind is EntryKind.LIFE and e.topic in _STORY]
    happy = [e for e in journal.entries if e.kind is EntryKind.FIRST and e.topic in _HAPPY_FIRSTS]
    firsts = happy[:firsts_shown]
    return [*map(describe_entry, story + firsts), life_in_numbers(journal.tallies)]


def memorial_text(pet: Pet, journal: Journal | None = None) -> str:
    """Who the pet was and how its life went."""
    lines = [f"{pet.name} the {pet.species}"]
    family = family_line(pet)
    if family is not None:
        lines.append(family)
    if pet.cause_of_death is not None:
        lines.append(describe_event(Died(pet.age, pet.cause_of_death)))
    mistakes = "1 mistake" if pet.care_mistakes == 1 else f"{pet.care_mistakes} mistakes"
    lines.append(f"Lived {format_age(pet.age)} · {mistakes} · {pet.weight} g")
    if journal is not None:  # one first fewer when the family line takes a row (60×20)
        lines += ["", *highlights(journal, MAX_FIRSTS - (family is not None))]
    return "\n".join(lines)


class MemorialScreen(Screen[MemorialChoice]):
    """Shown once the pet has died: a new egg, the egg it left (if any), or quit."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("e", "heir", "Hatch its egg"),
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

    @override
    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Only offer to hatch an egg the pet actually left (SPEC §2.8)."""
        return action != "heir" or self._pet.egg_waiting

    def action_heir(self) -> None:
        """Hatch the egg this pet left."""
        self.dismiss(MemorialChoice.HEIR)

    def action_new_egg(self) -> None:
        """Start again with a new egg."""
        self.dismiss(MemorialChoice.NEW_EGG)

    def action_journal(self) -> None:
        """Read the whole journal."""
        self.app.push_screen(JournalScreen(self._pet.name, self._journal, self._tz))

    def action_quit(self) -> None:
        """Save and exit."""
        self.dismiss(MemorialChoice.QUIT)
