"""Upgrading old save files to the current schema.

Migrations operate on the raw JSON object *before* validation, so each one only needs to
know the shape of the version it upgrades from. To bump the schema:

1. Add ``SaveFileV<N+1>`` and bump ``CURRENT_SCHEMA_VERSION`` in ``models.py``.
2. Register a function here under key ``N`` that turns a vN dict into a vN+1 dict.
3. Commit a real vN save to ``tests/fixtures/saves/`` and keep its loading test.
"""

from collections.abc import Callable, Mapping
from typing import Any

from tama.errors import CorruptSaveError, UnsupportedSaveVersionError
from tama.persistence.models import CURRENT_SCHEMA_VERSION

Migration = Callable[[dict[str, Any]], dict[str, Any]]

MIGRATIONS: dict[int, Migration] = {}
"""Key ``N`` upgrades a version-N save to version N+1."""


def migrate(
    raw: object,
    *,
    current: int = CURRENT_SCHEMA_VERSION,
    migrations: Mapping[int, Migration] = MIGRATIONS,
) -> dict[str, Any]:
    """Upgrade a decoded save to schema version ``current``.

    Raises:
        CorruptSaveError: If ``raw`` is not a save object with a valid version.
        UnsupportedSaveVersionError: If the save is newer than this version of tama.
    """
    if not isinstance(raw, dict):
        raise CorruptSaveError("save file is not a JSON object")
    version = raw.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise CorruptSaveError(f"save file has an invalid schema_version: {version!r}")
    if version > current:
        raise UnsupportedSaveVersionError(
            f"save file is schema v{version}, but this version of tama only reads up to v{current}"
        )
    upgraded: dict[str, Any] = dict(raw)
    for from_version in range(version, current):
        upgraded = migrations[from_version](upgraded)
        upgraded["schema_version"] = from_version + 1
    return upgraded
