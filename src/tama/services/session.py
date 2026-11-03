"""The game session: the single owner of the current pet, its RNG and its save file.

The UI talks only to ``GameSession``. It never calls the domain or the repository directly.
"""

import logging
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta, tzinfo
from random import Random
from typing import Self

from tama.domain.actions import apply, apply_game_outcome
from tama.domain.balance import DEFAULT_BALANCE, Balance
from tama.domain.context import Context
from tama.domain.events import Action, Event, Outcome
from tama.domain.minigame import Direction, LeftRightGame
from tama.domain.pet import ZERO, Pet, new_egg
from tama.domain.simulation import advance, skip_to
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
    """

    away_for: timedelta
    simulated: timedelta
    events: tuple[Event, ...]

    @property
    def pet_sitter(self) -> bool:
        """Whether some of the time away exceeded the cap and was skipped."""
        return self.away_for > self.simulated

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

    def __init__(
        self,
        *,
        pet: Pet,
        rng: Random,
        repo: SaveRepository,
        clock: Clock,
        settings: SessionSettings,
    ) -> None:
        """Wrap an existing pet. Prefer ``create`` or ``load``."""
        self._pet = pet
        self._ctx = Context(rng=rng, balance=settings.balance, tz=settings.tz)
        self._repo = repo
        self._clock = clock
        self._settings = settings
        self._last_saved_at: datetime | None = None
        self.save_error: SaveWriteError | None = None

    @classmethod
    def create(
        cls,
        name: str,
        *,
        repo: SaveRepository,
        clock: Clock,
        settings: SessionSettings,
        seed: int | None = None,
    ) -> Self:
        """Start a new game with a fresh egg and save it immediately.

        Raises:
            InvalidArgumentError: If ``name`` is not a valid pet name.
            SaveWriteError: If the new game could not be saved.
        """
        rng = Random(seed)
        pet = new_egg(name, clock.now(), rng, settings.balance)
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
        )
        return LoadedSession(session, session._catch_up(), loaded.from_backup)

    @property
    def pet(self) -> Pet:
        """The current pet."""
        return self._pet

    @property
    def balance(self) -> Balance:
        """The game's tunable constants."""
        return self._settings.balance

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

    def finish_game(self, *, won: bool) -> Outcome:
        """Apply a finished mini-game's result, saving if it was accepted."""
        return self._commit(apply_game_outcome(self._pet, won=won, ctx=self._ctx))

    def guess(self, game: LeftRightGame, direction: Direction) -> LeftRightGame:
        """Play a mini-game round using the session's RNG (so it is saved and reproducible)."""
        return game.guess(direction, self._ctx.rng)

    def save(self) -> None:
        """Save now.

        Raises:
            SaveWriteError: If saving failed.
        """
        self._repo.save(SaveGame(self._pet, self._ctx.rng.getstate()))
        self._last_saved_at = self._clock.now()
        self.save_error = None

    def close(self) -> None:
        """Save before shutting down.

        Raises:
            SaveWriteError: If saving failed; the player should be told.
        """
        self.save()

    def _commit(self, outcome: Outcome) -> Outcome:
        self._pet = outcome.pet
        if outcome.refusal is None:
            self._try_save()
        return outcome

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
        simulated = min(away_for, self._settings.offline_cap)
        outcome = advance(self._pet, simulated, self._ctx)
        if simulated < away_for:
            logger.info("Pet sitter covered %s beyond the offline cap", away_for - simulated)
        self._pet = skip_to(outcome.pet, now)
        return CatchUp(away_for, simulated, outcome.events)
