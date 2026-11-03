import json
from datetime import UTC, datetime, timedelta
from fractions import Fraction
from pathlib import Path
from random import Random
from typing import Any

import pytest

from tama.domain.stage import LifeStage
from tama.domain.stats import Stats
from tama.errors import CorruptSaveError, UnsupportedSaveVersionError
from tama.persistence.codec import decode, encode
from tama.persistence.models import SaveGame, restore_rng
from tests.factories import make_pet

FIXTURES = Path(__file__).parents[2] / "fixtures" / "saves"


def test_encode_is_indented_json_with_trailing_newline() -> None:
    text = encode(SaveGame(make_pet(), Random(0).getstate()))

    assert text.startswith('{\n  "schema_version": 1,')
    assert text.endswith("}\n")


def test_decode_inverts_encode() -> None:
    game = SaveGame(make_pet(), Random(0).getstate())

    assert decode(encode(game)) == game


@pytest.mark.parametrize("text", ["", "{", "not json", "[1, 2]", '{"schema_version": 1}'])
def test_invalid_text_is_corrupt(text: str) -> None:
    with pytest.raises(CorruptSaveError):
        decode(text)


def test_newer_schema_is_unsupported() -> None:
    raw = json.loads(encode(SaveGame(make_pet(), Random(0).getstate())))
    raw["schema_version"] = 2

    with pytest.raises(UnsupportedSaveVersionError):
        decode(json.dumps(raw))


# --- Fixtures from real older versions ------------------------------------------------------


def test_v1_fixture_loads() -> None:
    game = decode((FIXTURES / "v1.json").read_text())
    pet = game.pet

    assert pet.name == "Fixture"
    assert pet.stage is LifeStage.TEEN
    assert pet.born_at == datetime(2026, 1, 1, 12, tzinfo=UTC)
    assert pet.age == timedelta(days=1, hours=2, minutes=54)
    assert pet.carry == timedelta(seconds=32)
    assert pet.stats == Stats(
        hunger=47, happiness=58, energy=66, hygiene=58, health=73, discipline=0
    )
    assert pet.drift.energy == Fraction(-4, 5)
    assert pet.poop_progress == Fraction(9, 20)
    assert pet.sickness_doses == 1
    assert pet.recent_snacks == (timedelta(days=1, hours=2, minutes=13),)
    assert restore_rng(game.rng_state).random() == 0.6715634814879851


def test_v1_fixture_reencodes_identically() -> None:
    """Guards the v1 format against accidental changes (which would need a migration)."""
    text = (FIXTURES / "v1.json").read_text()
    original: dict[str, Any] = json.loads(text)

    reencoded: dict[str, Any] = json.loads(encode(decode(text)))

    original.pop("app_version")
    reencoded.pop("app_version")
    assert reencoded == original
