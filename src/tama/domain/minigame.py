"""The "Left or Right" guessing mini-game (SPEC §3)."""

from dataclasses import dataclass
from enum import StrEnum
from random import Random
from typing import Self

from tama.errors import GameOverError, InvalidArgumentError


class Direction(StrEnum):
    """Where the pet might look."""

    LEFT = "left"
    RIGHT = "right"


@dataclass(frozen=True, slots=True)
class RoundResult:
    """One round: the player's guess and where the pet actually looked."""

    guess: Direction
    pet_looked: Direction

    @property
    def correct(self) -> bool:
        """Whether the guess was right."""
        return self.guess is self.pet_looked


@dataclass(frozen=True, slots=True)
class LeftRightGame:
    """An immutable game state. Each ``guess`` returns the next state."""

    rounds: int = 5
    wins_needed: int = 3
    results: tuple[RoundResult, ...] = ()

    def __post_init__(self) -> None:
        """Validate settings."""
        if self.rounds < 1 or not 1 <= self.wins_needed <= self.rounds:
            raise InvalidArgumentError(
                f"need rounds >= 1 and 1 <= wins_needed <= rounds, "
                f"got rounds={self.rounds}, wins_needed={self.wins_needed}"
            )

    @property
    def is_over(self) -> bool:
        """Whether every round has been played."""
        return len(self.results) >= self.rounds

    @property
    def round_number(self) -> int:
        """The 1-based round being played (or the last round, once over)."""
        return min(len(self.results) + 1, self.rounds)

    @property
    def wins(self) -> int:
        """Correct guesses so far."""
        return sum(result.correct for result in self.results)

    @property
    def won(self) -> bool:
        """Whether the game is over and the player guessed enough rounds."""
        return self.is_over and self.wins >= self.wins_needed

    @property
    def last_result(self) -> RoundResult | None:
        """The most recent round, if any."""
        return self.results[-1] if self.results else None

    def guess(self, direction: Direction, rng: Random) -> Self:
        """Play a round: the pet picks a direction at random and the guess is scored.

        Raises:
            GameOverError: If all rounds have already been played.
        """
        if self.is_over:
            raise GameOverError("the game is already over")
        looked = rng.choice(list(Direction))
        return type(self)(
            self.rounds, self.wins_needed, (*self.results, RoundResult(direction, looked))
        )
