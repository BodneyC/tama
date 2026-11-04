"""Every pet at a glance, as of now (SPEC §6.1, ADR 0007).

Summaries load each pet and catch it up to the current time *in memory only*: nothing here
saves, so looking at pets (the pet select screen, ``tama --status``, the header's count of
other pets needing care) can never change or corrupt them.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from tama.domain.attention import AttentionReason, attention_reasons
from tama.domain.journal import Journal
from tama.domain.pet import Pet
from tama.errors import SaveError, UnknownPetError
from tama.infra.clock import Clock
from tama.persistence.roster import PetFile, PetRoster
from tama.services.session import GameSession, SessionSettings

MAX_PETS = 9
"""So the number keys 1-9 can pick any of them."""


@dataclass(frozen=True, slots=True)
class PetSummary:
    """One pet as of now, or why it couldn't be read."""

    file: PetFile
    pet: Pet | None = None
    error: SaveError | None = None
    needs: frozenset[AttentionReason] = field(default_factory=frozenset)
    last: bool = False
    """Whether this is the pet played last."""
    journal: Journal = field(default_factory=Journal)
    """Its journal as of now (including what catching up wrote, which isn't saved)."""

    @property
    def name(self) -> str:
        """The pet's name, or its file's name if it can't be read."""
        return self.pet.name if self.pet is not None else self.file.path.stem

    @property
    def alive(self) -> bool:
        """Whether this is a readable, living pet."""
        return self.pet is not None and self.pet.is_alive

    @property
    def needs_care(self) -> bool:
        """Whether it is calling for attention (never while dead, an egg or on holiday)."""
        return bool(self.needs)


def summarize(
    file: PetFile, *, clock: Clock, settings: SessionSettings, last: bool = False
) -> PetSummary:
    """``file``'s pet caught up to now in memory (capped like a normal load), never saved."""
    try:
        session = GameSession.load(repo=file.repo(), clock=clock, settings=settings).session
    except SaveError as exc:
        return PetSummary(file, error=exc, last=last)
    pet = session.pet
    needs = attention_reasons(pet, settings.balance)
    return PetSummary(file, pet, needs=needs, last=last, journal=session.journal)


def pet_summaries(
    roster: PetRoster, *, clock: Clock, settings: SessionSettings
) -> list[PetSummary]:
    """Every pet, the last one played first and then by name."""
    last = roster.last()
    rows = [
        summarize(file, clock=clock, settings=settings, last=file == last)
        for file in roster.files()
    ]
    return sorted(rows, key=lambda row: (not row.last, row.name.casefold(), row.file.key))


def others_needing_care(
    roster: PetRoster, *, open_pet: PetFile, clock: Clock, settings: SessionSettings
) -> int:
    """How many pets other than ``open_pet`` are calling for attention right now."""
    return sum(
        summarize(file, clock=clock, settings=settings).needs_care
        for file in roster.files()
        if file != open_pet
    )


def name_taken(rows: Sequence[PetSummary], name: str) -> bool:
    """Whether a living pet already has ``name`` (ignoring case and surrounding spaces)."""
    wanted = name.strip().casefold()
    return any(row.alive and row.name.casefold() == wanted for row in rows)


def can_add_pet(rows: Sequence[PetSummary]) -> bool:
    """Whether there is room for another pet."""
    return len(rows) < MAX_PETS


def find_pet(rows: Sequence[PetSummary], query: str) -> PetSummary:
    """The pet ``--pet query`` means: an exact name, else a unique prefix; living pets first.

    Raises:
        UnknownPetError: If nothing matches, or several pets do; the message lists the pets.
    """
    wanted = query.strip().casefold()
    living = [row for row in rows if row.alive]
    others = [row for row in rows if not row.alive]
    for group in (living, others):
        exact = [row for row in group if row.name.casefold() == wanted]
        if exact:
            return exact[0]
    for group in (living, others):
        matches = [row for row in group if row.name.casefold().startswith(wanted)]
        if len(matches) == 1:
            return matches[0]
        if matches:
            raise UnknownPetError(f"{query!r} matches several pets. {_listing(rows)}")
    raise UnknownPetError(f"There's no pet called {query!r}. {_listing(rows)}")


def _listing(rows: Sequence[PetSummary]) -> str:
    names = sorted((row.name for row in rows), key=str.casefold)
    return f"Your pets: {', '.join(names)}." if names else "You have no pets yet."
