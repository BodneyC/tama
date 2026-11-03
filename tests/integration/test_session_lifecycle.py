"""M3 acceptance: create a pet, close the game, come back later, and find it has lived on."""

from datetime import timedelta
from pathlib import Path
from random import Random

from tama.domain.context import Context
from tama.domain.events import Action
from tama.domain.pet import new_egg
from tama.domain.simulation import advance
from tama.domain.stage import LifeStage
from tama.infra.clock import FakeClock
from tama.persistence.codec import decode
from tama.persistence.repository import JsonSaveRepository
from tama.services.session import GameSession, SessionSettings
from tests.factories import FIXED_NOW

SEED = 3  # a seed where the pet stays healthy (no sickness roll) for the five hours
SETTINGS = SessionSettings()


def test_pet_lives_on_while_the_game_is_closed(tmp_path: Path) -> None:
    clock = FakeClock(FIXED_NOW)
    repo = JsonSaveRepository(tmp_path / "save.json")

    GameSession.create("Mochi", repo=repo, clock=clock, settings=SETTINGS, seed=SEED).close()
    clock.advance(timedelta(hours=5))
    loaded = GameSession.load(repo=repo, clock=clock, settings=SETTINGS)

    # Exactly what the pure simulation predicts for five hours from hatching.
    rng = Random(SEED)
    expected = advance(new_egg("Mochi", FIXED_NOW, rng), timedelta(hours=5), Context(rng=rng))
    assert loaded.session.pet == expected.pet
    assert loaded.away.events == expected.events

    # And it reads sensibly to the player.
    assert loaded.away.away_for == timedelta(hours=5)
    assert not loaded.away.pet_sitter
    assert loaded.away.summary == [
        "Hatched",
        "Grew into a child",
        "Misbehaved",
        "Got away with misbehaving",
        "Pooped ×2",
        "Got dirty",
        "Was left filthy",
    ]
    assert loaded.session.pet.stage is LifeStage.CHILD
    assert loaded.session.pet.is_alive

    # Caring for it and quitting leaves a valid save that matches the game.
    assert loaded.session.act(Action.MEAL).refusal is None
    loaded.session.close()
    on_disk = decode(repo.path.read_text(encoding="utf-8"))
    assert on_disk.pet == loaded.session.pet
    assert repo.load().game == on_disk
