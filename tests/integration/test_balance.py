"""Balance regression: ordinary players who sleep at night still see their pet grow old.

Plays whole lives with the simulated players from ``tools/balance.py`` (run that for the
full picture across many seeds).
"""

from datetime import timedelta

import pytest
from tools.balance import PLAYERS, Player, live
from tools.generations import Line, keep_a_line

from tama.domain.balance import DEFAULT_BALANCE
from tama.domain.stage import Variant

CASUAL, BUSY, SNACKER = PLAYERS[1], PLAYERS[2], PLAYERS[4]


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


@pytest.mark.slow
@pytest.mark.parametrize("player", [CASUAL, BUSY], ids=["casual", "busy"])
def test_ordinary_feeding_keeps_a_pet_in_its_weight_band(player: Player) -> None:
    life = live(player, seed=1, balance=DEFAULT_BALANCE)

    assert life.out_of_band == timedelta(0)
    assert life.weight_mistakes == 0


@pytest.mark.slow
def test_cheering_a_pet_up_with_snacks_raises_a_chubby_adult() -> None:
    life = live(SNACKER, seed=1, balance=DEFAULT_BALANCE)

    assert life.variant is Variant.CHUBBY
    assert life.weight_mistakes == 1  # one long episode, counted once


@pytest.mark.slow
def test_a_casual_player_keeps_a_family_line_going_for_a_month() -> None:
    line = keep_a_line(CASUAL, seed=1, balance=DEFAULT_BALANCE, days=30)

    assert line == Line(generations=2, ended="going")
