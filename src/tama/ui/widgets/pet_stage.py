"""The stage: the animated pet plus what's around it (poop, sickness, sleep)."""

from collections.abc import Iterable
from typing import override

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static

from tama.domain.balance import DEFAULT_BALANCE, Balance
from tama.domain.events import Event
from tama.domain.pet import Pet
from tama.domain.tricks import can_show_off, known_tricks
from tama.ui.sprites import overlay_content
from tama.ui.widgets.pet_view import PetView, ViewOptions


def overlay_names(pet: Pet) -> list[str]:
    """Indicator sprites shown under the pet, in order."""
    if pet.on_holiday:  # frozen: the suitcase says it all
        return ["suitcase"]
    names: list[str] = []
    if pet.is_asleep:
        names.append("zzz")
    if pet.is_sick:
        names.append("sick")
    names.extend(["poop"] * pet.poop_count)
    return names


class PetStage(Container):
    """Centred, animated pet and indicators; dimmed when the lights are off or on holiday."""

    def __init__(self, options: ViewOptions | None = None) -> None:
        """Draw with the given view options."""
        super().__init__()
        self._options = options or ViewOptions()

    @override
    def compose(self) -> ComposeResult:
        """Build the stage."""
        yield PetView(self._options, id="sprite")
        yield Static(id="overlay", markup=False)

    def show(
        self, pet: Pet, events: Iterable[Event] = (), balance: Balance = DEFAULT_BALANCE
    ) -> None:
        """Update the stage for ``pet``, reacting to ``events`` that just happened.

        ``balance`` decides which tricks a content pet knows to show off (SPEC §2.10).
        """
        view = self.query_one(PetView)
        view.show(pet, known_tricks(pet, balance) if can_show_off(pet, balance) else ())
        view.react(events)
        self.query_one("#overlay", Static).update(overlay_content(overlay_names(pet), view.look))
        self.set_class(not pet.lights_on, "lights-off")
        self.set_class(pet.on_holiday, "on-holiday")
