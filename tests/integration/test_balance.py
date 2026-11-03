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
    ("player", "variant"), [(CASUAL, Variant.GOOD), (BUSY, Variant.SCRUFFY)], ids=["casual", "busy"]
)
def test_players_who_check_in_while_awake_see_old_age(player: Player, variant: Variant) -> None:
    life = live(player, seed=7, balance=DEFAULT_BALANCE)

    assert life.died_of == "old_age"
    assert life.variant is variant
