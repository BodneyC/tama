"""Converting between ``SaveGame`` and save-file text."""

import json

from pydantic import ValidationError

from tama.errors import CorruptSaveError
from tama.persistence.migrations import migrate
from tama.persistence.models import SaveFileV2, SaveGame


def encode(game: SaveGame) -> str:
    """Serialize ``game`` as indented, human-readable JSON."""
    return SaveFileV2.from_domain(game).model_dump_json(indent=2) + "\n"


def decode(text: str) -> SaveGame:
    """Parse save-file text, migrating old schemas.

    Raises:
        CorruptSaveError: If the text is not a valid save.
        UnsupportedSaveVersionError: If the save is from a newer version of tama.
    """
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CorruptSaveError(f"save file is not valid JSON: {exc}") from exc
    try:
        model = SaveFileV2.model_validate(migrate(raw))
    except ValidationError as exc:
        raise CorruptSaveError(f"save file has invalid data: {exc}") from exc
    return model.to_domain()
