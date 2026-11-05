"""PetView playback, driven step by step."""

import itertools
from datetime import timedelta
from random import Random
from typing import ClassVar, override

import pytest
from textual.app import App, ComposeResult
from textual.binding import BindingType
from textual.containers import Container

from tama.domain.animation import AnimationKey
from tama.domain.events import (
    Action,
    Ate,
    Event,
    Evolved,
    FellAsleep,
    LearnedTrick,
    RefusalReason,
    Refused,
)
from tama.domain.pet import DEFAULT_SPECIES
from tama.domain.stage import LifeStage, Trick, Variant
from tama.domain.stats import Stats
from tama.ui.sprites import Sprite, load_sprite
from tama.ui.widgets.pet_view import (
    BLINK_EVERY,
    TRICK_EVERY,
    PetView,
    ViewOptions,
    steps_per_frame,
)
from tests.factories import make_pet

AGE = timedelta(hours=1)
CHILD = make_pet()


class Host(App[None]):
    """A bare app with a stage-sized container holding one PetView."""

    BINDINGS: ClassVar[list[BindingType]] = []

    def __init__(self, view: PetView) -> None:
        super().__init__()
        self.view = view

    @override
    def compose(self) -> ComposeResult:
        with Container():
            yield self.view


def still_view(**options: bool) -> PetView:
    return PetView(ViewOptions(animate=False, **options), rng=Random(0))


def sprite(stage: LifeStage, key: AnimationKey) -> Sprite:
    return load_sprite(DEFAULT_SPECIES, Variant.DEFAULT, stage, key)


def playing_reaction(view: PetView) -> Sprite | None:
    """Read the reaction afresh (stepping changes it; keep mypy from over-narrowing)."""
    return view.reaction


def run_steps(view: PetView, n: int) -> None:
    for _ in range(n):
        view.step()


@pytest.mark.parametrize(("fps", "steps"), [(1, 10), (1.25, 8), (4, 2), (6, 2), (8, 1), (100, 1)])
def test_steps_per_frame(fps: float, steps: int) -> None:
    assert steps_per_frame(fps) == steps


async def test_show_loops_the_state_animation_from_the_first_frame() -> None:
    view = still_view()
    async with Host(view).run_test():
        view.show(CHILD)

        assert view.current is sprite(LifeStage.CHILD, AnimationKey.IDLE)
        assert view.frame == 0
        assert view.reaction is None


async def test_step_advances_frames_at_the_sprite_fps_and_wraps() -> None:
    view = still_view()
    async with Host(view).run_test():
        view.show(make_pet(is_asleep=False, sickness_doses=1))  # sick: 2 frames at 1 fps
        per_frame = steps_per_frame(view.current.fps)

        run_steps(view, per_frame - 1)
        assert view.frame == 0
        run_steps(view, 1)
        assert view.frame == 1
        run_steps(view, per_frame)
        assert view.frame == 0


async def test_reaction_plays_once_then_returns_to_the_loop() -> None:
    view = still_view()
    async with Host(view).run_test():
        view.show(CHILD)
        view.react([Ate(AGE, Action.MEAL)])
        eat = sprite(LifeStage.CHILD, AnimationKey.EAT)
        assert view.current is eat
        frames = len(view.current.frames(view.look))

        run_steps(view, frames * steps_per_frame(view.current.fps) - 1)
        assert playing_reaction(view) is eat
        run_steps(view, 1)

        assert playing_reaction(view) is None
        assert view.current is sprite(LifeStage.CHILD, AnimationKey.IDLE)


async def test_events_without_a_reaction_change_nothing() -> None:
    view = still_view()
    async with Host(view).run_test():
        view.show(CHILD)
        view.react([FellAsleep(AGE)])

        assert view.reaction is None


async def test_last_reaction_wins() -> None:
    view = still_view()
    events: list[Event] = [
        Ate(AGE, Action.MEAL),
        Refused(AGE, Action.MEAL, RefusalReason.MISBEHAVING),
    ]
    async with Host(view).run_test():
        view.show(CHILD)
        view.react(events)

        assert view.current is sprite(LifeStage.CHILD, AnimationKey.REFUSE)


async def test_hatching_plays_from_the_new_stage() -> None:
    view = still_view()
    async with Host(view).run_test():
        view.show(make_pet(stage=LifeStage.EGG))
        assert view.current is sprite(LifeStage.EGG, AnimationKey.WOBBLE)

        view.show(make_pet(stage=LifeStage.BABY))
        view.react([Evolved(AGE, LifeStage.EGG, LifeStage.BABY, Variant.DEFAULT)])

        assert view.current is sprite(LifeStage.BABY, AnimationKey.HATCH)


async def test_react_before_show_is_ignored() -> None:
    view = still_view()
    async with Host(view).run_test():
        view.react([Ate(AGE, Action.MEAL)])

        assert view.reaction is None


async def test_changing_loop_during_a_reaction_keeps_the_reaction_going() -> None:
    view = still_view()
    async with Host(view).run_test():
        view.show(CHILD)
        view.react([Ate(AGE, Action.MEAL)])
        run_steps(view, steps_per_frame(view.current.fps))
        frame = view.frame

        view.show(make_pet(sickness_doses=1))

        assert view.frame == frame
        assert view.current is sprite(LifeStage.CHILD, AnimationKey.EAT)


async def test_showing_the_same_state_does_not_restart_the_loop() -> None:
    view = still_view()
    async with Host(view).run_test():
        view.show(make_pet(sickness_doses=1))
        run_steps(view, steps_per_frame(view.current.fps))

        view.show(make_pet(sickness_doses=1))

        assert view.frame == 1


async def test_idle_pet_blinks_now_and_then() -> None:
    view = still_view()
    async with Host(view).run_test():
        view.show(CHILD)
        view._next_blink = 1

        view.step()

        assert view.reaction is sprite(LifeStage.CHILD, AnimationKey.BLINK)


async def test_a_pet_showing_off_swaps_the_odd_blink_for_a_trick() -> None:
    view = still_view()
    async with Host(view).run_test():
        view.show(CHILD, tricks=(Trick.WAVE, Trick.SPIN))
        view._next_blink = view._next_trick = 1

        view.step()

        known = (AnimationKey.TRICK_WAVE, AnimationKey.TRICK_SPIN)
        assert any(view.reaction is sprite(LifeStage.CHILD, key) for key in known)
        assert view._next_trick >= TRICK_EVERY[0]


async def test_tricks_come_only_every_few_minutes() -> None:
    view = still_view()
    async with Host(view).run_test():
        view.show(CHILD, tricks=(Trick.WAVE,))
        view._next_blink = 1
        view._next_trick = TRICK_EVERY[0]

        view.step()

        assert view.reaction is sprite(LifeStage.CHILD, AnimationKey.BLINK)


async def test_a_pet_not_showing_off_just_blinks() -> None:
    view = still_view()
    async with Host(view).run_test():
        view.show(CHILD)
        view._next_blink = view._next_trick = 1

        view.step()

        assert view.reaction is sprite(LifeStage.CHILD, AnimationKey.BLINK)


async def test_a_trick_comes_every_one_to_three_minutes_of_idling() -> None:
    view = still_view()
    async with Host(view).run_test():
        view.show(CHILD, tricks=(Trick.BOW,))
        bow = sprite(LifeStage.CHILD, AnimationKey.TRICK_BOW)
        started: list[int] = []

        for step in range(10 * 60 * 10):  # ten minutes of steps
            before = view.reaction
            view.step()
            if view.reaction is bow and before is not bow:
                started.append(step)

        gaps = [b - a for a, b in itertools.pairwise(started)]
        assert len(started) >= 3
        assert all(TRICK_EVERY[0] <= gap <= TRICK_EVERY[1] + BLINK_EVERY[1] + 100 for gap in gaps)


async def test_a_newly_learned_trick_plays_at_once() -> None:
    view = still_view()
    async with Host(view).run_test():
        view.show(make_pet(stats=Stats(discipline=65)))
        view.react([LearnedTrick(AGE, Trick.SPIN)])

        assert view.current is sprite(LifeStage.CHILD, AnimationKey.TRICK_SPIN)


async def test_sleeping_pet_does_not_fidget() -> None:
    view = still_view()
    async with Host(view).run_test():
        view.show(make_pet(is_asleep=True))
        view._next_blink = view._next_wander = 1

        view.step()

        assert view.reaction is None
        assert view.offset_x == 0


async def test_idle_pet_wanders_within_the_stage() -> None:
    view = still_view()
    async with Host(view).run_test(size=(60, 20)):
        view.show(CHILD)
        frame_width = len(view.current.cells(view.look)[0][0])
        limit = (60 - frame_width) // 2 - 2
        seen: set[int] = set()

        for _ in range(3000):
            view.step()
            seen.add(view.offset_x)

        assert len(seen) > 1
        assert all(abs(x) <= limit for x in seen)


async def test_reduced_motion_shows_still_key_frames_only() -> None:
    view = PetView(ViewOptions(reduced_motion=True), rng=Random(0))
    async with Host(view).run_test() as pilot:
        view.show(CHILD, tricks=(Trick.WAVE,))
        view.react([Ate(AGE, Action.MEAL), LearnedTrick(AGE, Trick.WAVE)])
        await pilot.pause(0.3)

        assert view.still
        assert view.reaction is None
        assert view.frame == 0


async def test_animation_timer_runs_when_animating() -> None:
    view = PetView(ViewOptions(), rng=Random(0))
    async with Host(view).run_test() as pilot:
        view.show(make_pet(stage=LifeStage.EGG))
        await pilot.pause(0.5)

        assert view.frame > 0
