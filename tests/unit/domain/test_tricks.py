from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tama.domain.actions import apply
from tama.domain.balance import DEFAULT_BALANCE, Balance
from tama.domain.events import Action, Disciplined, Event, Evolved, LearnedTrick
from tama.domain.lifecycle import progress
from tama.domain.stage import DeathCause, LifeStage, Trick
from tama.domain.stats import Stats
from tama.domain.tricks import can_show_off, known_tricks, learned_tricks
from tama.errors import InvalidArgumentError
from tests.factories import make_ctx, make_pet

# --- Known tricks --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("discipline", "tricks"),
    [
        (0, ()),
        (24, ()),
        (25, (Trick.WAVE,)),
        (49, (Trick.WAVE,)),
        (50, (Trick.WAVE, Trick.SPIN)),
        (75, (Trick.WAVE, Trick.SPIN, Trick.DANCE)),
        (100, (Trick.WAVE, Trick.SPIN, Trick.DANCE, Trick.BOW)),
    ],
)
def test_known_tricks_follow_discipline(discipline: int, tricks: tuple[Trick, ...]) -> None:
    pet = make_pet(stats=Stats(discipline=discipline))

    assert known_tricks(pet, DEFAULT_BALANCE) == tricks


@pytest.mark.parametrize(
    "stage", [LifeStage.CHILD, LifeStage.TEEN, LifeStage.ADULT, LifeStage.ELDER]
)
def test_children_and_older_know_tricks(stage: LifeStage) -> None:
    pet = make_pet(stage=stage, stats=Stats(discipline=100))

    assert len(known_tricks(pet, DEFAULT_BALANCE)) == len(Trick)


@pytest.mark.parametrize("stage", [LifeStage.EGG, LifeStage.BABY])
def test_eggs_and_babies_know_no_tricks(stage: LifeStage) -> None:
    pet = make_pet(stage=stage, stats=Stats(discipline=100))

    assert known_tricks(pet, DEFAULT_BALANCE) == ()


def test_the_dead_know_no_tricks() -> None:
    pet = make_pet(
        stage=LifeStage.DEAD, cause_of_death=DeathCause.OLD_AGE, stats=Stats(discipline=100)
    )

    assert known_tricks(pet, DEFAULT_BALANCE) == ()


def test_thresholds_come_from_balance() -> None:
    balance = Balance(trick_thresholds=((Trick.BOW, 10), (Trick.WAVE, 90)))
    pet = make_pet(stats=Stats(discipline=50))

    assert known_tricks(pet, balance) == (Trick.BOW,)


def test_balance_rejects_repeated_tricks() -> None:
    with pytest.raises(InvalidArgumentError, match="once"):
        Balance(trick_thresholds=((Trick.WAVE, 10), (Trick.WAVE, 20)))


# --- Learning ------------------------------------------------------------------------------


def test_learned_tricks_are_the_ones_newly_known() -> None:
    before = make_pet(stats=Stats(discipline=40))
    after = make_pet(stats=Stats(discipline=80))

    assert learned_tricks(before, after, DEFAULT_BALANCE) == (
        LearnedTrick(after.age, Trick.SPIN),
        LearnedTrick(after.age, Trick.DANCE),
    )


def test_forgetting_a_trick_is_not_learning() -> None:
    before = make_pet(stats=Stats(discipline=60))
    after = make_pet(stats=Stats(discipline=50))

    assert learned_tricks(before, after, DEFAULT_BALANCE) == ()


def test_disciplining_a_child_from_40_to_65_teaches_it_to_spin() -> None:
    pet = make_pet(misbehaving=True, stats=Stats(discipline=40))

    out = apply(pet, Action.DISCIPLINE, make_ctx())

    assert out.pet.stats.discipline == 65
    assert out.events == (
        Disciplined(pet.age, effective=True),
        LearnedTrick(pet.age, Trick.SPIN),
    )
    assert known_tricks(out.pet, DEFAULT_BALANCE) == (Trick.WAVE, Trick.SPIN)


def test_discipline_that_passes_no_threshold_teaches_nothing() -> None:
    pet = make_pet(misbehaving=True, stats=Stats(discipline=100))

    out = apply(pet, Action.DISCIPLINE, make_ctx())

    assert out.events == (Disciplined(pet.age, effective=True),)


def test_a_disciplined_heir_learns_its_trick_on_becoming_a_child() -> None:
    baby = make_pet(stage=LifeStage.BABY, stats=Stats(discipline=25), age=DEFAULT_BALANCE.child_age)
    events: list[Event] = []

    child = progress(baby, DEFAULT_BALANCE, events)

    assert child.stage is LifeStage.CHILD
    assert events == [
        Evolved(baby.age, LifeStage.BABY, LifeStage.CHILD, baby.variant),
        LearnedTrick(baby.age, Trick.WAVE),
    ]


def test_growing_up_past_child_teaches_nothing_new() -> None:
    teen_age = DEFAULT_BALANCE.teen_age
    child = make_pet(stats=Stats(discipline=60), age=teen_age)
    events: list[Event] = []

    progress(child, DEFAULT_BALANCE, events)

    assert [type(e) for e in events] == [Evolved]


@given(st.integers(0, 100), st.integers(0, 100))
def test_learned_and_known_agree(before: int, after: int) -> None:
    old = make_pet(stats=Stats(discipline=before))
    new = make_pet(stats=Stats(discipline=after))

    learned = {e.trick for e in learned_tricks(old, new, DEFAULT_BALANCE)}

    assert learned == set(known_tricks(new, DEFAULT_BALANCE)) - set(
        known_tricks(old, DEFAULT_BALANCE)
    )


# --- Showing off ---------------------------------------------------------------------------


CONTENT = Stats(happiness=80, discipline=50)


def test_a_content_pet_that_knows_tricks_shows_off() -> None:
    assert can_show_off(make_pet(stats=CONTENT), DEFAULT_BALANCE)


@pytest.mark.parametrize(
    "overrides",
    [
        {"stats": Stats(happiness=74, discipline=50)},
        {"stats": Stats(happiness=100, discipline=0)},
        {"is_asleep": True},
        {"lights_on": False},
        {"misbehaving": True},
        {"sickness_doses": 1},
        {"stage": LifeStage.BABY},
        {"paused_since": make_pet().updated_at},
    ],
    ids=["unhappy", "no-tricks", "asleep", "dark", "tantrum", "sick", "baby", "holiday"],
)
def test_no_showing_off_unless_content_awake_and_well(overrides: dict[str, Any]) -> None:
    pet = make_pet(**{"stats": CONTENT, **overrides})

    assert not can_show_off(pet, DEFAULT_BALANCE)
