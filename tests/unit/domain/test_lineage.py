from dataclasses import replace
from datetime import timedelta
from random import Random
from typing import Any

import pytest

from tama.domain.balance import DEFAULT_BALANCE
from tama.domain.events import HeirHatched
from tama.domain.lineage import founder, hatch_heir, heir_name
from tama.domain.pet import AncestorRecord, Pet, new_egg
from tama.domain.stage import DeathCause, LifeStage, Variant
from tama.domain.stats import Stats
from tama.errors import InvalidArgumentError, NoEggError
from tests.factories import FIXED_NOW, make_pet

LATER = FIXED_NOW + timedelta(days=20)


def dead_parent(**overrides: Any) -> Pet:
    fields: dict[str, Any] = {
        "stage": LifeStage.DEAD,
        "cause_of_death": DeathCause.OLD_AGE,
        "variant": Variant.GOOD,
        "species": "owl",
        "age": timedelta(days=16),
        "stats": Stats(discipline=80),
    }
    return make_pet(**(fields | overrides))


# --- Names ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "heir"),
    [
        ("Mochi", "Mochi II"),
        ("Mochi I", "Mochi II"),
        ("Mochi II", "Mochi III"),
        ("Mochi IX", "Mochi X"),
        ("Mochi XXXIX", "Mochi XL"),
        ("Lady VI", "Lady VII"),
        ("Vi", "Vi II"),  # a name, not a numeral: it has nothing before it
        ("Lady Vi", "Lady Vi II"),  # numerals are capitals
        ("Mochi IIII", "Mochi IIII II"),  # not a proper numeral
        ("Bartholomew VII", "Bartholomew VIII"),
    ],
)
def test_heir_name_counts_on_from_the_parent(name: str, heir: str) -> None:
    assert heir_name(name) == heir


@pytest.mark.parametrize("name", ["Sixteen chars!!!", "Bartholomew XVII"])
def test_heir_name_is_none_when_it_would_not_fit(name: str) -> None:
    assert heir_name(name) is None


# --- Hatching ------------------------------------------------------------------------------


def test_the_heir_is_a_fresh_egg_of_the_same_kind() -> None:
    parent = dead_parent()

    heir, outcome = hatch_heir(parent, "Mochi II", LATER, Random(1), DEFAULT_BALANCE)

    fresh = new_egg("Mochi II", LATER, Random(1), species="owl")
    assert heir == replace(
        fresh,
        generation=2,
        ancestors=(AncestorRecord("Mochi", parent.born_at, 1, Variant.GOOD, timedelta(days=16)),),
        stats=Stats(discipline=DEFAULT_BALANCE.heir_discipline),
    )
    assert outcome.pet == replace(parent, heir_hatched=True)
    assert outcome.events == (HeirHatched(parent.age, "Mochi II"),)
    assert not outcome.pet.egg_waiting


@pytest.mark.parametrize("variant", [Variant.SCRUFFY, Variant.CHUBBY])
def test_only_a_good_parent_gives_a_head_start(variant: Variant) -> None:
    heir, _ = hatch_heir(
        dead_parent(variant=variant), "Mochi II", LATER, Random(1), DEFAULT_BALANCE
    )

    assert heir.stats.discipline == 0


def test_the_line_goes_back_to_the_founder() -> None:
    first = dead_parent()
    second, _ = hatch_heir(first, "Mochi II", LATER, Random(1), DEFAULT_BALANCE)
    second = replace(second, stage=LifeStage.DEAD, cause_of_death=DeathCause.OLD_AGE)

    third, _ = hatch_heir(second, "Mochi III", LATER, Random(2), DEFAULT_BALANCE)

    assert third.generation == 3
    assert [a.name for a in third.ancestors] == ["Mochi", "Mochi II"]
    assert founder(third) == "Mochi"
    assert founder(first) is None


@pytest.mark.parametrize(
    "parent",
    [
        make_pet(),
        dead_parent(cause_of_death=DeathCause.POOR_HEALTH),
        dead_parent(heir_hatched=True),
    ],
    ids=["alive", "poor-health", "already-hatched"],
)
def test_only_a_waiting_egg_can_hatch(parent: Pet) -> None:
    with pytest.raises(NoEggError):
        hatch_heir(parent, "Mochi II", LATER, Random(1), DEFAULT_BALANCE)


def test_the_heir_name_must_be_valid() -> None:
    with pytest.raises(InvalidArgumentError):
        hatch_heir(dead_parent(), "", LATER, Random(1), DEFAULT_BALANCE)


def test_generation_must_be_positive() -> None:
    with pytest.raises(InvalidArgumentError, match="generation"):
        make_pet(generation=0)
