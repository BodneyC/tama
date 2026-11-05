"""The pet as an opponent: young pets are easy, grown-ups put up a fight (ROADMAP M6.5).

Plays the scripted *casual* player from ``tools/games.py`` (takes wins, blocks, otherwise
random) against the shipped Balance.
"""

import pytest
from tools.games import BOARDS, STAGES, casual_player, pet_report, pet_results, results

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


@pytest.mark.slow
@pytest.mark.parametrize("board", list(BOARDS))
def test_an_adult_usually_beats_a_baby_from_either_side(board: str) -> None:
    new_game = BOARDS[board]

    adult_first = pet_results(new_game, LifeStage.ADULT, LifeStage.BABY, DEFAULT_BALANCE, GAMES)
    baby_first = pet_results(new_game, LifeStage.BABY, LifeStage.ADULT, DEFAULT_BALANCE, GAMES)

    # Results are the first pet's: the adult wins as WIN when first, as LOSS when second.
    assert adult_first[GameResult.WIN] > 2 * adult_first[GameResult.LOSS]
    assert baby_first[GameResult.LOSS] > 2 * baby_first[GameResult.WIN]


def test_the_pet_vs_pet_report_covers_every_pair_of_stages() -> None:
    text = pet_report(DEFAULT_BALANCE, 2)

    assert text.count("pet vs pet") == len(BOARDS)
    rows = [line.split()[0] for line in text.splitlines() if "/" in line and "%" not in line]
    assert rows == [stage.value for stage in STAGES] * len(BOARDS)
    assert all(
        line.count("/") == 2 * len(STAGES)
        for line in text.splitlines()
        if "/" in line and "%" not in line
    )
