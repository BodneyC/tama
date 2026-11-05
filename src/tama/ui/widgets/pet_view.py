"""Animated sprite playback (SPEC §5.2).

``PetView`` loops the animation that suits the pet's state and plays one-shot reactions
(eating, refusing, hatching...) before returning to the loop. While idle it blinks now and then,
wanders a little and, if it is in the mood to show off, swaps the odd blink for a trick.
*Which* animation to play is decided by the pure ``tama.domain.animation`` functions; this
widget only handles timing.

Animation advances in steps of ``STEP_SECONDS``. A timer calls ``step()`` while mounted,
unless animation is off (tests, snapshots) or the player asked for reduced motion, in which
case the first frame of the loop is shown and nothing moves.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from random import Random

from textual.widget import Widget
from textual.widgets import Static

from tama.domain.animation import (
    AnimationKey,
    looping_animation,
    reaction_animation,
    trick_animation,
)
from tama.domain.events import Event
from tama.domain.pet import DEFAULT_SPECIES, Pet
from tama.domain.stage import Trick
from tama.ui.colours import Look, Mode
from tama.ui.sprites import PLACEHOLDER, Sprite, load_sprite, species_of

STEP_SECONDS = 0.1
BLINK_EVERY = (30, 70)
"""Steps between blinks while idle (3-7 s)."""
WANDER_EVERY = (20, 45)
"""Steps between small moves while idle (2-4.5 s)."""
TRICK_EVERY = (600, 1800)
"""Idle steps before the next blink may be a trick instead (1-3 min, SPEC §2.10)."""
WANDER_MARGIN = 2
"""Cells kept clear between the wandering pet and the edge of the stage."""


@dataclass(frozen=True, slots=True)
class ViewOptions:
    """How the pet is drawn.

    Attributes:
        monochrome: No colour (``NO_COLOR``).
        animate: Run the animation timer (off in tests and snapshots).
        reduced_motion: Show static key frames only; no reactions, blinking or wandering.
    """

    monochrome: bool = False
    animate: bool = True
    reduced_motion: bool = False


def steps_per_frame(fps: float) -> int:
    """How many steps each frame of a ``fps`` animation lasts."""
    return max(1, round(1 / (fps * STEP_SECONDS)))


class PetView(Static):
    """The animated pet."""

    def __init__(
        self,
        options: ViewOptions | None = None,
        *,
        rng: Random | None = None,
        small: bool = False,
        id: str | None = None,  # noqa: A002 - Textual's widget id parameter
    ) -> None:
        """Create the view. ``rng`` drives blinking and wandering (cosmetic, not game state).

        ``small`` draws the pet at half size (beside a pet-vs-pet board).
        """
        super().__init__(id=id, markup=False)
        self.small = small
        options = options or ViewOptions()
        self._options = options
        self._color = not options.monochrome
        self._species = DEFAULT_SPECIES
        self._rng = rng or Random()
        self._pet: Pet | None = None
        self._loop: Sprite = PLACEHOLDER
        self._loop_key: AnimationKey | None = None
        self.reaction: Sprite | None = None
        self.frame = 0
        self._steps = 0
        self.offset_x = 0
        self._next_blink = self._rng.randint(*BLINK_EVERY)
        self._next_wander = self._rng.randint(*WANDER_EVERY)
        self._next_trick = self._rng.randint(*TRICK_EVERY)
        self._tricks: tuple[Trick, ...] = ()

    @property
    def still(self) -> bool:
        """Whether only static key frames are shown."""
        return self._options.reduced_motion

    @property
    def look(self) -> Look:
        """How sprites are drawn right now: the app theme's mode, in colour or not."""
        return Look(Mode.of(dark=self.app.current_theme.dark), color=self._color)

    @property
    def current(self) -> Sprite:
        """The sprite being played: the reaction if one is running, else the loop."""
        return self.reaction or self._loop

    def on_mount(self) -> None:
        """Start the animation timer unless animation is off."""
        if self._options.animate and not self.still:
            self.set_interval(STEP_SECONDS, self.step)

    def set_loop(self, sprite: Sprite, key: AnimationKey | None = None) -> None:
        """Loop ``sprite`` (restarting it only if it changed)."""
        if sprite is not self._loop:
            self._loop, self._loop_key = sprite, key
            if self.reaction is None:
                self.frame = self._steps = 0
        self._draw()

    def show(self, pet: Pet, tricks: Sequence[Trick] = ()) -> None:
        """Loop the animation that suits ``pet``'s state.

        ``tricks`` are the ones it may show off now and then while idle (none unless it is in
        the mood, ``tama.domain.tricks.can_show_off``).
        """
        self._pet = pet
        self._tricks = tuple(tricks)
        key = looping_animation(pet)
        self._species = species_of(pet)
        self.set_loop(self.sprite(pet, key), key)

    def sprite(self, pet: Pet, key: AnimationKey) -> Sprite:
        """``pet``'s ``key`` animation at this view's size."""
        return load_sprite(species_of(pet), pet.variant, pet.stage, key, small=self.small)

    def react(self, events: Iterable[Event]) -> None:
        """Play a one-shot reaction to the last event that has one (call after ``show``)."""
        if self.still or self._pet is None:
            return
        keys = [key for key in map(reaction_animation, events) if key is not None]
        if keys:
            self._start_reaction(self._pet, keys[-1])

    def step(self) -> None:
        """Advance one animation step."""
        sprite = self.current
        self._steps += 1
        if self._steps >= steps_per_frame(sprite.fps):
            self._steps = 0
            self.frame += 1
            if self.frame >= len(sprite.frames(self.look)):
                self.frame = 0
                self.reaction = None
        if self.reaction is None and self._loop_key is AnimationKey.IDLE and self._pet is not None:
            self._idle_fidgets(self._pet)
        self._draw()

    def _start_reaction(self, pet: Pet, key: AnimationKey) -> None:
        self.reaction = self.sprite(pet, key)
        self.frame = self._steps = 0
        self._draw()

    def _idle_fidgets(self, pet: Pet) -> None:
        self._next_blink -= 1
        self._next_trick -= 1
        if self._next_blink <= 0:
            self._next_blink = self._rng.randint(*BLINK_EVERY)
            self._start_reaction(pet, self._blink_or_trick())
        self._next_wander -= 1
        if self._next_wander <= 0:
            self._next_wander = self._rng.randint(*WANDER_EVERY)
            limit = self._wander_limit()
            step = self._rng.choice((-2, -1, 1, 2))
            self.offset_x = max(-limit, min(limit, self.offset_x + step))

    def _blink_or_trick(self) -> AnimationKey:
        if self._next_trick > 0 or not self._tricks:
            return AnimationKey.BLINK
        self._next_trick = self._rng.randint(*TRICK_EVERY)
        return trick_animation(self._rng.choice(self._tricks))

    def _wander_limit(self) -> int:
        frame_width = len(self.current.cells(self.look)[0][0])
        stage_width = self.parent.size.width if isinstance(self.parent, Widget) else 0
        return max(0, (stage_width - frame_width) // 2 - WANDER_MARGIN)

    def _draw(self) -> None:
        frames = self.current.frames(self.look)
        self.update(frames[min(self.frame, len(frames) - 1)])
        self.styles.offset = (self.offset_x, 0)
