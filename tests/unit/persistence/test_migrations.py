from typing import Any

import pytest

from tama.errors import CorruptSaveError, UnsupportedSaveVersionError
from tama.persistence.migrations import MIGRATIONS, migrate
from tama.persistence.models import CURRENT_SCHEMA_VERSION


def test_every_old_version_has_a_migration() -> None:
    assert set(MIGRATIONS) == set(range(1, CURRENT_SCHEMA_VERSION))


def test_current_version_is_returned_unchanged() -> None:
    raw = {"schema_version": CURRENT_SCHEMA_VERSION, "pet": {"name": "Mochi"}}

    assert migrate(raw) == raw


def test_migrations_are_chained_in_order() -> None:
    def v1_to_v2(raw: dict[str, Any]) -> dict[str, Any]:
        return {**raw, "steps": [*raw["steps"], "1->2"]}

    def v2_to_v3(raw: dict[str, Any]) -> dict[str, Any]:
        return {**raw, "steps": [*raw["steps"], "2->3"]}

    out = migrate(
        {"schema_version": 1, "steps": []}, current=3, migrations={1: v1_to_v2, 2: v2_to_v3}
    )

    assert out == {"schema_version": 3, "steps": ["1->2", "2->3"]}


def test_migration_does_not_mutate_input() -> None:
    raw = {"schema_version": 1, "x": 1}

    migrate(raw, current=2, migrations={1: lambda r: {**r, "x": 2}})

    assert raw == {"schema_version": 1, "x": 1}


@pytest.mark.parametrize(
    ("pet", "expected"),
    [({"name": "Mochi"}, {"species": "tama", "name": "Mochi"}), ("not a pet", "not a pet")],
)
def test_v1_saves_become_tamas(pet: object, expected: object) -> None:
    out = migrate({"schema_version": 1, "pet": pet}, current=2)

    assert out == {"schema_version": 2, "pet": expected}


@pytest.mark.parametrize(
    ("pet", "expected"),
    [
        ({"name": "Mochi"}, {"name": "Mochi", "paused_since": None}),
        ({"paused_since": "x"}, {"paused_since": "x"}),
        ("not a pet", "not a pet"),
    ],
)
def test_v2_saves_are_not_on_holiday(pet: object, expected: object) -> None:
    out = migrate({"schema_version": 2, "pet": pet}, current=3)

    assert out == {"schema_version": 3, "pet": expected}


@pytest.mark.parametrize(
    ("pet", "expected"),
    [
        ({"name": "Mochi"}, {"stay_awake": "PT0S", "woken_tantrum": False, "name": "Mochi"}),
        (
            {"stay_awake": "PT5M", "woken_tantrum": True},
            {"stay_awake": "PT5M", "woken_tantrum": True},
        ),
        ("not a pet", "not a pet"),
    ],
)
def test_v3_saves_were_never_woken(pet: object, expected: object) -> None:
    out = migrate({"schema_version": 3, "pet": pet}, current=4)

    assert out == {"schema_version": 4, "pet": expected}


@pytest.mark.parametrize(
    ("pet", "expected"),
    [
        (
            {"name": "Mochi", "timers": {"hunger": "PT0S"}},
            {
                "weight_progress": "0",
                "name": "Mochi",
                "timers": {"weight": "PT0S", "hunger": "PT0S"},
            },
        ),
        (
            {"weight_progress": "1/2", "timers": {"weight": "PT1H"}},
            {"weight_progress": "1/2", "timers": {"weight": "PT1H"}},
        ),
        ({"timers": "not timers"}, {"weight_progress": "0", "timers": "not timers"}),
        ("not a pet", "not a pet"),
    ],
)
def test_v4_saves_had_burned_no_weight(pet: object, expected: object) -> None:
    out = migrate({"schema_version": 4, "pet": pet}, current=5)

    assert out == {"schema_version": 5, "pet": expected}


def test_v5_saves_start_a_journal_as_of_their_last_update() -> None:
    pet = {"updated_at": "2026-01-01T12:00:00Z", "age": "PT1H"}

    out = migrate({"schema_version": 5, "pet": pet}, current=6)

    assert out["journal"]["entries"] == [
        {
            "kind": "life",
            "topic": "journal_started",
            "at": "2026-01-01T12:00:00Z",
            "age": "PT1H",
            "detail": "",
        }
    ]
    assert out["journal"]["tallies"]["meals"] == 0


@pytest.mark.parametrize(
    "raw",
    [{"schema_version": 5, "pet": "not a pet"}, {"schema_version": 5, "pet": {}, "journal": 1}],
    ids=["malformed", "already-has-one"],
)
def test_v5_saves_that_cannot_start_a_journal_are_left_for_validation(
    raw: dict[str, object],
) -> None:
    assert migrate(raw, current=6) == {**raw, "schema_version": 6}


@pytest.mark.parametrize(
    ("pet", "heir_hatched"),
    [
        ({"stage": "child", "cause_of_death": None}, False),
        ({"stage": "dead", "cause_of_death": "poor_health"}, False),
        ({"stage": "dead", "cause_of_death": "old_age"}, True),
    ],
    ids=["alive", "poor-health", "old-age"],
)
def test_v6_pets_founded_their_line_and_old_eggs_are_not_offered(
    pet: dict[str, object], heir_hatched: bool
) -> None:
    out = migrate({"schema_version": 6, "pet": pet}, current=7)

    assert out["pet"] == {"generation": 1, "ancestors": [], "heir_hatched": heir_hatched, **pet}


def test_v6_saves_without_a_pet_are_left_for_validation() -> None:
    assert migrate({"schema_version": 6, "pet": 3}, current=7) == {"schema_version": 7, "pet": 3}


def test_newer_saves_are_unsupported() -> None:
    with pytest.raises(UnsupportedSaveVersionError, match="v99"):
        migrate({"schema_version": 99})


@pytest.mark.parametrize(
    "raw",
    [[], "save", {}, {"schema_version": "1"}, {"schema_version": 0}, {"schema_version": True}],
)
def test_malformed_saves_are_corrupt(raw: object) -> None:
    with pytest.raises(CorruptSaveError):
        migrate(raw)
