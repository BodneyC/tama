"""Animated sprite playback (SPEC §5.2).

``PetView`` loops the animation that suits the pet's state and plays one-shot reactions
(eating, refusing, hatching...) before returning to the loop. While idle it blinks now and then
and wanders a little. *Which* animation to play is decided by the pure ``tama.domain.animation``
functions; this widget only handles timing.

Animation advances in steps of ``STEP_SECONDS``. A timer calls ``step()`` while mounted,
unless animation is off (tests, snapshots) or the player asked for reduced motion, in which
case the first frame of the loop is shown and nothing moves.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from random import Random

from textual.widget import Widget
from textual.widgets import Static

from tama.domain.animation import AnimationKey, looping_animation, reaction_animation
from tama.domain.events import Event
from tama.domain.pet import Pet
from tama.ui.sprites import PLACEHOLDER, Sprite, load_sprite

STEP_SECONDS = 0.1
BLINK_EVERY = (30, 70)
"""Steps between blinks while idle (3-7 s)."""
WANDER_EVERY = (20, 45)
"""Steps between small moves while idle (2-4.5 s)."""
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
        id: str | None = None,  # noqa: A002 - Textual's widget id parameter
    ) -> None:
        """Create the view. ``rng`` drives blinking and wandering (cosmetic, not game state)."""
        super().__init__(id=id, markup=False)
        options = options or ViewOptions()
        self._options = options
        self._color = not options.monochrome
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

    @property
    def still(self) -> bool:
        """Whether only static key frames are shown."""
        return self._options.reduced_motion

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

    def show(self, pet: Pet) -> None:
        """Loop the animation that suits ``pet``'s state."""
        self._pet = pet
        key = looping_animation(pet)
        self.set_loop(load_sprite(pet.variant, pet.stage, key), key)

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
            if self.frame >= len(sprite.frames(color=self._color)):
                self.frame = 0
                self.reaction = None
        if self.reaction is None and self._loop_key is AnimationKey.IDLE and self._pet is not None:
            self._idle_fidgets(self._pet)
        self._draw()

    def _start_reaction(self, pet: Pet, key: AnimationKey) -> None:
        self.reaction = load_sprite(pet.variant, pet.stage, key)
        self.frame = self._steps = 0
        self._draw()

    def _idle_fidgets(self, pet: Pet) -> None:
        self._next_blink -= 1
        if self._next_blink <= 0:
            self._next_blink = self._rng.randint(*BLINK_EVERY)
            self._start_reaction(pet, AnimationKey.BLINK)
        self._next_wander -= 1
        if self._next_wander <= 0:
            self._next_wander = self._rng.randint(*WANDER_EVERY)
            limit = self._wander_limit()
            step = self._rng.choice((-2, -1, 1, 2))
            self.offset_x = max(-limit, min(limit, self.offset_x + step))

    def _wander_limit(self) -> int:
        frame_width = len(self.current.cells(color=self._color)[0][0])
        stage_width = self.parent.size.width if isinstance(self.parent, Widget) else 0
        return max(0, (stage_width - frame_width) // 2 - WANDER_MARGIN)

    def _draw(self) -> None:
        frames = self.current.frames(color=self._color)
        self.update(frames[min(self.frame, len(frames) - 1)])
        self.styles.offset = (self.offset_x, 0)
