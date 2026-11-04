"""M6.10 acceptance: a whole life's journal reads as its story, and the shell prints it."""

from collections import Counter
from datetime import timedelta

import pytest
from typer.testing import CliRunner

from tama import cli
from tama.cli import app
from tama.domain.events import Action, Outcome
from tama.domain.journal import EntryKind, Topic
from tama.domain.minigames import GameKind, GameResult
from tama.domain.stage import DeathCause
from tama.infra.clock import FakeClock
from tama.infra.paths import SAVE_PATH_ENV
from tama.persistence.roster import PetRoster
from tama.services.describe import describe_entry, journal_entries
from tama.services.session import GameSession, SessionSettings
from tests.factories import FIXED_NOW
from tests.fakes import InMemorySaveRepository
from tests.integration.test_cli_pets import data_dir

CHECK_EVERY = timedelta(minutes=5)


def live_a_whole_life() -> tuple[GameSession, InMemorySaveRepository, Counter[str]]:
    """A diligent player looks in every 5 minutes, through the session, until old age."""
    clock, repo = FakeClock(FIXED_NOW), InMemorySaveRepository()
    session = GameSession.create(
        "Mochi", repo=repo, clock=clock, settings=SessionSettings(), seed=4
    )
    taken: Counter[str] = Counter()

    def do(outcome: Outcome) -> None:
        if outcome.refusal is None:
            taken[outcome.events[0].__class__.__name__] += 1

    wins = 0
    while session.pet.is_alive:
        clock.advance(CHECK_EVERY)
        session.tick()
        pet = session.pet
        if pet.misbehaving and not pet.is_asleep:
            do(session.act(Action.DISCIPLINE))
        if pet.is_sick and not pet.is_asleep:
            do(session.act(Action.MEDICINE))
        if pet.poop_count:
            do(session.act(Action.CLEAN))
        if session.pet.stats.hunger < 70:
            do(session.act(Action.MEAL))
        if session.pet.stats.happiness < 70 and session.act(Action.PLAY).refusal is None:
            wins += 1
            result = GameResult.WIN if wins % 3 else GameResult.LOSS
            do(session.finish_game(result, GameKind.FOUR_IN_A_ROW))
        if session.pet.is_asleep == session.pet.lights_on:
            session.act(Action.LIGHTS)
    session.save()
    return session, repo, taken


@pytest.fixture(autouse=True)
def several_pets_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SAVE_PATH_ENV)
    monkeypatch.setattr(cli, "configure_logging", lambda directory: directory / "tama.log")


@pytest.mark.slow
def test_a_whole_life_journal_tells_its_story_and_tama_journal_prints_it() -> None:
    session, repo, taken = live_a_whole_life()
    journal = session.journal

    story = [describe_entry(e) for e in journal.entries if e.kind is EntryKind.LIFE]
    assert story == [
        "Hatched",
        "Grew into a child",
        "Grew into a teen",
        "Grew into a well-behaved adult",
        "Grew into an elder",
        "Passed away peacefully of old age",
        "Left an egg",
    ]
    assert session.pet.cause_of_death is DeathCause.OLD_AGE
    assert [e.at for e in journal.entries] == sorted(e.at for e in journal.entries)

    tallies = journal.tallies
    assert tallies.meals == taken["Ate"]
    games = tallies.game(GameKind.FOUR_IN_A_ROW)
    assert games.won + games.lost == taken["Played"]
    assert tallies.tantrums_caught == taken["Disciplined"]
    assert tallies.doses == taken["MedicineGiven"]
    assert tallies.care_mistakes == session.pet.care_mistakes
    assert any(e.topic is Topic.MILESTONE for e in journal.entries)

    file = PetRoster(data_dir()).create("Mochi")
    assert repo.game is not None
    assert repo.game.journal == journal
    file.repo().save(repo.game)
    before = file.path.read_bytes()

    result = CliRunner().invoke(app, ["journal"])

    assert result.exit_code == 0
    printed = result.stdout.splitlines()
    assert printed[printed.index("") + 1 :] == journal_entries(journal, session.tz)
    assert file.path.read_bytes() == before
