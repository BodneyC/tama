import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from random import Random
from typing import Any

import pytest
from hypothesis import given

from tama.domain.pet import Pet
from tama.errors import (
    CorruptSaveError,
    SaveNotFoundError,
    SaveWriteError,
    UnsupportedSaveVersionError,
)
from tama.persistence.codec import encode
from tama.persistence.models import SaveGame
from tama.persistence.repository import JsonSaveRepository, SaveRepository
from tests.factories import FIXED_NOW, make_pet
from tests.strategies import pets, rng_states


def game(name: str = "Mochi") -> SaveGame:
    return SaveGame(make_pet(name=name), Random(0).getstate())


@pytest.fixture
def repo(tmp_path: Path) -> JsonSaveRepository:
    return JsonSaveRepository(tmp_path / "data" / "save.json")


def test_satisfies_protocol(repo: JsonSaveRepository) -> None:
    assert isinstance(repo, SaveRepository)


# --- Round trip (M2 acceptance) -------------------------------------------------------------


@given(pets(), rng_states())
def test_load_after_save_returns_the_same_game(pet: Pet, rng_state: Any) -> None:
    # tempfile rather than tmp_path: hypothesis reuses function-scoped fixtures across examples.
    with tempfile.TemporaryDirectory() as tmp:
        repository = JsonSaveRepository(Path(tmp) / "save.json")
        original = SaveGame(pet, rng_state)

        repository.save(original)
        loaded = repository.load()

    assert loaded.game == original
    assert not loaded.from_backup


# --- Saving -----------------------------------------------------------------------------------


def test_save_creates_missing_directories(repo: JsonSaveRepository) -> None:
    repo.save(game())

    assert repo.path.read_text(encoding="utf-8") == encode(game())


def test_second_save_rotates_previous_into_backup(repo: JsonSaveRepository) -> None:
    repo.save(game("First"))
    repo.save(game("Second"))

    assert repo.load().game.pet.name == "Second"
    assert json.loads(repo.backup_path.read_text(encoding="utf-8"))["pet"]["name"] == "First"


def test_save_leaves_no_temporary_files(repo: JsonSaveRepository) -> None:
    repo.save(game())
    repo.save(game())

    assert sorted(p.name for p in repo.path.parent.iterdir()) == ["save.json", "save.json.bak"]


def test_unwritable_location_raises_save_write_error(tmp_path: Path) -> None:
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("")
    repository = JsonSaveRepository(blocker / "save.json")

    with pytest.raises(SaveWriteError, match="not-a-dir"):
        repository.save(game())


def test_failed_write_keeps_existing_save_and_cleans_up(
    repo: JsonSaveRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo.save(game("Original"))

    def failing_replace(*_args: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", failing_replace)

    with pytest.raises(SaveWriteError, match="disk full"):
        repo.save(game("Lost"))

    monkeypatch.undo()
    assert repo.load().game.pet.name == "Original"
    assert sorted(p.name for p in repo.path.parent.iterdir()) == ["save.json"]


# --- Loading ----------------------------------------------------------------------------------


def test_missing_save(repo: JsonSaveRepository) -> None:
    assert not repo.exists()
    with pytest.raises(SaveNotFoundError):
        repo.load()


def corrupt(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ this is not json", encoding="utf-8")


def write_backup(repo: JsonSaveRepository, name: str = "Backup") -> None:
    repo.backup_path.parent.mkdir(parents=True, exist_ok=True)
    repo.backup_path.write_text(encode(game(name)), encoding="utf-8")


@pytest.mark.parametrize(
    "break_primary",
    [corrupt, lambda p: None, lambda p: p.mkdir(parents=True)],
    ids=["corrupt", "missing", "unreadable"],
)
def test_falls_back_to_backup(
    repo: JsonSaveRepository, break_primary: Callable[[Path], None]
) -> None:
    write_backup(repo)
    break_primary(repo.path)

    loaded = repo.load()

    assert repo.exists()
    assert loaded.from_backup
    assert loaded.game.pet.name == "Backup"


def test_corrupt_primary_without_backup(repo: JsonSaveRepository) -> None:
    corrupt(repo.path)

    with pytest.raises(CorruptSaveError, match=r"save\.json"):
        repo.load()


def test_corrupt_backup_without_primary(repo: JsonSaveRepository) -> None:
    corrupt(repo.backup_path)

    with pytest.raises(CorruptSaveError, match=r"save\.json\.bak"):
        repo.load()


def test_both_corrupt(repo: JsonSaveRepository) -> None:
    corrupt(repo.path)
    corrupt(repo.backup_path)

    with pytest.raises(CorruptSaveError, match="backup"):
        repo.load()


def test_newer_save_is_not_silently_replaced_by_backup(repo: JsonSaveRepository) -> None:
    write_backup(repo)
    raw = json.loads(encode(game()))
    raw["schema_version"] = 99
    repo.path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(UnsupportedSaveVersionError):
        repo.load()


# --- Quarantine -------------------------------------------------------------------------------


def test_quarantine_moves_bad_files_aside(repo: JsonSaveRepository) -> None:
    corrupt(repo.path)
    corrupt(repo.backup_path)

    moved = repo.quarantine(FIXED_NOW)

    assert [p.name for p in moved] == [
        "save.json.corrupt-20260101T120000",
        "save.json.bak.corrupt-20260101T120000",
    ]
    assert all(p.exists() for p in moved)
    assert not repo.exists()


def test_quarantine_with_nothing_to_move(repo: JsonSaveRepository) -> None:
    assert repo.quarantine(FIXED_NOW) == []


def test_quarantine_failure_raises_save_write_error(
    repo: JsonSaveRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    corrupt(repo.path)

    def failing_replace(*_args: object) -> None:
        raise OSError("read-only")

    monkeypatch.setattr(os, "replace", failing_replace)

    with pytest.raises(SaveWriteError, match="read-only"):
        repo.quarantine(FIXED_NOW)
