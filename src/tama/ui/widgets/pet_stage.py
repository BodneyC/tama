"""The stage: the pet's sprite plus what's around it (poop, sickness, sleep)."""

from typing import override

from textual.app import ComposeResult
from textual.containers import Container
from textual.content import Content
from textual.widgets import Static

from tama.domain.animation import looping_animation
from tama.domain.pet import Pet
from tama.ui.sprites import load_sprite


def overlay_text(pet: Pet) -> str:
    """Indicators shown under the pet."""
    parts: list[str] = []
    if pet.is_asleep:
        parts.append("Zzz")
    if pet.is_sick:
        parts.append("☠ sick")
    parts.extend(["💩"] * pet.poop_count)
    return "  ".join(parts)


def sprite_frame(pet: Pet, *, color: bool) -> Content:
    """The frame to show for ``pet``: the first frame of its looping animation."""
    return load_sprite(pet.variant, pet.stage, looping_animation(pet)).frames(color=color)[0]


class PetStage(Container):
    """Centred sprite and indicators; dimmed when the lights are off."""

    def __init__(self, *, monochrome: bool = False) -> None:
        """Draw sprites without colour if ``monochrome`` (e.g. ``NO_COLOR``)."""
        super().__init__()
        self._color = not monochrome

    @override
    def compose(self) -> ComposeResult:
        """Build the stage."""
        yield Static(id="sprite", markup=False)
        yield Static(id="overlay", markup=False)

    def show(self, pet: Pet) -> None:
        """Update the stage for ``pet``."""
        self.query_one("#sprite", Static).update(sprite_frame(pet, color=self._color))
        self.query_one("#overlay", Static).update(overlay_text(pet))
        self.set_class(not pet.lights_on, "lights-off")
