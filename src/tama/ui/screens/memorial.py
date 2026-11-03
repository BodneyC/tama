"""The memorial: a dead pet's gravestone and life story, and a fresh egg (SPEC §2)."""

from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from tama.domain.events import Died
from tama.domain.pet import Pet
from tama.services.describe import describe_event, format_age
from tama.ui.widgets.pet_view import PetView, ViewOptions


def memorial_text(pet: Pet) -> str:
    """Who the pet was and how its life went."""
    lines = [f"{pet.name} the {pet.species}"]
    if pet.cause_of_death is not None:
        lines.append(describe_event(Died(pet.age, pet.cause_of_death)))
    lines += [
        "",
        f"Lived {format_age(pet.age)}",
        f"Care mistakes: {pet.care_mistakes}",
        f"Final weight: {pet.weight} g",
    ]
    return "\n".join(lines)


class MemorialScreen(Screen[bool]):
    """Shown once the pet has died. Dismisses with True to hatch a new egg, False to quit."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("n", "new_egg", "New egg"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, pet: Pet, view: ViewOptions | None = None) -> None:
        """Remember ``pet``, drawing its gravestone with ``view`` options."""
        super().__init__()
        self._pet = pet
        self._view = view or ViewOptions()

    @override
    def compose(self) -> ComposeResult:
        """Build the screen."""
        with Vertical(id="memorial", classes="dialog"):
            yield Static("In loving memory", classes="dialog-title")
            yield PetView(self._view, id="grave")
            yield Static(memorial_text(self._pet), id="memorial-body", markup=False)
        yield Footer(compact=True)

    def on_mount(self) -> None:
        """Show the gravestone."""
        self.query_one(PetView).show(self._pet)

    def action_new_egg(self) -> None:
        """Start again with a new egg."""
        self.dismiss(True)  # noqa: FBT003 - the screen's result, not a flag

    def action_quit(self) -> None:
        """Save and exit."""
        self.dismiss(False)  # noqa: FBT003 - the screen's result, not a flag
