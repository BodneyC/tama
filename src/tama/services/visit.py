"""A visit: the open pet and a guest side by side, playing board games (SPEC §3.2, ADR 0011).

``VisitSession`` holds two ordinary ``GameSession``s and ticks both. Each pet moves in a game
with its own RNG and stage; the host plays the first side. Whatever way a visit ends,
``close`` saves the guest and lets go of its lock, exactly once.
"""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from tama.domain.balance import Balance
from tama.domain.events import Outcome
from tama.domain.minigames import GameKind, GameResult, Side
from tama.domain.minigames.opponent import BoardGame
from tama.domain.visit import VisitRefusal, can_visit, visit_refusals
from tama.errors import SaveWriteError, VisitRefusedError
from tama.persistence.roster import PetFile
from tama.services.describe import visit_ended_text, visit_refusal_text
from tama.services.roster import PetSummary
from tama.services.session import CatchUp, GameSession

logger = logging.getLogger(__name__)

UNREADABLE = "can't be read"
OPEN_ELSEWHERE = "open in another tama"


@dataclass(frozen=True, slots=True)
class VisitCandidate:
    """A pet in the visit picker, and why it can't come (``None`` if it can)."""

    summary: PetSummary
    reason: str | None = None

    @property
    def can_come(self) -> bool:
        """Whether it can be invited."""
        return self.reason is None


def visit_candidates(
    rows: Sequence[PetSummary],
    *,
    host: PetFile | None,
    balance: Balance,
    locked_elsewhere: Callable[[PetFile], bool],
) -> list[VisitCandidate]:
    """Every pet but the host, each with the reason it can't visit (SPEC §3.2)."""
    candidates: list[VisitCandidate] = []
    for row in rows:
        if row.file == host:
            continue
        reason: str | None = None
        if row.pet is None:
            reason = UNREADABLE
        elif refusals := visit_refusals(row.pet, balance):
            reason = visit_refusal_text(refusals[0])
        elif locked_elsewhere(row.file):
            reason = OPEN_ELSEWHERE
        candidates.append(VisitCandidate(row, reason))
    return candidates


@dataclass(frozen=True, slots=True)
class VisitEnded:
    """Why a visit ended by itself: ``leaver`` (host or guest) couldn't carry on."""

    leaver: str
    reason: VisitRefusal
    text: str


@dataclass(frozen=True, slots=True)
class VisitTick:
    """What a tick of the visit brought: each pet's catch-up and whether the visit is over."""

    host: CatchUp
    guest: CatchUp
    ended: VisitEnded | None


class VisitSession:
    """The host's and the guest's sessions for the length of a visit."""

    def __init__(
        self, host: GameSession, guest: GameSession, *, release: Callable[[], None]
    ) -> None:
        """Pair two sessions; ``release`` lets go of the guest's lock (called by ``close``)."""
        self.host = host
        self.guest = guest
        self._release = release
        self.closed = False
        self.greetings: tuple[Outcome, Outcome] | None = None

    def start(self) -> tuple[Outcome, Outcome]:
        """The two pets greet each other: each gets a visit (happier unless too soon).

        Raises:
            VisitRefusedError: If either pet can't visit right now.
        """
        for session in (self.host, self.guest):
            refusals = visit_refusals(session.pet, session.balance)
            if refusals:
                text = visit_refusal_text(refusals[0])
                raise VisitRefusedError(f"{session.pet.name} can't visit: {text}")
        self.greetings = (
            self.host.start_visit(self.guest.pet.name),
            self.guest.start_visit(self.host.pet.name),
        )
        return self.greetings

    def tick(self) -> VisitTick:
        """Bring both pets up to date (each autosaving as usual) and see if the visit is over."""
        host, guest = self.host.tick(), self.guest.tick()
        return VisitTick(host, guest, self.ended())

    def ended(self) -> VisitEnded | None:
        """Why the visit can't go on (the host is checked first), or ``None`` if it can."""
        for session in (self.host, self.guest):
            refusals = visit_refusals(session.pet, session.balance)
            if refusals:
                name = session.pet.name
                text = visit_ended_text(
                    host=self.host.pet.name,
                    guest=self.guest.pet.name,
                    leaver=name,
                    reason=refusals[0],
                )
                return VisitEnded(name, refusals[0], text)
        return None

    def can_play(self) -> bool:
        """Whether both pets are up for a game (the same rule as visiting)."""
        return all(can_visit(s.pet, s.balance) for s in (self.host, self.guest))

    def move[G: BoardGame](self, game: G) -> G:
        """The next move, by whichever pet's turn it is: the host plays the first side."""
        session = self.host if game.to_move is Side.PLAYER else self.guest
        return session.pet_move(game, side=game.to_move)

    def play_out[G: BoardGame](self, game: G) -> G:
        """Every remaining move, to the end of the game (``Space``, or reduced motion)."""
        while game.result is None:
            game = self.move(game)
        return game

    def finish_game(self, kind: GameKind, result: GameResult) -> tuple[Outcome, Outcome]:
        """Give each pet the finished game's effect from its own side (and save both)."""
        return (
            self.host.finish_game(result, kind, side=Side.PLAYER, friend=self.guest.pet.name),
            self.guest.finish_game(result, kind, side=Side.PET, friend=self.host.pet.name),
        )

    def close(self) -> None:
        """Save the guest and give it back (its lock released), once; later calls do nothing.

        The lock is released even if saving fails, so the guest can be opened again; the
        failure is logged and re-raised for the UI to report.

        Raises:
            SaveWriteError: If the guest could not be saved.
        """
        if self.closed:
            return
        self.closed = True
        try:
            self.guest.close()
        except SaveWriteError:
            logger.exception("Could not save the guest %s", self.guest.pet.name)
            raise
        finally:
            self._release()
