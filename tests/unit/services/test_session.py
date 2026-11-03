import logging
from dataclasses import replace
from datetime import UTC, time, timedelta, timezone
from random import Random
from typing import Any

import pytest

from tama.domain.balance import DEFAULT_BALANCE
from tama.domain.context import Context
from tama.domain.events import Action, Ate, Evolved, Played, RefusalReason
from tama.domain.minigame import Direction, LeftRightGame
from tama.domain.pet import new_egg
from tama.domain.simulation import advance
from tama.domain.stage import LifeStage
from tama.domain.stats import Stats
from tama.errors import SaveNotFoundError, SaveWriteError
from tama.infra.clock import FakeClock
from tama.infra.config import Config
from tama.persistence.models import SaveGame
from tama.services.autosave import AutosavePolicy
from tama.services.session import GameSession, SessionSettings
from tests.factories import FIXED_NOW, make_pet
from tests.fakes import InMemorySaveRepository

SETTINGS = SessionSettings()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(FIXED_NOW)


def saved(seed: int = 0, **pet_overrides: Any) -> InMemorySaveRepository:
    pet = make_pet(**pet_overrides)
    return InMemorySaveRepository(SaveGame(pet, Random(seed).getstate()))


# --- Creating ---------------------------------------------------------------------------------


def test_create_hatches_a_new_egg_and_saves_it(clock: FakeClock) -> None:
    repo = InMemorySaveRepository()

    session = GameSession.create("Mochi", repo=repo, clock=clock, settings=SETTINGS, seed=7)

    assert session.pet == new_egg("Mochi", FIXED_NOW, Random(7))
    assert repo.save_count == 1
    assert repo.game is not None
    assert repo.game.pet == session.pet


def test_create_with_same_seed_is_reproducible(clock: FakeClock) -> None:
    a = GameSession.create(
        "A", repo=InMemorySaveRepository(), clock=clock, settings=SETTINGS, seed=3
    )
    b = GameSession.create(
        "A", repo=InMemorySaveRepository(), clock=clock, settings=SETTINGS, seed=3
    )

    assert a.pet == b.pet


# --- Loading & offline catch-up ---------------------------------------------------------------


def test_load_without_a_save(clock: FakeClock) -> None:
    with pytest.raises(SaveNotFoundError):
        GameSession.load(repo=InMemorySaveRepository(), clock=clock, settings=SETTINGS)


def test_load_simulates_time_away_exactly_like_the_domain(clock: FakeClock) -> None:
    repo = saved(seed=5)
    assert repo.game is not None
    original = repo.game.pet
    clock.advance(timedelta(hours=2, seconds=30))

    loaded = GameSession.load(repo=repo, clock=clock, settings=SETTINGS)

    expected = advance(original, timedelta(hours=2, seconds=30), Context(rng=Random(5)))
    assert loaded.session.pet == expected.pet
    assert loaded.away.events == expected.events
    assert loaded.away.away_for == loaded.away.simulated == timedelta(hours=2, seconds=30)
    assert not loaded.away.pet_sitter
    assert not loaded.away.clock_went_backwards
    assert not loaded.recovered_from_backup


def test_offline_time_beyond_the_cap_is_skipped(clock: FakeClock) -> None:
    repo = saved()
    settings = replace(SETTINGS, offline_cap=timedelta(hours=3))
    clock.advance(timedelta(hours=10))

    loaded = GameSession.load(repo=repo, clock=clock, settings=settings)

    assert loaded.away.away_for == timedelta(hours=10)
    assert loaded.away.simulated == timedelta(hours=3)
    assert loaded.away.pet_sitter
    assert loaded.session.pet.age == make_pet().age + timedelta(hours=3)
    assert loaded.session.pet.updated_at == clock.now()


def test_clock_going_backwards_does_not_rewind_the_pet(
    clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    repo = saved()
    assert repo.game is not None
    original = repo.game.pet
    clock.advance(timedelta(hours=-6))

    with caplog.at_level(logging.WARNING):
        loaded = GameSession.load(repo=repo, clock=clock, settings=SETTINGS)

    assert loaded.away.clock_went_backwards
    assert loaded.away.events == ()
    assert loaded.session.pet == replace(original, updated_at=clock.now())
    assert "clock went backwards" in caplog.text


def test_load_reports_backup_recovery(clock: FakeClock) -> None:
    repo = saved()
    repo.from_backup = True

    assert GameSession.load(repo=repo, clock=clock, settings=SETTINGS).recovered_from_backup


def test_away_summary_is_human_readable(clock: FakeClock) -> None:
    repo = saved(poop_progress=0, age=timedelta(hours=1))
    clock.advance(timedelta(hours=4, minutes=30))

    away = GameSession.load(repo=repo, clock=clock, settings=SETTINGS).away

    assert "Pooped ×2" in away.summary
    assert "Got hungry" in away.summary


# --- Live play --------------------------------------------------------------------------------


def test_tick_advances_to_the_clock(clock: FakeClock) -> None:
    session = GameSession.load(repo=saved(), clock=clock, settings=SETTINGS).session
    before = session.pet

    clock.advance(timedelta(minutes=9))
    tick = session.tick()

    assert session.pet.age == before.age + timedelta(minutes=9)
    assert session.pet.stats.hunger == before.stats.hunger - 3
    assert tick.away_for == timedelta(minutes=9)


def test_tick_with_no_time_passed_is_a_no_op(clock: FakeClock) -> None:
    session = GameSession.load(repo=saved(), clock=clock, settings=SETTINGS).session
    before = session.pet

    assert session.tick().events == ()
    assert session.pet == before


def test_first_tick_after_load_saves(clock: FakeClock) -> None:
    repo = saved()
    session = GameSession.load(repo=repo, clock=clock, settings=SETTINGS).session

    session.tick()

    assert repo.save_count == 1


def test_ticks_autosave_on_the_interval(clock: FakeClock) -> None:
    repo = saved()
    session = GameSession.load(repo=repo, clock=clock, settings=SETTINGS).session
    session.tick()

    clock.advance(timedelta(seconds=30))
    session.tick()
    saves_before_interval = repo.save_count
    clock.advance(timedelta(seconds=30))
    session.tick()

    assert saves_before_interval == 1
    assert repo.save_count == 2


def test_evolving_saves_immediately(clock: FakeClock) -> None:
    repo = saved(stage=LifeStage.BABY, age=timedelta(minutes=59))
    settings = replace(SETTINGS, autosave=AutosavePolicy(interval=timedelta(hours=1)))
    session = GameSession.load(repo=repo, clock=clock, settings=settings).session
    session.tick()

    clock.advance(timedelta(minutes=1))
    tick = session.tick()

    assert any(isinstance(e, Evolved) for e in tick.events)
    assert repo.save_count == 2


def test_failed_autosave_is_reported_not_raised(clock: FakeClock) -> None:
    repo = saved()
    session = GameSession.load(repo=repo, clock=clock, settings=SETTINGS).session
    repo.fail_saves = True

    session.tick()

    assert isinstance(session.save_error, SaveWriteError)

    repo.fail_saves = False
    clock.advance(timedelta(minutes=1))
    session.tick()

    assert session.save_error is None


def test_clock_going_backwards_during_play(clock: FakeClock) -> None:
    session = GameSession.load(repo=saved(), clock=clock, settings=SETTINGS).session
    before = session.pet
    clock.advance(timedelta(minutes=-10))

    tick = session.tick()

    assert tick.clock_went_backwards
    assert session.pet == replace(before, updated_at=clock.now())


# --- Actions ----------------------------------------------------------------------------------


def test_act_applies_the_action_and_saves(clock: FakeClock) -> None:
    repo = saved(stats=Stats(hunger=50))
    session = GameSession.load(repo=repo, clock=clock, settings=SETTINGS).session

    outcome = session.act(Action.MEAL)

    assert outcome.events == (Ate(session.pet.age, Action.MEAL),)
    assert session.pet.stats.hunger == 80
    assert repo.save_count == 1
    assert repo.game is not None
    assert repo.game.pet == session.pet


def test_refused_action_does_not_save(clock: FakeClock) -> None:
    repo = saved()
    session = GameSession.load(repo=repo, clock=clock, settings=SETTINGS).session

    outcome = session.act(Action.MEDICINE)

    assert outcome.refusal is RefusalReason.NOT_SICK
    assert repo.save_count == 0


def test_finish_game_applies_result_and_saves(clock: FakeClock) -> None:
    repo = saved(stats=Stats(happiness=50))
    session = GameSession.load(repo=repo, clock=clock, settings=SETTINGS).session

    outcome = session.finish_game(won=True)

    assert isinstance(outcome.events[0], Played)
    assert session.pet.stats.happiness == 70
    assert repo.save_count == 1


def test_actions_and_saves_share_the_rng(clock: FakeClock) -> None:
    repo = saved(seed=1, recent_snacks=(timedelta(minutes=59),) * 3)
    session = GameSession.load(repo=repo, clock=clock, settings=SETTINGS).session

    session.act(Action.SNACK)  # over the snack limit, so it rolls for sickness

    assert repo.game is not None
    assert repo.game.rng_state != Random(1).getstate()


def test_close_saves_and_raises_on_failure(clock: FakeClock) -> None:
    repo = saved()
    session = GameSession.load(repo=repo, clock=clock, settings=SETTINGS).session

    session.close()
    assert repo.save_count == 1

    repo.fail_saves = True
    with pytest.raises(SaveWriteError):
        session.close()


# --- Settings ---------------------------------------------------------------------------------


def test_settings_from_config() -> None:
    config = Config(night_start=time(21), night_end=time(6), offline_cap=timedelta(hours=8))
    tz = timezone(timedelta(hours=-5))

    settings = SessionSettings.from_config(config, tz)

    assert settings.balance == replace(DEFAULT_BALANCE, night_start=time(21), night_end=time(6))
    assert settings.offline_cap == timedelta(hours=8)
    assert settings.tz is tz


def test_default_settings() -> None:
    assert SETTINGS.balance == DEFAULT_BALANCE
    assert SETTINGS.tz is UTC
    assert SETTINGS.offline_cap == timedelta(hours=72)


# --- Mini-game --------------------------------------------------------------------------------


def test_guess_uses_and_persists_the_session_rng(clock: FakeClock) -> None:
    repo = saved(seed=9)
    session = GameSession.load(repo=repo, clock=clock, settings=SETTINGS).session

    game = session.guess(LeftRightGame(), Direction.LEFT)
    session.close()

    expected = LeftRightGame().guess(Direction.LEFT, Random(9))
    assert game == expected
    assert repo.game is not None
    assert repo.game.rng_state != Random(9).getstate()


def test_create_hatches_the_chosen_species(clock: FakeClock) -> None:
    repo = InMemorySaveRepository()

    session = GameSession.create("Hoot", repo=repo, clock=clock, settings=SETTINGS, species="owl")

    assert session.pet.species == "owl"
    assert repo.game is not None
    assert repo.game.pet.species == "owl"
