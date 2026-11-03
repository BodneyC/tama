"""Which animation the pet should be showing (SPEC §5.2).

This decides *what* to play; frame playback and timing live in the UI. Blinking and
wandering are cosmetic variations of ``IDLE`` chosen by the UI.
"""

from enum import StrEnum

from tama.domain.events import (
    Ate,
    Cleaned,
    Disciplined,
    Event,
    Evolved,
    MedicineGiven,
    Played,
    Refused,
)
from tama.domain.pet import Pet
from tama.domain.stage import LifeStage


class AnimationKey(StrEnum):
    """Named animations. Sprite files are looked up by these names."""

    IDLE = "idle"
    BLINK = "blink"
    EAT = "eat"
    PLAY = "play"
    HAPPY = "happy"
    REFUSE = "refuse"
    SLEEP = "sleep"
    SICK = "sick"
    CLEAN = "clean"
    EVOLVE = "evolve"
    HATCH = "hatch"
    WOBBLE = "wobble"
    DEAD = "dead"


def looping_animation(pet: Pet) -> AnimationKey:
    """The animation to loop while nothing in particular is happening."""
    if pet.stage is LifeStage.DEAD:
        return AnimationKey.DEAD
    if pet.stage is LifeStage.EGG:
        return AnimationKey.WOBBLE
    if pet.is_asleep:
        return AnimationKey.SLEEP
    if pet.is_sick:
        return AnimationKey.SICK
    return AnimationKey.IDLE


def reaction_animation(event: Event) -> AnimationKey | None:  # noqa: PLR0911 - one return per match arm
    """The one-shot animation to play in response to ``event``, if any."""
    match event:
        case Evolved(from_stage=LifeStage.EGG):
            return AnimationKey.HATCH
        case Evolved():
            return AnimationKey.EVOLVE
        case Ate():
            return AnimationKey.EAT
        case Played(won=True) | MedicineGiven(cured=True):
            return AnimationKey.HAPPY
        case Played():
            return AnimationKey.PLAY
        case Cleaned():
            return AnimationKey.CLEAN
        case Refused() | Disciplined(effective=False):
            return AnimationKey.REFUSE
        case _:
            return None


def select_animation(pet: Pet, last_event: Event | None = None) -> AnimationKey:
    """The reaction to ``last_event`` if it has one, otherwise the state's loop."""
    reaction = reaction_animation(last_event) if last_event is not None else None
    return reaction or looping_animation(pet)
