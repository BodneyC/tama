"""The game session: the single owner of the current pet, its RNG and its save file.

The UI talks only to ``GameSession``. It never calls the domain or the repository directly.
"""

import logging
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta, tzinfo
from pathlib import Path
from random import Random
from typing import Self

from tama.domain.actions import apply, apply_game_outcome
from tama.domain.balance import DEFAULT_BALANCE, Balance
from tama.domain.context import Context
from tama.domain.daylight import DayPhase, phase
from tama.domain.events import Action, Event, Outcome
from tama.domain.holiday import pause, resume
from tama.domain.journal import Journal, record
from tama.domain.lineage import hatch_heir
from tama.domain.minigames import GameKind, GameResult, Side
from tama.domain.minigames.left_right import Direction, LeftRightGame
from tama.domain.minigames.opponent import BoardGame, pet_move
from tama.domain.pet import DEFAULT_SPECIES, ZERO, Pet, new_egg
from tama.domain.simulation import advance, skip_to
from tama.domain.visit import start_visit
from tama.errors import SaveWriteError
from tama.infra.clock import Clock
from tama.infra.config import Config
from tama.persistence.models import SaveGame, restore_rng
from tama.persistence.repository import SaveRepository
from tama.services.autosave import AutosavePolicy
from tama.services.describe import summarize

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SessionSettings:
    """How the session runs, derived from user config."""

    balance: Balance = DEFAULT_BALANCE
    tz: tzinfo = UTC
    offline_cap: timedelta = timedelta(hours=72)
    autosave: AutosavePolicy = field(default_factory=AutosavePolicy)

    @classmethod
    def from_config(cls, config: Config, tz: tzinfo) -> Self:
        """Build settings from user config and the player's time zone."""
        balance = replace(
            DEFAULT_BALANCE, night_start=config.night_start, night_end=config.night_end
        )
        return cls(balance=balance, tz=tz, offline_cap=config.offline_cap)


@dataclass(frozen=True, slots=True)
class CatchUp:
    """What happened when the session caught up with the wall clock.

    Attributes:
        away_for: Wall-clock time since the pet was last updated (negative if the clock
            went backwards).
        simulated: How much of that time was actually simulated (capped).
        events: What happened, in order.
        on_holiday: Whether the pet was paused, so nothing was simulated at all.
    """

    away_for: timedelta
    simulated: timedelta
    events: tuple[Event, ...]
    on_holiday: bool = False

    @property
    def pet_sitter(self) -> bool:
        """Whether some of the time away exceeded the cap and was skipped."""
        return not self.on_holiday and self.away_for > self.simulated

    @property
    def clock_went_backwards(self) -> bool:
        """Whether the wall clock was earlier than the pet's last update."""
        return self.away_for < ZERO

    @property
    def summary(self) -> list[str]:
        """Human-readable lines for the "While you were away" dialog."""
        return summarize(self.events)


@dataclass(frozen=True, slots=True)
class LoadedSession:
    """A session resumed from disk, with what happened while the player was away."""

    session: "GameSession"
    away: CatchUp
    recovered_from_backup: bool


class GameSession:
    """Owns the pet and keeps it in step with the clock and the save file.

    Save failures during ticks and actions don't raise: the game carries on and the error
    is exposed as ``save_error`` for the UI to show. ``save``/``close`` do raise.
    """

    def __init__(  # noqa: PLR0913 - explicit dependencies, all keyword-only
        self,
        *,
        pet: Pet,
        rng: Random,
        repo: SaveRepository,
        clock: Clock,
        settings: SessionSettings,
        journal: Journal | None = None,
    ) -> None:
        """Wrap an existing pet (and its journal). Prefer ``create`` or ``load``."""
        self._pet = pet
        self._journal = journal or Journal()
        self._ctx = Context(rng=rng, balance=settings.balance, tz=settings.tz)
        self._repo = repo
        self._clock = clock
        self._settings = settings
        self._last_saved_at: datetime | None = None
        self.save_error: SaveWriteError | None = None

    @classmethod
    def create(  # noqa: PLR0913 - explicit dependencies, all keyword-only
        cls,
        name: str,
        *,
        repo: SaveRepository,
        clock: Clock,
        settings: SessionSettings,
        seed: int | None = None,
        species: str = DEFAULT_SPECIES,
    ) -> Self:
        """Start a new game with a fresh ``species`` egg and save it immediately.

        Raises:
            InvalidArgumentError: If ``name`` is not a valid pet name.
            SaveWriteError: If the new game could not be saved.
        """
        rng = Random(seed)
        pet = new_egg(name, clock.now(), rng, settings.balance, species=species)
        session = cls(pet=pet, rng=rng, repo=repo, clock=clock, settings=settings)
        session.save()
        return session

    @classmethod
    def load(
        cls, *, repo: SaveRepository, clock: Clock, settings: SessionSettings
    ) -> LoadedSession:
        """Resume the saved game, simulating the time since it was last played.

        The session is not saved here; the first ``tick`` does that.

        Raises:
            SaveNotFoundError, CorruptSaveError, UnsupportedSaveVersionError: From the repository.
        """
        loaded = repo.load()
        session = cls(
            pet=loaded.game.pet,
            rng=restore_rng(loaded.game.rng_state),
            repo=repo,
            clock=clock,
            settings=settings,
            journal=loaded.game.journal,
        )
        return LoadedSession(session, session._catch_up(), loaded.from_backup)

    @staticmethod
    def discard_save(*, repo: SaveRepository, clock: Clock) -> list[Path]:
        """Move an unreadable save (and its backup) aside so a new pet can start.

        Returns:
            Where the files were moved (``<name>.corrupt-<timestamp>``).

        Raises:
            SaveWriteError: If they could not be moved.
        """
        moved = repo.quarantine(clock.now())
        logger.warning("Moved unreadable save files aside: %s", moved)
        return moved

    @property
    def pet(self) -> Pet:
        """The current pet."""
        return self._pet

    @property
    def journal(self) -> Journal:
        """The pet's journal, up to date with everything the session has done (SPEC §2.9)."""
        return self._journal

    @property
    def tz(self) -> tzinfo:
        """The player's time zone, for showing dates."""
        return self._settings.tz

    @property
    def balance(self) -> Balance:
        """The game's tunable constants."""
        return self._settings.balance

    def day_phase(self) -> DayPhase:
        """The player's time of day now, for the stage's background (SPEC §5.1).

        It follows the wall clock, not the pet, so it moves on for a pet on holiday too.
        """
        return phase(self._clock.now(), self._ctx)

    def tick(self) -> CatchUp:
        """Bring the pet up to the current time, autosaving if due."""
        catch_up = self._catch_up()
        due = self._settings.autosave.is_due(
            now=self._clock.now(), last_saved_at=self._last_saved_at, events=catch_up.events
        )
        if due:
            self._try_save()
        return catch_up

    def act(self, action: Action) -> Outcome:
        """Perform a player action, saving if it was accepted.

        The pet is not ticked first; the UI ticks every second, so it is at most a second old.
        """
        return self._commit(apply(self._pet, action, self._ctx))

    def finish_game(
        self,
        result: GameResult,
        game: GameKind,
        *,
        side: Side = Side.PLAYER,
        friend: str | None = None,
    ) -> Outcome:
        """Apply a finished mini-game's result, saving if it was accepted.

        In a game against another pet, ``friend``, this pet played ``side`` (SPEC §3.2).
        """
        outcome = apply_game_outcome(
            self._pet, result, game=game, ctx=self._ctx, side=side, friend=friend
        )
        return self._commit(outcome)

    def start_visit(self, friend: str) -> Outcome:
        """Meet ``friend`` (SPEC §3.2), saving at once.

        Raises:
            VisitRefusedError: If this pet can't visit right now.
        """
        return self._commit(start_visit(self._pet, friend, self._settings.balance))

    def hatch_heir(self, name: str) -> tuple[Pet, Random]:
        """Hatch the egg this (dead) pet left: the heir called ``name``, and its own RNG.

        The heir's RNG is seeded from this pet's, so a line started with ``--seed`` replays.
        ``HeirHatched`` goes in this pet's journal; nothing is saved: the caller saves the heir
        first and then this pet (ADR 0010).

        Raises:
            NoEggError: If this pet has no egg waiting.
            InvalidArgumentError: If ``name`` is not a valid name.
        """
        heir_rng = Random(self._ctx.rng.getrandbits(64))
        heir, outcome = hatch_heir(
            self._pet, name, self._clock.now(), heir_rng, self._settings.balance
        )
        self._take(outcome)
        return heir, heir_rng

    def hand_over(self, name: str) -> "GameSession":
        """Hatch this pet's egg in its place: the heir takes over the same save file.

        For a single save file (``--save-path``), where there is no pet list to add the heir to;
        the parent lives on in the heir's family line (and the file's backup).

        Raises:
            NoEggError: If this pet has no egg waiting.
            InvalidArgumentError: If ``name`` is not a valid name.
            SaveWriteError: If the heir could not be saved.
        """
        heir, rng = self.hatch_heir(name)
        session = GameSession(
            pet=heir, rng=rng, repo=self._repo, clock=self._clock, settings=self._settings
        )
        session.save()
        return session

    def pause(self) -> Outcome:
        """Put the pet on holiday (SPEC §2.6), saving at once; refused if it isn't settled."""
        return self._commit_change(pause(self._pet, self._ctx.balance))

    def resume(self) -> Outcome:
        """Bring the pet back from holiday as of now, saving at once (no-op if not paused)."""
        return self._commit_change(resume(self._pet, self._clock.now()))

    def guess(self, game: LeftRightGame, direction: Direction) -> LeftRightGame:
        """Play a mini-game round using the session's RNG (so it is saved and reproducible)."""
        return game.guess(direction, self._ctx.rng)

    def pet_move[G: BoardGame](self, game: G, *, side: Side = Side.PET) -> G:
        """Make the pet's move (as ``side``) in a board game, using the session's RNG."""
        move = pet_move(game, self._pet.stage, self._ctx.balance, self._ctx.rng, side=side)
        return game.play(move)

    def save(self) -> None:
        """Save now.

        Raises:
            SaveWriteError: If saving failed.
        """
        self._repo.save(SaveGame(self._pet, self._ctx.rng.getstate(), self._journal))
        self._last_saved_at = self._clock.now()
        self.save_error = None

    def close(self) -> None:
        """Save before shutting down.

        Raises:
            SaveWriteError: If saving failed; the player should be told.
        """
        self.save()

    def _commit_change(self, outcome: Outcome) -> Outcome:
        """Take ``outcome``'s pet, saving only if anything changed."""
        changed = outcome.pet != self._pet
        self._take(outcome)
        if changed:
            self._try_save()
        return outcome

    def _commit(self, outcome: Outcome) -> Outcome:
        self._take(outcome)
        if outcome.refusal is None:
            self._try_save()
        return outcome

    def _take(self, outcome: Outcome) -> None:
        """Adopt ``outcome``'s pet, writing its events in the journal first."""
        self._journal = record(self._journal, outcome.events, self._pet)
        self._pet = outcome.pet

    def _try_save(self) -> None:
        try:
            self.save()
        except SaveWriteError as exc:
            logger.exception("Autosave failed")
            self.save_error = exc

    def _catch_up(self) -> CatchUp:
        now = self._clock.now()
        away_for = now - self._pet.updated_at
        if away_for < ZERO:
            logger.warning("System clock went backwards by %s; not rewinding the pet", -away_for)
            self._pet = skip_to(self._pet, now)
            return CatchUp(away_for, ZERO, ())
        if self._pet.on_holiday:  # frozen: nothing to simulate and no pet sitter needed
            self._pet = skip_to(self._pet, now)
            return CatchUp(away_for, ZERO, (), on_holiday=True)
        simulated = min(away_for, self._settings.offline_cap)
        outcome = advance(self._pet, simulated, self._ctx)
        if simulated < away_for:
            logger.info("Pet sitter covered %s beyond the offline cap", away_for - simulated)
        self._take(outcome)  # before skipping ahead, so entries keep their own times
        self._pet = skip_to(self._pet, now)
        return CatchUp(away_for, simulated, outcome.events)
