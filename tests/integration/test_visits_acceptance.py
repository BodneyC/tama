"""M6.12 acceptance: two awake pets meet, watch a game of Four in a Row, and part (SPEC §3.2).

With two awake pets, ``v`` invites one, both gain happiness once, a watched game of Four in a
Row ends with the right effect on each pet, and ending the visit leaves the guest saved and
unlocked; a second tama can't open the guest during the visit.
"""

import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from tama.domain.journal import Topic
from tama.domain.minigames import GameResult
from tama.domain.stage import LifeStage
from tama.domain.stats import Stats
from tama.persistence.roster import PetFile
from tama.ui.screens.games.pet_vs_pet import PetVsPetScreen
from tama.ui.screens.main import MainScreen
from tama.ui.screens.visit import VisitScreen
from tests.factories import make_pet
from tests.ui.helpers import library_with, make_library_app

STATS = Stats(happiness=50, energy=80)
EFFECT = {GameResult.WIN: (20, -1), GameResult.DRAW: (10, 0), GameResult.LOSS: (5, 0)}
"""Happiness and weight change for each result (SPEC §3 ``p`` row); energy is always -10."""

_SECOND_TAMA = """
import sys
from pathlib import Path
from tama.errors import PetLockedError
from tama.persistence.lock import PetLock
try:
    PetLock(Path(sys.argv[1])).acquire()
except PetLockedError:
    sys.exit(3)
"""


def second_tama_can_open(file: PetFile) -> bool:
    """Whether another process could take ``file``'s lock (it gives it up again if so)."""
    done = subprocess.run(  # noqa: S603 - our own interpreter and script
        [sys.executable, "-c", _SECOND_TAMA, str(file.path)], check=False
    )
    return done.returncode == 0


async def test_two_pets_visit_play_four_in_a_row_and_part(tmp_path: Path) -> None:
    adult = make_pet(stage=LifeStage.ADULT, stats=STATS)
    mochi, pip = replace(adult, name="Mochi"), replace(adult, name="Pip", species="owl")
    library, files = library_with(tmp_path, mochi, pip)
    app = make_library_app(library, open_pet=files[0])
    async with app.run_test() as pilot:
        await pilot.press("v", "1")  # Pip, the only other pet
        await pilot.pause()
        assert isinstance(app.screen, VisitScreen)
        visit = app.visit
        assert visit is not None
        assert visit.host.pet.stats.happiness == visit.guest.pet.stats.happiness == 60
        assert not second_tama_can_open(files[1])

        app.tick()
        visit.tick()  # time passing doesn't cheer them up again
        assert visit.host.journal.tallies.visits == 1

        await pilot.press("g", "1")  # Four in a Row, played out at once without animation
        await pilot.pause()
        game = app.screen
        assert isinstance(game, PetVsPetScreen)
        result = game.game.result
        assert result is not None
        await pilot.press("enter")
        await pilot.pause()

        for session, mine, before in (
            (visit.host, result, mochi),
            (visit.guest, result.mirrored, pip),
        ):
            happiness, weight = EFFECT[mine]
            assert session.pet.stats.happiness == 60 + happiness
            assert session.pet.stats.energy == before.stats.energy - 10
            assert session.pet.weight == before.weight + weight
            assert session.journal.entries[-1].topic is Topic.PLAYED_WITH

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)
        assert app.visit is None

        guest = files[1].repo().load().game
        assert guest.pet == visit.guest.pet
        assert guest.journal.tallies.visits == 1
        assert second_tama_can_open(files[1])
