"""PetLibrary: hatching an heir from a dead pet's egg (SPEC §2.8, ADR 0010)."""

import os
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from random import Random
from typing import Any

import pytest

from tama.domain.journal import Topic
from tama.domain.stage import DeathCause, LifeStage, Variant
from tama.domain.stats import Stats
from tama.errors import InvalidArgumentError, NoEggError, PetLockedError, RosterFullError
from tama.infra.clock import FakeClock
from tama.persistence.lock import PetLock
from tama.persistence.models import SaveGame
from tama.persistence.roster import PetFile, PetRoster
from tama.services.library import PetLibrary
from tama.services.roster import MAX_PETS
from tama.services.session import SessionSettings
from tests.factories import FIXED_NOW, make_pet

OLD: dict[str, Any] = {
    "stage": LifeStage.DEAD,
    "cause_of_death": DeathCause.OLD_AGE,
    "variant": Variant.GOOD,
    "species": "owl",
    "age": timedelta(days=16),
    "stats": Stats(discipline=90),
}
LATER = FIXED_NOW + timedelta(days=17)


@pytest.fixture
def library(tmp_path: Path) -> PetLibrary:
    return PetLibrary(PetRoster(tmp_path), clock=FakeClock(LATER), settings=SessionSettings())


def add(library: PetLibrary, name: str, **overrides: Any) -> PetFile:
    """A pet saved as of the library's clock, so nothing happens to it while catching up."""
    pet = replace(make_pet(**overrides), name=name, updated_at=LATER)
    file = library.roster.create(name)
    file.repo().save(SaveGame(pet, Random(0).getstate()))
    return file


def row(library: PetLibrary, name: str) -> Any:
    return next(r for r in library.summaries() if r.name == name)


def test_a_pet_that_died_of_old_age_has_an_egg_waiting(library: PetLibrary) -> None:
    add(library, "Mochi", **OLD)
    add(library, "Bao", **(OLD | {"cause_of_death": DeathCause.POOR_HEALTH}))
    add(library, "Pip")

    assert row(library, "Mochi").egg_waiting
    assert not row(library, "Bao").egg_waiting
    assert not row(library, "Pip").egg_waiting


def test_hatching_the_heir_opens_it_and_marks_the_egg(library: PetLibrary) -> None:
    parent = add(library, "Mochi", **OLD)

    session = library.hatch_heir(parent, "Mochi II")

    heir = session.pet
    assert (heir.name, heir.species, heir.generation) == ("Mochi II", "owl", 2)
    assert heir.stats.discipline == 25
    assert heir.born_at == LATER
    assert library.open_file is not None
    assert library.roster.last() == library.open_file
    saved_parent = parent.repo().load().game
    assert saved_parent.pet.heir_hatched
    assert [e.topic for e in saved_parent.journal.entries] == [Topic.HEIR_HATCHED]
    assert not row(library, "Mochi").egg_waiting
    assert len(library.summaries()) == 2


def test_the_heir_rng_comes_from_the_parent(tmp_path: Path) -> None:
    lives = []
    for n in range(2):
        lib = PetLibrary(
            PetRoster(tmp_path / str(n)), clock=FakeClock(LATER), settings=SessionSettings()
        )
        lives.append(lib.hatch_heir(add(lib, "Mochi", **OLD), "Mochi II").pet.lifespan)
        lib.close()

    assert lives[0] == lives[1]


def test_an_egg_hatches_only_once(library: PetLibrary) -> None:
    parent = add(library, "Mochi", **OLD)
    library.hatch_heir(parent, "Mochi II")

    with pytest.raises(NoEggError):
        library.hatch_heir(parent, "Mochi II")


def test_a_crash_between_the_two_saves_cannot_give_a_second_heir(library: PetLibrary) -> None:
    parent = add(library, "Mochi", **OLD)
    library.hatch_heir(parent, "Mochi II")
    library.close()
    game = parent.repo().load().game  # as if the parent's save never happened:
    parent.repo().save(replace(game, pet=replace(game.pet, heir_hatched=False)))

    assert not row(library, "Mochi").egg_waiting
    with pytest.raises(NoEggError):
        library.hatch_heir(parent, "Mochi III")


def test_no_heir_beyond_nine_pets(library: PetLibrary) -> None:
    parent = add(library, "Mochi", **OLD)
    for n in range(MAX_PETS - 1):
        add(library, f"Pet {n}")

    with pytest.raises(RosterFullError):
        library.hatch_heir(parent, "Mochi II")


def test_the_heir_needs_a_name_no_living_pet_has(library: PetLibrary) -> None:
    parent = add(library, "Mochi", **OLD)
    add(library, "Mochi II")

    with pytest.raises(InvalidArgumentError, match="already have a Mochi II"):
        library.hatch_heir(parent, "Mochi II")


def test_a_parent_open_elsewhere_cannot_hatch(library: PetLibrary) -> None:
    parent = add(library, "Mochi", **OLD)

    with PetLock(parent.path, pid=os.getppid()), pytest.raises(PetLockedError):
        library.hatch_heir(parent, "Mochi II")
