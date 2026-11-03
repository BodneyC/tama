"""In-memory test doubles."""

from datetime import datetime
from pathlib import Path

from tama.errors import SaveNotFoundError, SaveWriteError
from tama.persistence.models import SaveGame
from tama.persistence.repository import LoadResult


class InMemorySaveRepository:
    """A ``SaveRepository`` that keeps the game in memory and can be told to fail."""

    def __init__(self, game: SaveGame | None = None, *, from_backup: bool = False) -> None:
        self.game = game
        self.from_backup = from_backup
        self.save_count = 0
        self.fail_saves = False

    def exists(self) -> bool:
        return self.game is not None

    def load(self) -> LoadResult:
        if self.game is None:
            raise SaveNotFoundError("nothing saved")
        return LoadResult(self.game, from_backup=self.from_backup)

    def save(self, game: SaveGame) -> None:
        if self.fail_saves:
            raise SaveWriteError("disk full")
        self.game = game
        self.save_count += 1

    def quarantine(self, now: datetime) -> list[Path]:
        self.game = None
        return []
