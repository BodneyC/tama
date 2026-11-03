import json
from random import Random
from typing import Any

import pytest
from hypothesis import given
from pydantic import ValidationError

from tama.domain.pet import Pet
from tama.errors import CorruptSaveError
from tama.persistence.models import CURRENT_SCHEMA_VERSION, SaveFileV2, SaveGame, restore_rng
from tests.factories import make_pet
from tests.strategies import pets, rng_states


def dump(game: SaveGame) -> dict[str, Any]:
    raw: dict[str, Any] = json.loads(SaveFileV2.from_domain(game).model_dump_json())
    return raw


@given(pets(), rng_states())
def test_round_trip_through_json_is_exact(pet: Pet, rng_state: Any) -> None:
    game = SaveGame(pet, rng_state)

    text = SaveFileV2.from_domain(game).model_dump_json()

    assert SaveFileV2.model_validate_json(text).to_domain() == game


def test_schema_version_is_written() -> None:
    raw = dump(SaveGame(make_pet(), Random(0).getstate()))

    assert raw["schema_version"] == CURRENT_SCHEMA_VERSION == 2
    assert raw["pet"]["species"] == "tama"


def test_fractions_and_durations_are_human_readable() -> None:
    raw = dump(SaveGame(make_pet(), Random(0).getstate()))

    assert raw["pet"]["lifespan"].startswith("P")
    assert raw["pet"]["drift"]["hunger"] == "0"
    assert raw["pet"]["stage"] == "child"


def test_restored_rng_continues_the_same_sequence() -> None:
    rng = Random(42)
    rng.random()
    game = SaveGame(make_pet(), rng.getstate())

    restored = restore_rng(
        SaveFileV2.model_validate_json(SaveFileV2.from_domain(game).model_dump_json())
        .to_domain()
        .rng_state
    )

    assert [restored.random() for _ in range(5)] == [rng.random() for _ in range(5)]


def test_unknown_fields_are_rejected() -> None:
    raw = dump(SaveGame(make_pet(), Random(0).getstate()))
    raw["pet"]["favourite_colour"] = "blue"

    with pytest.raises(ValidationError):
        SaveFileV2.model_validate(raw)


def test_naive_timestamps_are_rejected() -> None:
    raw = dump(SaveGame(make_pet(), Random(0).getstate()))
    raw["pet"]["born_at"] = "2026-01-01T12:00:00"

    with pytest.raises(ValidationError):
        SaveFileV2.model_validate(raw)


def test_domain_invariant_violations_become_corrupt_save_errors() -> None:
    raw = dump(SaveGame(make_pet(), Random(0).getstate()))
    raw["pet"]["stats"]["hunger"] = 500

    with pytest.raises(CorruptSaveError, match="hunger"):
        SaveFileV2.model_validate(raw).to_domain()


@pytest.mark.parametrize(
    "internal", [[1, 2, 3], [0] * 624 + [1000]], ids=["too-short", "bad-position"]
)
def test_invalid_rng_state_becomes_corrupt_save_error(internal: list[int]) -> None:
    raw = dump(SaveGame(make_pet(), Random(0).getstate()))
    raw["rng"]["internal"] = internal

    with pytest.raises(CorruptSaveError, match="RNG"):
        SaveFileV2.model_validate(raw).to_domain()
