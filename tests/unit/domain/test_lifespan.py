"""Whole-life simulations (M1 acceptance criterion)."""

from datetime import timedelta
from random import Random

import pytest

from tama.domain.actions import apply, apply_game_outcome, refusal
from tama.domain.context import Context
from tama.domain.events import Action, Died, Event, Evolved
from tama.domain.minigames import GameResult
from tama.domain.pet import Pet, new_egg
from tama.domain.simulation import advance
from tama.domain.stage import DeathCause, LifeStage, Variant
from tests.factories import FIXED_NOW, make_ctx

CHECK_EVERY = timedelta(minutes=4)  # inside the 5-minute misbehaviour grace period


def attentive_care(pet: Pet, ctx: Context) -> Pet:
    """What a diligent player does when they glance at the pet."""

    def act(action: Action) -> None:
        nonlocal pet
        pet = apply(pet, action, ctx).pet  # refusals are fine; try again next check

    if pet.is_sick:
        act(Action.MEDICINE)
    if pet.poop_count or pet.stats.hygiene < 80:
        act(Action.CLEAN)
    if pet.stats.hunger < 70:
        act(Action.MEAL)
    if pet.stats.happiness < 70 and refusal(pet, Action.PLAY, ctx.balance) is None:
        pet = apply_game_outcome(pet, GameResult.WIN, ctx=ctx).pet
    if pet.misbehaving:
        act(Action.DISCIPLINE)
    if pet.is_asleep == pet.lights_on:
        act(Action.LIGHTS)
    return pet


def live(seed: int, *, cared_for: bool) -> tuple[Pet, list[Event]]:
    ctx = make_ctx(seed)
    pet = new_egg("Mochi", FIXED_NOW, Random(seed))
    events: list[Event] = []
    while pet.is_alive:
        out = advance(pet, CHECK_EVERY, ctx)
        pet, events = out.pet, events + list(out.events)
        if cared_for:
            pet = attentive_care(pet, ctx)
    return pet, events


def life_story(events: list[Event]) -> list[LifeStage | DeathCause]:
    return [
        e.to_stage if isinstance(e, Evolved) else e.cause
        for e in events
        if isinstance(e, Evolved | Died)
    ]


@pytest.mark.slow
def test_well_cared_for_pet_lives_a_full_life() -> None:
    pet, events = live(seed=2026, cared_for=True)

    assert life_story(events) == [
        LifeStage.BABY,
        LifeStage.CHILD,
        LifeStage.TEEN,
        LifeStage.ADULT,
        LifeStage.ELDER,
        DeathCause.OLD_AGE,
    ]
    assert pet.variant is Variant.GOOD
    assert pet.care_mistakes == 0
    assert pet.age == pet.lifespan


def test_neglected_pet_dies_young() -> None:
    pet, events = live(seed=2026, cared_for=False)

    assert life_story(events) == [LifeStage.BABY, LifeStage.CHILD, DeathCause.POOR_HEALTH]
    assert pet.care_mistakes >= 1
    assert pet.age < timedelta(days=1)
