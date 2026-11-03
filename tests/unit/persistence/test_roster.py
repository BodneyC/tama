import json
import os
from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta
from itertools import count
from pathlib import Path
from random import Random
from typing import Any

import pytest

from tama.persistence.models import SaveGame
from tama.persistence.repository import JsonSaveRepository
from tama.persistence.roster import PetRoster, slugify
from tests.factories import FIXED_NOW, make_pet


def ids() -> Callable[[], str]:
    """Stable ids for tests: 000001, 000002, ..."""
    numbers = count(1)
    return lambda: f"{next(numbers):06x}"


def roster(tmp_path: Path) -> PetRoster:
    return PetRoster(tmp_path, new_id=ids())


def write(path: Path, name: str = "Mochi", **overrides: Any) -> None:
    pet = replace(make_pet(), name=name, **overrides)
    JsonSaveRepository(path).save(SaveGame(pet, Random(0).getstate()))


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("Mochi", "mochi"),
        ("Mr Whiskers", "mr-whiskers"),
        ("Zoë", "zoe"),
        ("../../etc", "etc"),
        ("a/b\\c", "a-b-c"),
        ("🐣", "pet"),
        ("  ", "pet"),
        ("x" * 40, "x" * 24),
    ],
)
def test_names_become_safe_file_names(name: str, slug: str) -> None:
    assert slugify(name) == slug


def test_an_empty_roster(tmp_path: Path) -> None:
    pets = roster(tmp_path)

    assert pets.files() == []
    assert pets.last() is None


def test_a_new_pet_gets_its_own_file(tmp_path: Path) -> None:
    pets = roster(tmp_path)

    first = pets.create("Mr Whiskers")
    second = pets.create("Mr Whiskers")

    assert first.path == tmp_path / "pets" / "mr-whiskers-000001.json"
    assert second.path == tmp_path / "pets" / "mr-whiskers-000002.json"
    assert not first.path.exists()  # created on first save


def test_listing_finds_saves_and_lone_backups_but_nothing_else(tmp_path: Path) -> None:
    pets = roster(tmp_path)
    write(pets.directory / "mochi-aaaaaa.json")
    write(pets.directory / "mochi-aaaaaa.json")  # now has a .bak too
    (pets.directory / "pip-bbbbbb.json.bak").write_text("{}", encoding="utf-8")
    (pets.directory / "last.json").write_text("{}", encoding="utf-8")
    (pets.directory / "mochi-aaaaaa.json.lock").write_text("1", encoding="utf-8")
    (pets.directory / "notes.txt").write_text("hi", encoding="utf-8")
    (pets.directory / "archive").mkdir()
    write(pets.directory / "archive" / "old-cccccc.json")

    names = [pet.path.name for pet in pets.files()]

    assert names == ["mochi-aaaaaa.json", "pip-bbbbbb.json"]


def test_the_last_played_pet_is_remembered(tmp_path: Path) -> None:
    pets = roster(tmp_path)
    write(pets.directory / "a-000001.json")
    write(pets.directory / "b-000002.json")
    b = pets.files()[1]

    pets.set_last(b)

    assert pets.last() == b
    assert json.loads((pets.directory / "last.json").read_text()) == {"file": "b-000002.json"}


@pytest.mark.parametrize("last", ["{ nope", '{"file": "gone.json"}', '{"file": 3}', "[]", None])
def test_without_a_usable_last_json_the_latest_save_is_used(
    tmp_path: Path, last: str | None
) -> None:
    pets = roster(tmp_path)
    write(pets.directory / "a-000001.json")
    write(pets.directory / "b-000002.json")
    old = (pets.directory / "b-000002.json").stat().st_mtime - 60
    os.utime(pets.directory / "b-000002.json", (old, old))
    if last is not None:
        (pets.directory / "last.json").write_text(last, encoding="utf-8")

    latest = pets.last()

    assert latest is not None
    assert latest.path.name == "a-000001.json"


def test_archiving_moves_a_pets_files_away(tmp_path: Path) -> None:
    pets = roster(tmp_path)
    path = pets.directory / "mochi-aaaaaa.json"
    write(path)
    write(path)
    pet = pets.files()[0]

    moved = pets.archive(pet)

    assert pets.files() == []
    assert sorted(p.name for p in moved) == ["mochi-aaaaaa.json", "mochi-aaaaaa.json.bak"]
    assert all(p.parent == pets.directory / "archive" and p.exists() for p in moved)


def test_archiving_never_overwrites_an_earlier_archive(tmp_path: Path) -> None:
    pets = roster(tmp_path)
    path = pets.directory / "mochi-aaaaaa.json"
    write(path, name="First")
    pets.archive(pets.files()[0])
    write(path, name="Second")

    moved = pets.archive(pets.files()[0])

    assert len(list((pets.directory / "archive").glob("mochi-aaaaaa*.json"))) == 2
    assert moved[0].name != "mochi-aaaaaa.json"


# --- Upgrading from a single save.json ----------------------------------------------------


def test_a_legacy_save_moves_into_the_roster_and_is_last_played(tmp_path: Path) -> None:
    legacy = tmp_path / "save.json"
    write(legacy, name="Old Timer")
    write(legacy, name="Old Timer")  # with a backup
    pets = roster(tmp_path)

    migrated = pets.migrate_legacy(legacy)

    assert migrated is not None
    assert migrated.path.parent == pets.directory
    assert migrated.path.name.startswith("old-timer-")
    assert migrated.repo().load().game.pet.name == "Old Timer"
    assert migrated.repo().backup_path.exists()
    assert not legacy.exists()
    assert not legacy.with_name("save.json.bak").exists()
    assert pets.last() == migrated


def test_legacy_migration_is_idempotent(tmp_path: Path) -> None:
    legacy = tmp_path / "save.json"
    write(legacy)
    pets = roster(tmp_path)

    first = pets.migrate_legacy(legacy)
    again = pets.migrate_legacy(legacy)

    assert first is not None
    assert again is None
    assert pets.files() == [first]


def test_an_interrupted_legacy_move_finishes_without_losing_a_file(tmp_path: Path) -> None:
    legacy = tmp_path / "save.json"
    write(legacy, name="Mochi")
    write(legacy, name="Mochi")
    pets = roster(tmp_path)
    # Simulate a crash after the backup moved but before the save did.
    target = pets.legacy_target(legacy)
    target.parent.mkdir(parents=True, exist_ok=True)
    legacy.with_name("save.json.bak").replace(target.with_name(target.name + ".bak"))

    migrated = pets.migrate_legacy(legacy)

    assert migrated is not None
    assert migrated.path == target
    assert target.exists()
    assert target.with_name(target.name + ".bak").exists()
    assert pets.files() == [migrated]


def test_an_unreadable_legacy_save_still_moves(tmp_path: Path) -> None:
    legacy = tmp_path / "save.json"
    legacy.write_text("{ nope", encoding="utf-8")
    pets = roster(tmp_path)

    migrated = pets.migrate_legacy(legacy)

    assert migrated is not None
    assert migrated.path.name == "pet-legacy.json"
    assert migrated.path.read_text(encoding="utf-8") == "{ nope"


def test_no_legacy_save_means_nothing_to_do(tmp_path: Path) -> None:
    assert roster(tmp_path).migrate_legacy(tmp_path / "save.json") is None


def test_the_legacy_target_depends_only_on_the_pet(tmp_path: Path) -> None:
    legacy = tmp_path / "save.json"
    write(legacy, born_at=FIXED_NOW)
    a = roster(tmp_path).legacy_target(legacy)
    write(legacy, born_at=FIXED_NOW, updated_at=FIXED_NOW + timedelta(hours=1))

    assert roster(tmp_path).legacy_target(legacy) == a
