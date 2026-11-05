import time
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from random import Random
from typing import Any

import pytest

from tama.domain.attention import AttentionReason
from tama.domain.stage import DeathCause, LifeStage
from tama.domain.stats import Stats
from tama.errors import CorruptSaveError, UnknownPetError
from tama.infra.clock import FakeClock
from tama.persistence.models import SaveGame
from tama.persistence.roster import PetRoster
from tama.services.roster import (
    MAX_PETS,
    PetSummary,
    can_add_pet,
    find_pet,
    name_taken,
    others_needing_care,
    pet_summaries,
)
from tama.services.session import SessionSettings
from tests.factories import FIXED_NOW, make_pet

SETTINGS = SessionSettings()
DEAD: dict[str, Any] = {"stage": LifeStage.DEAD, "cause_of_death": DeathCause.OLD_AGE}


def add(roster: PetRoster, name: str, **overrides: Any) -> None:
    pet = replace(make_pet(**overrides), name=name)
    roster.create(name).repo().save(SaveGame(pet, Random(0).getstate()))


def summaries(roster: PetRoster, clock: FakeClock | None = None) -> list[PetSummary]:
    return pet_summaries(roster, clock=clock or FakeClock(FIXED_NOW), settings=SETTINGS)


def test_every_pet_is_summarised_as_of_now_without_saving(tmp_path: Path) -> None:
    roster = PetRoster(tmp_path)
    add(roster, "Mochi", stats=Stats(hunger=30))
    before = {p.path: p.path.read_bytes() for p in roster.files()}
    clock = FakeClock(FIXED_NOW + timedelta(hours=2))

    [mochi] = summaries(roster, clock)

    assert mochi.pet is not None
    assert mochi.pet.updated_at == clock.now()
    assert AttentionReason.HUNGRY in mochi.needs
    assert {p.path: p.path.read_bytes() for p in roster.files()} == before
    assert not any(p.repo().backup_path.exists() for p in roster.files())


def test_the_last_pet_played_comes_first_then_by_name(tmp_path: Path) -> None:
    roster = PetRoster(tmp_path)
    for name in ("pip", "Bao", "Mochi"):
        add(roster, name)
    roster.set_last(next(p for p in roster.files() if p.key.startswith("mochi")))

    names = [s.name for s in summaries(roster)]

    assert names == ["Mochi", "Bao", "pip"]
    assert [s.last for s in summaries(roster)] == [True, False, False]


def test_pets_that_have_passed_away_come_last_even_if_played_last(tmp_path: Path) -> None:
    roster = PetRoster(tmp_path)
    add(roster, "Aldo", **DEAD)
    add(roster, "Zed", **DEAD)
    add(roster, "Mochi")
    add(roster, "Bao")
    roster.set_last(next(p for p in roster.files() if p.key.startswith("zed")))

    rows = summaries(roster)

    assert [s.name for s in rows] == ["Bao", "Mochi", "Zed", "Aldo"]
    assert rows[2].last


def test_an_unreadable_pet_is_listed_with_its_error(tmp_path: Path) -> None:
    roster = PetRoster(tmp_path)
    add(roster, "Mochi")
    broken = roster.directory / "broken-abcdef.json"
    broken.write_text("{ nope", encoding="utf-8")

    rows = summaries(roster)

    bad = next(s for s in rows if s.pet is None)
    assert bad.name == "broken-abcdef"
    assert isinstance(bad.error, CorruptSaveError)
    assert not bad.alive
    assert not bad.needs_care


def test_others_needing_care_skips_the_open_pet_dead_and_paused_pets(tmp_path: Path) -> None:
    roster = PetRoster(tmp_path)
    add(roster, "Open", stats=Stats(hunger=5))
    add(roster, "Hungry", stats=Stats(hunger=5))
    add(roster, "Fine")
    add(roster, "Gone", **DEAD)
    add(roster, "Away", stats=Stats(hunger=5), paused_since=FIXED_NOW)
    open_pet = next(p for p in roster.files() if p.key.startswith("open"))

    count = others_needing_care(
        roster, open_pet=open_pet, clock=FakeClock(FIXED_NOW), settings=SETTINGS
    )

    assert count == 1


def test_living_names_are_unique_but_dead_ones_can_be_reused(tmp_path: Path) -> None:
    roster = PetRoster(tmp_path)
    add(roster, "Mochi")
    add(roster, "Old", **DEAD)
    rows = summaries(roster)

    assert name_taken(rows, "mochi")
    assert name_taken(rows, "  MOCHI ")
    assert not name_taken(rows, "Old")
    assert not name_taken(rows, "Pip")


def test_at_most_nine_pets(tmp_path: Path) -> None:
    roster = PetRoster(tmp_path)
    for i in range(MAX_PETS - 1):
        add(roster, f"Pet{i}")
    assert can_add_pet(summaries(roster))

    add(roster, "Ninth")

    assert MAX_PETS == 9
    assert not can_add_pet(summaries(roster))


# --- Finding a pet by name (--pet) --------------------------------------------------------


@pytest.fixture
def rows(tmp_path: Path) -> list[PetSummary]:
    roster = PetRoster(tmp_path)
    add(roster, "Mochi")
    add(roster, "Momo")
    add(roster, "Mochi II")
    add(roster, "Pip", **DEAD)
    add(roster, "Pipsqueak")
    return summaries(roster)


@pytest.mark.parametrize(
    ("query", "found"),
    [
        ("Mochi", "Mochi"),  # exact beats being a prefix of "Mochi II"
        ("mochi ii", "Mochi II"),
        ("MOM", "Momo"),  # unique prefix
        ("pips", "Pipsqueak"),
        ("Pip", "Pip"),  # exact, even though dead
        ("pi", "Pipsqueak"),  # a living pet before a dead one
    ],
)
def test_find_pet(rows: list[PetSummary], query: str, found: str) -> None:
    assert find_pet(rows, query).name == found


@pytest.mark.parametrize(("query", "message"), [("mo", "matches several"), ("Zed", "no pet")])
def test_find_pet_explains_what_went_wrong(
    rows: list[PetSummary], query: str, message: str
) -> None:
    with pytest.raises(UnknownPetError, match=message) as caught:
        find_pet(rows, query)

    assert "Mochi, Mochi II, Momo, Pip, Pipsqueak" in str(caught.value)


def test_summarising_nine_pets_after_a_night_away_is_quick(tmp_path: Path) -> None:
    # SPEC §6.1: startup loads and simulates every pet; measured at ~0.4 s, so 4 s means trouble.
    roster = PetRoster(tmp_path)
    for i in range(MAX_PETS):
        add(roster, f"Pet{i}", stage=LifeStage.ADULT)
    clock = FakeClock(FIXED_NOW + timedelta(hours=8))

    started = time.perf_counter()
    rows = summaries(roster, clock)

    assert time.perf_counter() - started < 4
    assert all(row.alive for row in rows)
