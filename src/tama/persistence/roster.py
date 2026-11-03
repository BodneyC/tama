"""Several pets, one save file each, in ``<data dir>/pets/`` (ADR 0007, SPEC §6.1).

The directory listing *is* the list of pets: there is no index to fall out of step with the
saves. ``last.json`` only remembers which pet was played last, and losing it is harmless.
"""

import hashlib
import json
import logging
import os
import re
import secrets
import tempfile
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from tama.errors import SaveError, SaveWriteError
from tama.persistence.codec import decode
from tama.persistence.repository import JsonSaveRepository

logger = logging.getLogger(__name__)

PETS_DIR = "pets"
ARCHIVE_DIR = "archive"
LAST_FILE = "last.json"
SLUG_LENGTH = 24
_BACKUP = ".bak"


def slugify(name: str) -> str:
    """``name`` as a short, filename-safe slug (``Mr Whiskers`` → ``mr-whiskers``)."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug[:SLUG_LENGTH].strip("-") or "pet"


@dataclass(frozen=True, slots=True)
class PetFile:
    """One pet's save file (which may not exist yet, or only as a backup)."""

    path: Path

    @property
    def key(self) -> str:
        """The file name, which identifies the pet within the roster."""
        return self.path.name

    def repo(self) -> JsonSaveRepository:
        """A repository for loading and saving this pet."""
        return JsonSaveRepository(self.path)


class PetRoster:
    """Lists, creates and archives pet files, and remembers the last pet played."""

    def __init__(self, data_dir: Path, *, new_id: Callable[[], str] | None = None) -> None:
        """Keep pets under ``data_dir/pets``; ``new_id`` makes the random part of file names."""
        self.directory = data_dir / PETS_DIR
        self._new_id = new_id or (lambda: secrets.token_hex(3))

    def files(self) -> list[PetFile]:
        """Every pet, by file name; a pet whose save is missing but has a backup counts too."""
        if not self.directory.is_dir():
            return []
        names: set[str] = set()
        for entry in self.directory.iterdir():
            if not entry.is_file():
                continue
            name = entry.name.removesuffix(_BACKUP)
            if name.endswith(".json") and name != LAST_FILE and not name.startswith("."):
                names.add(name)
        return [PetFile(self.directory / name) for name in sorted(names)]

    def create(self, name: str) -> PetFile:
        """A new, unused file for a pet called ``name`` (written on its first save)."""
        while True:
            pet = PetFile(self.directory / f"{slugify(name)}-{self._new_id()}.json")
            if not pet.repo().exists():
                return pet

    def last(self) -> PetFile | None:
        """The pet played last: from ``last.json``, else the most recently saved one."""
        pets = self.files()
        if not pets:
            return None
        remembered = self._read_last()
        for pet in pets:
            if pet.key == remembered:
                return pet
        return max(pets, key=_modified)

    def set_last(self, pet: PetFile) -> None:
        """Remember ``pet`` as the one played last (best effort: failures are only logged)."""
        try:
            _write_atomically(self.directory / LAST_FILE, json.dumps({"file": pet.key}))
        except OSError:
            logger.exception("Could not remember the last pet played")

    def archive(self, pet: PetFile) -> list[Path]:
        """Move ``pet``'s files to ``pets/archive/`` (never deleted, never overwriting).

        Raises:
            SaveWriteError: If the files could not be moved.
        """
        archive = self.directory / ARCHIVE_DIR
        target = archive / pet.key
        number = 1
        while target.exists() or _backup_of(target).exists():
            number += 1
            target = archive / f"{pet.path.stem}-{number}.json"
        moved: list[Path] = []
        try:
            archive.mkdir(parents=True, exist_ok=True)
            for source, destination in (
                (pet.path, target),
                (_backup_of(pet.path), _backup_of(target)),
            ):
                if source.exists():
                    source.replace(destination)
                    moved.append(destination)
        except OSError as exc:
            raise SaveWriteError(f"could not archive {pet.path}: {exc}") from exc
        logger.info("Archived %s to %s", pet.key, target)
        return moved

    # --- Upgrading from a single save file ------------------------------------------------

    def legacy_target(self, legacy: Path) -> Path:
        """Where the pet in ``legacy`` (or its backup) moves to: the same answer every time.

        The id comes from the pet's name and birth time rather than at random, so a move that
        was interrupted half way finishes into the same file when tama next starts.
        """
        for source in (legacy, _backup_of(legacy)):
            try:
                pet = decode(source.read_text(encoding="utf-8")).pet
            except (OSError, UnicodeDecodeError, SaveError):
                continue
            digest = hashlib.sha256(f"{pet.name}|{pet.born_at.isoformat()}".encode()).hexdigest()
            return self.directory / f"{slugify(pet.name)}-{digest[:6]}.json"
        return self.directory / "pet-legacy.json"

    def migrate_legacy(self, legacy: Path) -> PetFile | None:
        """Move an old single ``save.json`` (and its ``.bak``) into the roster as last played.

        The backup moves first and the save second, each with an atomic rename, so an
        interrupted move leaves every file in one place or the other and finishes next time.
        Returns ``None`` if there was nothing to move.

        Raises:
            SaveWriteError: If the files could not be moved.
        """
        backup = _backup_of(legacy)
        if not legacy.exists() and not backup.exists():
            return None
        target = self.legacy_target(legacy)
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            if backup.exists():
                backup.replace(_backup_of(target))
            if legacy.exists():
                legacy.replace(target)
        except OSError as exc:
            raise SaveWriteError(f"could not move {legacy} into {self.directory}: {exc}") from exc
        logger.info("Moved the old save %s to %s", legacy, target)
        pet = PetFile(target)
        self.set_last(pet)
        return pet

    def _read_last(self) -> str | None:
        try:
            data = json.loads((self.directory / LAST_FILE).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        name = data.get("file") if isinstance(data, dict) else None
        return name if isinstance(name, str) else None


def _backup_of(path: Path) -> Path:
    return path.with_name(path.name + _BACKUP)


def _modified(pet: PetFile) -> float:
    times = [p.stat().st_mtime for p in (pet.path, _backup_of(pet.path)) if p.exists()]
    return max(times, default=0.0)


def _write_atomically(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            tmp_file.write(text)
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)
