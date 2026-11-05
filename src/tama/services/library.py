"""Several pets, as the UI sees them (ADR 0007): list, open, hatch, archive and switch.

``PetLibrary`` is the UI's single entry point to the roster, as ``GameSession`` is to one pet.
It holds the lock on whichever pet is open, so one pet is only ever open in one window.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import tzinfo
from pathlib import Path

from tama.domain.balance import Balance
from tama.domain.pet import DEFAULT_SPECIES
from tama.domain.visit import visit_refusals
from tama.errors import (
    InvalidArgumentError,
    NoEggError,
    RosterFullError,
    SaveError,
    VisitRefusedError,
)
from tama.infra.clock import Clock
from tama.persistence.lock import PetLock
from tama.persistence.roster import PetFile, PetRoster
from tama.services.describe import visit_refusal_text
from tama.services.roster import (
    PetSummary,
    can_add_pet,
    name_taken,
    others_needing_care,
    pet_summaries,
)
from tama.services.session import GameSession, LoadedSession, SessionSettings
from tama.services.visit import VisitCandidate, VisitSession, visit_candidates

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
    def balance(self) -> Balance:
        """The game's tunable numbers."""
        return self._settings.balance

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

    def hatch_heir(self, parent: PetFile, name: str) -> GameSession:
        """Hatch the egg ``parent`` left as a new pet called ``name``, opened and played next.

        The heir is saved before the parent, so a crash in between never yields two heirs
        (ADR 0010).

        Raises:
            NoEggError: If ``parent`` has no egg waiting (or an heir already hatched from it).
            RosterFullError: If there are nine pets already.
            InvalidArgumentError: If ``name`` is invalid or a living pet already has it.
            PetLockedError: If ``parent`` is open in another tama.
            SaveError: If ``parent`` can't be loaded or a pet can't be saved.
        """
        rows = self.summaries()
        row = next((r for r in rows if r.file == parent), None)
        if row is None or not row.egg_waiting:
            raise NoEggError(f"{row.name if row else parent.key} has no egg to hatch")
        if not can_add_pet(rows):
            raise RosterFullError("You have nine pets already; archive one to make room.")
        if name_taken(rows, name):
            raise InvalidArgumentError(f"You already have a {name.strip()}.")
        with self.borrow(parent) as parent_session:
            heir, rng = parent_session.hatch_heir(name)
            file = self.roster.create(heir.name)
            session = GameSession(
                pet=heir, rng=rng, repo=file.repo(), clock=self._clock, settings=self._settings
            )
            session.save()
            parent_session.save()
        self._take(file)
        self.roster.set_last(file)
        return session

    @contextmanager
    def borrow(self, file: PetFile) -> Iterator[GameSession]:
        """Lock and load ``file``'s pet for a quick change (``tama --pause``), then let go.

        Raises:
            PetLockedError: If it is open in another tama.
            SaveError: If it can't be loaded.
        """
        with PetLock(file.path):
            yield GameSession.load(
                repo=file.repo(), clock=self._clock, settings=self._settings
            ).session

    def visit_candidates(self) -> list[VisitCandidate]:
        """Every pet but the open one, with why it can't come round (SPEC §3.2)."""
        return visit_candidates(
            self.summaries(),
            host=self.open_file,
            balance=self.balance,
            locked_elsewhere=lambda file: PetLock(file.path).held_elsewhere(),
        )

    def borrow_for_visit(self, file: PetFile, host: GameSession) -> VisitSession:
        """Lock and load ``file``'s pet (catching up) to visit ``host``, and start the visit.

        The guest stays locked until ``VisitSession.close``, which every way out of a visit
        calls (ADR 0011). Nothing is saved if the visit can't start.

        Raises:
            InvalidArgumentError: If ``file`` is the open pet itself.
            PetLockedError: If it is open in another tama.
            SaveError: If it can't be loaded.
            VisitRefusedError: If either pet can't visit right now.
        """
        if file == self.open_file:
            raise InvalidArgumentError(f"{host.pet.name} can't visit itself")
        refusals = visit_refusals(host.pet, self.balance)
        if refusals:
            reason = visit_refusal_text(refusals[0])
            raise VisitRefusedError(f"{host.pet.name} can't have a visit: {reason}")
        lock = PetLock(file.path)
        lock.acquire()
        try:
            guest = GameSession.load(
                repo=file.repo(), clock=self._clock, settings=self._settings
            ).session
            visit = VisitSession(host, guest, release=lock.release)
            visit.start()
        except (SaveError, VisitRefusedError):
            lock.release()
            raise
        return visit

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
