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
