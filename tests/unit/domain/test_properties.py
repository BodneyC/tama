"""Property-based tests for invariants that must hold for *any* pet state."""

from dataclasses import replace
from datetime import timedelta

from hypothesis import given
from hypothesis import strategies as st

from tama.domain.actions import apply, apply_game_outcome
from tama.domain.balance import DEFAULT_BALANCE
from tama.domain.events import Action
from tama.domain.pet import Pet
from tama.domain.simulation import advance
from tama.domain.stats import DRIFTING, STAT_MAX, STAT_MIN, Stat
from tests.factories import make_ctx
from tests.strategies import actions, durations, pets

UP_TO_3H = durations(timedelta(hours=3))


def assert_invariants(pet: Pet) -> None:
    for stat in Stat:
        assert STAT_MIN <= pet.stats[stat] <= STAT_MAX
    for stat in DRIFTING:
        assert -1 < pet.drift[stat] < 1
    assert 0 <= pet.poop_count <= DEFAULT_BALANCE.max_poops
    assert 0 <= pet.poop_progress < 1
    assert pet.weight >= DEFAULT_BALANCE.min_weight
    assert timedelta(0) <= pet.carry < DEFAULT_BALANCE.step
    assert pet.age % DEFAULT_BALANCE.step == timedelta(0)
    assert pet.is_alive == (pet.cause_of_death is None)


@given(pets(), UP_TO_3H, st.integers())
def test_advance_preserves_invariants(pet: Pet, elapsed: timedelta, seed: int) -> None:
    assert_invariants(advance(pet, elapsed, make_ctx(seed)).pet)


@given(pets(), UP_TO_3H, UP_TO_3H, st.integers())
def test_splitting_time_gives_identical_results(
    pet: Pet, first: timedelta, second: timedelta, seed: int
) -> None:
    whole_ctx, split_ctx = make_ctx(seed), make_ctx(seed)

    whole = advance(pet, first + second, whole_ctx)
    part = advance(pet, first, split_ctx)
    rest = advance(part.pet, second, split_ctx)

    assert rest.pet == whole.pet
    assert part.events + rest.events == whole.events
    assert split_ctx.rng.getstate() == whole_ctx.rng.getstate()


@given(pets(alive=False), UP_TO_3H)
def test_dead_pets_never_change(pet: Pet, elapsed: timedelta) -> None:
    out = advance(pet, elapsed, make_ctx())

    assert out.events == ()
    assert replace(out.pet, updated_at=pet.updated_at, carry=pet.carry) == pet


@given(pets(), UP_TO_3H)
def test_age_never_decreases_and_never_outpaces_time(pet: Pet, elapsed: timedelta) -> None:
    out = advance(pet, elapsed, make_ctx())

    assert pet.age <= out.pet.age <= pet.age + pet.carry + elapsed
    assert out.pet.updated_at == pet.updated_at + elapsed


@given(pets(alive=True), st.lists(st.one_of(actions, st.booleans()), max_size=10), st.integers())
def test_actions_preserve_invariants(pet: Pet, moves: list[Action | bool], seed: int) -> None:
    ctx = make_ctx(seed)
    for move in moves:
        # A bool stands for finishing a mini-game (won or lost).
        out = (
            apply_game_outcome(pet, won=move, ctx=ctx)
            if isinstance(move, bool)
            else apply(pet, move, ctx)
        )
        assert out.refusal is None or out.pet == pet
        pet = out.pet
        assert_invariants(pet)
