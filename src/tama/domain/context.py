"""Everything the domain needs from the outside world, passed in explicitly."""

from dataclasses import dataclass, field
from datetime import UTC, tzinfo
from random import Random

from tama.domain.balance import DEFAULT_BALANCE, Balance


@dataclass(frozen=True, slots=True)
class Context:
    """Inputs for simulation and actions.

    Attributes:
        rng: The only source of randomness. Persist its state to make reloads deterministic.
        balance: Tunable game constants.
        tz: The player's local time zone, used to decide when it is night.
    """

    rng: Random
    balance: Balance = field(default=DEFAULT_BALANCE)
    tz: tzinfo = UTC
