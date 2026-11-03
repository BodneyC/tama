"""Reading and writing the save file safely.

Writes are atomic: the new save goes to a temp file in the same directory, is fsynced, and
then replaces the old one, which is kept as ``<name>.bak``. A crash can therefore never
leave a half-written save. At worst the primary is briefly missing, and loading falls back
to the backup.
"""

import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from tama.errors import CorruptSaveError, SaveNotFoundError, SaveWriteError
from tama.persistence.codec import decode, encode
from tama.persistence.models import SaveGame

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LoadResult:
    """A loaded game, and whether it had to be recovered from the backup."""

    game: SaveGame
    from_backup: bool


@runtime_checkable
class SaveRepository(Protocol):
    """Somewhere a game can be saved to and loaded from."""

    def exists(self) -> bool:
        """Whether there is anything to load (a save or a backup)."""
        ...

    def load(self) -> LoadResult:
        """Load the game, falling back to the backup if the save is unusable.

        Raises:
            SaveNotFoundError: If there is no save or backup.
            CorruptSaveError: If nothing could be loaded.
            UnsupportedSaveVersionError: If the save is from a newer version of tama.
        """
        ...

    def save(self, game: SaveGame) -> None:
        """Save the game, keeping the previous save as a backup.

        Raises:
            SaveWriteError: If the game could not be written.
        """
        ...

    def quarantine(self, now: datetime) -> list[Path]:
        """Move unusable save files aside so a new game can start, returning their new paths.

        Raises:
            SaveWriteError: If the files could not be moved.
        """
        ...


class JsonSaveRepository:
    """Stores the game as a JSON file, with a ``.bak`` copy of the previous save."""

    def __init__(self, path: Path) -> None:
        """Use ``path`` for the save file; the backup lives next to it."""
        self.path = path
        self.backup_path = path.with_name(path.name + ".bak")

    def exists(self) -> bool:
        """Whether a save or backup is present (readable or not)."""
        return self.path.exists() or self.backup_path.exists()

    def load(self) -> LoadResult:
        """Load the save, or the backup if the save is missing, unreadable or corrupt."""
        try:
            return LoadResult(_read(self.path), from_backup=False)
        except (SaveNotFoundError, CorruptSaveError) as exc:
            primary_error = exc
        try:
            game = _read(self.backup_path)
        except SaveNotFoundError:
            raise primary_error from None
        except CorruptSaveError as backup_error:
            if isinstance(primary_error, SaveNotFoundError):
                raise
            raise CorruptSaveError(
                f"{primary_error}; the backup is also unusable: {backup_error}"
            ) from backup_error
        logger.warning("Recovered game from backup %s: %s", self.backup_path, primary_error)
        return LoadResult(game, from_backup=True)

    def save(self, game: SaveGame) -> None:
        """Atomically write ``game``, rotating the current save into the backup."""
        text = encode(game)
        directory = self.path.parent
        try:
            directory.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(dir=directory, prefix=f".{self.path.name}.")
            tmp = Path(tmp_name)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                    tmp_file.write(text)
                    tmp_file.flush()
                    os.fsync(tmp_file.fileno())
                if self.path.exists():
                    self.path.replace(self.backup_path)
                tmp.replace(self.path)
            finally:
                tmp.unlink(missing_ok=True)
            _fsync_directory(directory)
        except OSError as exc:
            raise SaveWriteError(f"could not save to {self.path}: {exc}") from exc

    def quarantine(self, now: datetime) -> list[Path]:
        """Rename the save and backup to ``<name>.corrupt-<timestamp>``."""
        stamp = now.strftime("%Y%m%dT%H%M%S")
        moved: list[Path] = []
        for path in (self.path, self.backup_path):
            if not path.exists():
                continue
            target = path.with_name(f"{path.name}.corrupt-{stamp}")
            try:
                path.replace(target)
            except OSError as exc:
                raise SaveWriteError(f"could not move {path} aside: {exc}") from exc
            logger.warning("Moved unusable save %s to %s", path, target)
            moved.append(target)
        return moved


def _read(path: Path) -> SaveGame:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SaveNotFoundError(f"no save file at {path}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise CorruptSaveError(f"could not read {path}: {exc}") from exc
    try:
        return decode(text)
    except CorruptSaveError as exc:
        raise CorruptSaveError(f"{path}: {exc}") from exc


def _fsync_directory(directory: Path) -> None:
    """Persist the rename itself (POSIX only; Windows can't open directories)."""
    if os.name != "posix":
        return
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
