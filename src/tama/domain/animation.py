"""Which animation the pet should be showing (SPEC §5.2).

This decides *what* to play; frame playback and timing live in the UI. Blinking, wandering
and showing off a trick (``tama.domain.tricks.can_show_off``) are cosmetic variations of
``IDLE`` chosen by the UI.
"""

from enum import StrEnum

from tama.domain.events import (
    Ate,
    Cleaned,
    Disciplined,
    Event,
    Evolved,
    LearnedTrick,
    MedicineGiven,
    Played,
    PlayedWith,
    Refused,
    Visited,
)
from tama.domain.minigames import GameResult
from tama.domain.pet import Pet
from tama.domain.stage import LifeStage, Trick


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
    LOOK_LEFT = "look_left"
    LOOK_RIGHT = "look_right"
    MISBEHAVE = "misbehave"
    TRICK_WAVE = "trick_wave"
    TRICK_SPIN = "trick_spin"
    TRICK_DANCE = "trick_dance"
    TRICK_BOW = "trick_bow"


def trick_animation(trick: Trick) -> AnimationKey:
    """The one-shot animation of ``trick`` (SPEC §2.10)."""
    return AnimationKey(f"trick_{trick.value}")


def looping_animation(pet: Pet) -> AnimationKey:
    """The animation to loop while nothing in particular is happening."""
    if pet.stage is LifeStage.DEAD:
        return AnimationKey.DEAD
    if pet.stage is LifeStage.EGG:
        return AnimationKey.WOBBLE
    if pet.is_asleep or pet.on_holiday:
        return AnimationKey.SLEEP
    if pet.is_sick:
        return AnimationKey.SICK
    if pet.misbehaving:
        return AnimationKey.MISBEHAVE
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
        case (
            Played(result=GameResult.WIN)
            | PlayedWith(result=GameResult.WIN)
            | MedicineGiven(cured=True)
            | Visited()
        ):
            return AnimationKey.HAPPY  # greeting a friend, too (SPEC §3.2)
        case Played() | PlayedWith():
            return AnimationKey.PLAY
        case Cleaned():
            return AnimationKey.CLEAN
        case LearnedTrick(trick=trick):
            return trick_animation(trick)
        case Refused() | Disciplined(effective=False):
            return AnimationKey.REFUSE
        case _:
            return None


def select_animation(pet: Pet, last_event: Event | None = None) -> AnimationKey:
    """The reaction to ``last_event`` if it has one, otherwise the state's loop."""
    reaction = reaction_animation(last_event) if last_event is not None else None
    return reaction or looping_animation(pet)
