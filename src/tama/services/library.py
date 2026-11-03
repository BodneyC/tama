"""Several pets, as the UI sees them (ADR 0007): list, open, hatch, archive and switch.

``PetLibrary`` is the UI's single entry point to the roster, as ``GameSession`` is to one pet.
It holds the lock on whichever pet is open, so one pet is only ever open in one window.
"""

import logging
from datetime import tzinfo
from pathlib import Path

from tama.domain.pet import DEFAULT_SPECIES
from tama.infra.clock import Clock
from tama.persistence.lock import PetLock
from tama.persistence.roster import PetFile, PetRoster
from tama.services.roster import (
    PetSummary,
    can_add_pet,
    name_taken,
    others_needing_care,
    pet_summaries,
)
from tama.services.session import GameSession, LoadedSession, SessionSettings

logger = logging.getLogger(__name__)


class PetLibrary:
    """Every pet in a roster, and the one that is open (locked) right now."""

    def __init__(self, roster: PetRoster, *, clock: Clock, settings: SessionSettings) -> None:
        """Manage ``roster``'s pets with the given clock and settings."""
        self.roster = roster
        self._clock = clock
        self._settings = settings
        self._lock: PetLock | None = None
        self.open_file: PetFile | None = None

    @property
    def tz(self) -> tzinfo:
        """The player's time zone, for showing dates."""
        return self._settings.tz

    def summaries(self) -> list[PetSummary]:
        """Every pet as of now (read-only), the last played first."""
        return pet_summaries(self.roster, clock=self._clock, settings=self._settings)

    def can_add(self) -> bool:
        """Whether there is room for another pet."""
        return can_add_pet(self.summaries())

    def name_taken(self, name: str) -> bool:
        """Whether a living pet already has ``name``."""
        return name_taken(self.summaries(), name)

    def open(self, file: PetFile) -> LoadedSession:
        """Lock ``file``'s pet, remember it as last played, and load it (catching up).

        Any pet open before is released first. If loading fails the lock is kept, so the
        player can deal with the unreadable file; ``close`` releases it.

        Raises:
            PetLockedError: If it is open in another tama.
            SaveError: If it can't be loaded.
        """
        self._take(file)
        self.roster.set_last(file)
        return GameSession.load(repo=file.repo(), clock=self._clock, settings=self._settings)

    def hatch(
        self, name: str, *, species: str = DEFAULT_SPECIES, seed: int | None = None
    ) -> GameSession:
        """A new egg in its own file, opened and remembered as last played.

        Raises:
            InvalidArgumentError: If ``name`` is not a valid pet name.
            SaveWriteError: If it could not be saved.
        """
        file = self.roster.create(name)
        self._take(file)
        session = GameSession.create(
            name,
            repo=file.repo(),
            clock=self._clock,
            settings=self._settings,
            seed=seed,
            species=species,
        )
        self.roster.set_last(file)
        return session

    def set_aside(self) -> list[Path]:
        """Move the open, unreadable pet's files aside (``.corrupt-<time>``) and close it.

        Raises:
            SaveWriteError: If they could not be moved.
        """
        if self.open_file is None:
            return []
        moved = GameSession.discard_save(repo=self.open_file.repo(), clock=self._clock)
        self.close()
        return moved

    def archive(self, file: PetFile) -> list[Path]:
        """Move a pet's files to the archive (SPEC §6.1).

        Raises:
            SaveWriteError: If they could not be moved.
        """
        return self.roster.archive(file)

    def others_needing_care(self) -> int:
        """How many pets other than the open one need attention right now (read-only)."""
        if self.open_file is None:
            return 0
        return others_needing_care(
            self.roster, open_pet=self.open_file, clock=self._clock, settings=self._settings
        )

    def close(self) -> None:
        """Release the open pet's lock."""
        if self._lock is not None:
            self._lock.release()
        self._lock = None
        self.open_file = None

    def _take(self, file: PetFile) -> None:
        lock = PetLock(file.path)
        lock.acquire()  # before letting go of the old one, so a failure changes nothing
        if self.open_file != file:
            self.close()
        self._lock, self.open_file = lock, file
