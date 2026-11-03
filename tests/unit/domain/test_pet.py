from datetime import timedelta
from fractions import Fraction
from random import Random

import pytest

from tama.domain.balance import DEFAULT_BALANCE
from tama.domain.pet import (
    DEFAULT_SPECIES,
    MAX_NAME_LENGTH,
    Drift,
    Pet,
    Timers,
    new_egg,
    validate_name,
    validate_species,
)
from tama.domain.stage import DeathCause, LifeStage, Variant
from tama.domain.stats import Stat, Stats
from tama.errors import InvalidArgumentError
from tests.factories import FIXED_NOW, make_pet


def test_new_egg_starts_as_healthy_egg() -> None:
    pet = new_egg("Mochi", FIXED_NOW, Random(0))

    assert pet.name == "Mochi"
    assert pet.stage is LifeStage.EGG
    assert pet.variant is Variant.DEFAULT
    assert pet.stats == Stats()
    assert pet.age == timedelta(0)
    assert pet.born_at == pet.updated_at == FIXED_NOW
    assert pet.is_alive
    assert not pet.is_sick


def test_new_egg_lifespan_is_seeded_within_spec_range() -> None:
    spans = {new_egg("A", FIXED_NOW, Random(seed)).lifespan for seed in range(50)}

    assert all(timedelta(days=14) <= span <= timedelta(days=18) for span in spans)
    assert len(spans) > 1
    assert (
        new_egg("A", FIXED_NOW, Random(7)).lifespan == new_egg("A", FIXED_NOW, Random(7)).lifespan
    )


def test_lifespan_is_a_whole_number_of_steps() -> None:
    pet = new_egg("A", FIXED_NOW, Random(3))

    assert pet.lifespan % DEFAULT_BALANCE.step == timedelta(0)


def test_new_egg_strips_name() -> None:
    assert new_egg("  Mochi ", FIXED_NOW, Random(0)).name == "Mochi"


@pytest.mark.parametrize("name", ["", "   ", "x" * (MAX_NAME_LENGTH + 1), "tab\tname"])
def test_invalid_names_are_rejected(name: str) -> None:
    with pytest.raises(InvalidArgumentError, match="name"):
        validate_name(name)


def test_new_egg_requires_aware_time() -> None:
    with pytest.raises(InvalidArgumentError, match="timezone-aware"):
        new_egg("A", FIXED_NOW.replace(tzinfo=None), Random(0))


def test_is_sick_reflects_remaining_doses() -> None:
    assert make_pet(sickness_doses=2).is_sick
    assert not make_pet(sickness_doses=0).is_sick


def test_is_alive_false_when_dead() -> None:
    pet = make_pet(stage=LifeStage.DEAD, cause_of_death=DeathCause.OLD_AGE)

    assert not pet.is_alive


def test_drift_get_and_set_by_stat() -> None:
    drift = Drift().with_value(Stat.HUNGER, Fraction(-1, 3))

    assert drift[Stat.HUNGER] == Fraction(-1, 3)
    assert drift[Stat.ENERGY] == 0


def test_timers_neglect_get_and_set_by_need() -> None:
    timers = Timers().with_neglect(Stat.HYGIENE, timedelta(minutes=3))

    assert timers.neglect(Stat.HYGIENE) == timedelta(minutes=3)
    assert timers.neglect(Stat.HUNGER) == timedelta(0)


def test_pet_rejects_negative_counters() -> None:
    with pytest.raises(InvalidArgumentError, match="poop_count"):
        make_pet(poop_count=-1)
    with pytest.raises(InvalidArgumentError, match="weight"):
        make_pet(weight=0)


def test_pet_rejects_naive_timestamps() -> None:
    with pytest.raises(InvalidArgumentError, match="timezone-aware"):
        make_pet(updated_at=FIXED_NOW.replace(tzinfo=None))


def test_pet_is_frozen() -> None:
    pet = make_pet()

    with pytest.raises(AttributeError):
        pet.name = "Other"  # type: ignore[misc]  # deliberately mutating a frozen dataclass


def test_pet_type_is_exported() -> None:
    assert isinstance(make_pet(), Pet)


# --- Species ------------------------------------------------------------------------------


def test_new_egg_is_the_default_species() -> None:
    assert new_egg("Mochi", FIXED_NOW, Random(0)).species == DEFAULT_SPECIES == "tama"


def test_new_egg_can_be_another_species() -> None:
    assert new_egg("Hoot", FIXED_NOW, Random(0), species="owl").species == "owl"


@pytest.mark.parametrize("species", ["", "Owl", "big bear", "../tama", "1owl", "owl!"])
def test_invalid_species_are_rejected(species: str) -> None:
    with pytest.raises(InvalidArgumentError, match="species"):
        validate_species(species)
    with pytest.raises(InvalidArgumentError, match="species"):
        make_pet(species=species)


@pytest.mark.parametrize("species", ["tama", "owl", "polar-bear", "cat_2"])
def test_valid_species_names(species: str) -> None:
    assert validate_species(species) == species
