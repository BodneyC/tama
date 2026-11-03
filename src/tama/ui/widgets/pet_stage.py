"""The stage: the pet's sprite plus what's around it (poop, sickness, sleep)."""

from typing import override

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static

from tama.domain.animation import looping_animation
from tama.domain.pet import Pet
from tama.ui.sprites import load_frames


def overlay_text(pet: Pet) -> str:
    """Indicators shown under the pet."""
    parts: list[str] = []
    if pet.is_asleep:
        parts.append("Zzz")
    if pet.is_sick:
        parts.append("☠ sick")
    parts.extend(["💩"] * pet.poop_count)
    return "  ".join(parts)


def sprite_text(pet: Pet) -> str:
    """The frame to show for ``pet``. A single static frame until animation lands (M5)."""
    return load_frames(pet.variant, pet.stage, looping_animation(pet))[0]


class PetStage(Container):
    """Centred sprite and indicators; dimmed when the lights are off."""

    @override
    def compose(self) -> ComposeResult:
        """Build the stage."""
        yield Static(id="sprite", markup=False)
        yield Static(id="overlay", markup=False)

    def show(self, pet: Pet) -> None:
        """Update the stage for ``pet``."""
        self.query_one("#sprite", Static).update(sprite_text(pet))
        self.query_one("#overlay", Static).update(overlay_text(pet))
        self.set_class(not pet.lights_on, "lights-off")
