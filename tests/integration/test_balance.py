"""Balance regression: ordinary players who sleep at night still see their pet grow old.

Plays whole lives with the simulated players from ``tools/balance.py`` (run that for the
full picture across many seeds).
"""

import pytest
from tools.balance import PLAYERS, Player, live

from tama.domain.balance import DEFAULT_BALANCE
from tama.domain.stage import Variant

CASUAL, BUSY = PLAYERS[1], PLAYERS[2]


@pytest.mark.slow
@pytest.mark.parametrize(
    ("player", "seed", "variant"),
    # Casual players raise a well-behaved adult in about 2 lives out of 3 (tools.balance); a
    # good and a scruffy casual life are pinned here, busy players' pets are always scruffy.
    [(CASUAL, 1, Variant.GOOD), (CASUAL, 7, Variant.SCRUFFY), (BUSY, 7, Variant.SCRUFFY)],
    ids=["casual-good", "casual-scruffy", "busy"],
)
def test_players_who_check_in_while_awake_see_old_age(
    player: Player, seed: int, variant: Variant
) -> None:
    life = live(player, seed=seed, balance=DEFAULT_BALANCE)

    assert life.died_of == "old_age"
    assert life.variant is variant


@pytest.mark.slow
def test_a_casual_player_catches_enough_tantrums_for_a_good_adult() -> None:
    # Seed 7 is scruffy from care mistakes, not from discipline (ROADMAP: discipline pass).
    life = live(CASUAL, seed=7, balance=DEFAULT_BALANCE)

    assert life.discipline_at_adult is not None
    assert life.discipline_at_adult >= DEFAULT_BALANCE.good_adult_min_discipline
    assert life.mistakes_at_adult is not None
    assert life.mistakes_at_adult > DEFAULT_BALANCE.good_adult_max_care_mistakes
