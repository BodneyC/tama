import json
from datetime import UTC, datetime, timedelta
from fractions import Fraction
from pathlib import Path
from random import Random
from typing import Any

import pytest

from tama.domain.journal import GameTally, Topic
from tama.domain.minigames import GameKind
from tama.domain.stage import LifeStage
from tama.domain.stats import Stats
from tama.errors import CorruptSaveError, UnsupportedSaveVersionError
from tama.persistence.codec import decode, encode
from tama.persistence.models import CURRENT_SCHEMA_VERSION, SaveGame, restore_rng
from tests.factories import make_pet

FIXTURES = Path(__file__).parents[2] / "fixtures" / "saves"


def test_encode_is_indented_json_with_trailing_newline() -> None:
    text = encode(SaveGame(make_pet(), Random(0).getstate()))

    assert text.startswith('{\n  "schema_version": 6,')
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
    raw["schema_version"] = CURRENT_SCHEMA_VERSION + 1

    with pytest.raises(UnsupportedSaveVersionError):
        decode(json.dumps(raw))


# --- Fixtures from real older versions ------------------------------------------------------


def assert_v5_fields_added(upgraded: dict[str, Any]) -> None:
    """Pop v5's weight fields from an upgraded save, checking they start at zero."""
    assert upgraded["pet"].pop("weight_progress") == "0"
    assert upgraded["pet"]["timers"].pop("weight") == "PT0S"


def assert_v6_journal_added(upgraded: dict[str, Any]) -> None:
    """Pop v6's journal from an upgraded save, checking it starts as of the pet's last update."""
    journal = upgraded.pop("journal")
    assert journal["entries"] == [
        {
            "kind": "life",
            "topic": "journal_started",
            "at": upgraded["pet"]["updated_at"],
            "age": upgraded["pet"]["age"],
            "detail": "",
        }
    ]
    assert set(journal["tallies"].pop("games")) == set()
    assert set(journal["tallies"].values()) == {0}


def test_v1_fixture_loads() -> None:
    game = decode((FIXTURES / "v1.json").read_text())
    pet = game.pet

    assert pet.name == "Fixture"
    assert pet.species == "tama"
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


def test_v1_fixture_migrates_losslessly() -> None:
    """Only the version and the new fields change when a v1 save is upgraded."""
    original: dict[str, Any] = json.loads((FIXTURES / "v1.json").read_text())

    upgraded: dict[str, Any] = json.loads(encode(decode((FIXTURES / "v1.json").read_text())))

    for raw in (original, upgraded):
        raw.pop("app_version")
    assert upgraded["schema_version"] == CURRENT_SCHEMA_VERSION
    assert upgraded["pet"].pop("species") == "tama"
    assert upgraded["pet"].pop("paused_since") is None
    assert upgraded["pet"].pop("stay_awake") == "PT0S"
    assert upgraded["pet"].pop("woken_tantrum") is False
    assert_v5_fields_added(upgraded)
    assert_v6_journal_added(upgraded)
    assert {**upgraded, "schema_version": 1} == original


def test_v2_fixture_loads_its_species() -> None:
    game = decode((FIXTURES / "v2.json").read_text())

    assert game.pet.species == "owl"
    assert game.pet.name == "Fixture"


def test_v2_fixture_migrates_losslessly() -> None:
    """Only the version and the new holiday field change when a v2 save is upgraded."""
    original: dict[str, Any] = json.loads((FIXTURES / "v2.json").read_text())

    upgraded: dict[str, Any] = json.loads(encode(decode((FIXTURES / "v2.json").read_text())))

    for raw in (original, upgraded):
        raw.pop("app_version")
    assert upgraded["schema_version"] == CURRENT_SCHEMA_VERSION
    assert upgraded["pet"].pop("paused_since") is None
    assert upgraded["pet"].pop("stay_awake") == "PT0S"
    assert upgraded["pet"].pop("woken_tantrum") is False
    assert_v5_fields_added(upgraded)
    assert_v6_journal_added(upgraded)
    assert {**upgraded, "schema_version": 2} == original


def test_v3_fixture_loads_a_pet_on_holiday() -> None:
    game = decode((FIXTURES / "v3.json").read_text())

    assert game.pet.on_holiday
    assert game.pet.paused_since == datetime(2026, 1, 1, 14, 54, 32, tzinfo=UTC)


def test_v3_fixture_migrates_losslessly() -> None:
    """Only the version and the new waking fields change when a v3 save is upgraded."""
    original: dict[str, Any] = json.loads((FIXTURES / "v3.json").read_text())

    upgraded: dict[str, Any] = json.loads(encode(decode((FIXTURES / "v3.json").read_text())))

    for raw in (original, upgraded):
        raw.pop("app_version")
    assert upgraded["schema_version"] == CURRENT_SCHEMA_VERSION
    assert upgraded["pet"].pop("stay_awake") == "PT0S"
    assert upgraded["pet"].pop("woken_tantrum") is False
    assert_v5_fields_added(upgraded)
    assert_v6_journal_added(upgraded)
    assert {**upgraded, "schema_version": 3} == original


def test_v4_fixture_loads_a_woken_pet() -> None:
    pet = decode((FIXTURES / "v4.json").read_text()).pet

    assert pet.stay_awake == timedelta(minutes=17)
    assert pet.woken_tantrum
    assert pet.misbehaving
    assert not pet.is_asleep


def test_v4_fixture_migrates_losslessly() -> None:
    """Only the version and the new weight fields change when a v4 save is upgraded."""
    original: dict[str, Any] = json.loads((FIXTURES / "v4.json").read_text())

    upgraded: dict[str, Any] = json.loads(encode(decode((FIXTURES / "v4.json").read_text())))

    for raw in (original, upgraded):
        raw.pop("app_version")
    assert upgraded["schema_version"] == CURRENT_SCHEMA_VERSION
    assert_v5_fields_added(upgraded)
    assert_v6_journal_added(upgraded)
    assert {**upgraded, "schema_version": 4} == original


def test_v5_fixture_loads_weight_burn_and_episode() -> None:
    pet = decode((FIXTURES / "v5.json").read_text()).pet

    assert pet.weight_progress == Fraction(7, 16)
    assert pet.timers.weight == timedelta(hours=3, minutes=5)


def test_v5_fixture_migrates_losslessly() -> None:
    """Only the version and the new journal change when a v5 save is upgraded."""
    original: dict[str, Any] = json.loads((FIXTURES / "v5.json").read_text())

    upgraded: dict[str, Any] = json.loads(encode(decode((FIXTURES / "v5.json").read_text())))

    for raw in (original, upgraded):
        raw.pop("app_version")
    assert upgraded["schema_version"] == CURRENT_SCHEMA_VERSION
    assert_v6_journal_added(upgraded)
    assert {**upgraded, "schema_version": 5} == original


def test_v6_fixture_loads_its_journal() -> None:
    journal = decode((FIXTURES / "v6.json").read_text()).journal

    assert [e.topic for e in journal.entries] == [Topic.HATCHED, Topic.MEAL, Topic.WIN]
    assert journal.entries[2].detail == "four_in_a_row"
    assert journal.tallies.meals == 3
    assert journal.tallies.game(GameKind.FOUR_IN_A_ROW) == GameTally(won=1, lost=2)


def test_v6_fixture_reencodes_identically() -> None:
    """Guards the v6 format against accidental changes (which would need a migration)."""
    text = (FIXTURES / "v6.json").read_text()
    original: dict[str, Any] = json.loads(text)

    reencoded: dict[str, Any] = json.loads(encode(decode(text)))

    original.pop("app_version")
    reencoded.pop("app_version")
    assert reencoded == original
