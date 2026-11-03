"""The pet as an opponent: young pets are easy, grown-ups put up a fight (ROADMAP M6.5).

Plays the scripted *casual* player from ``tools/games.py`` (takes wins, blocks, otherwise
random) against the shipped Balance.
"""

import pytest
from tools.games import BOARDS, casual_player, results

from tama.domain.balance import DEFAULT_BALANCE
from tama.domain.minigames import GameResult
from tama.domain.stage import LifeStage

GAMES = 200


@pytest.mark.slow
@pytest.mark.parametrize("board", list(BOARDS))
def test_young_pets_are_easy_and_adults_challenging(board: str) -> None:
    new_game = BOARDS[board]

    baby = results(new_game, casual_player, LifeStage.BABY, DEFAULT_BALANCE, GAMES)
    adult = results(new_game, casual_player, LifeStage.ADULT, DEFAULT_BALANCE, GAMES)

    assert baby[GameResult.WIN] / GAMES >= 0.6
    assert adult[GameResult.WIN] / GAMES <= 0.45
    assert adult[GameResult.WIN] < baby[GameResult.WIN]
