"""A whole busy life keeps its save small, journal included (ROADMAP M6.10, ADR 0009)."""

from datetime import UTC, timedelta
from random import Random

import pytest
from tools.balance import PLAYERS, START, care

from tama.domain.balance import DEFAULT_BALANCE
from tama.domain.context import Context
from tama.domain.events import CareMistake, Disciplined, MistakeReason, Outcome
from tama.domain.journal import MAX_MOMENTS, EntryKind, Journal, record
from tama.domain.pet import Pet, new_egg
from tama.domain.simulation import advance
from tama.domain.stage import DeathCause
from tama.persistence.codec import encode
from tama.persistence.models import SaveGame

CHECK_EVERY = timedelta(minutes=5)


@pytest.mark.slow
def test_a_whole_busy_life_keeps_the_save_under_64_kib() -> None:
    ctx = Context(rng=Random(3), balance=DEFAULT_BALANCE, tz=UTC)
    pet, journal = new_egg("Busy", START, Random(3)), Journal()
    snacker = PLAYERS[4]
    while pet.is_alive:
        out = advance(pet, CHECK_EVERY, ctx)
        journal, pet = record(journal, out.events, pet), out.pet
        if snacker.present(pet.updated_at):

            def write(before: Pet, outcome: Outcome) -> None:
                nonlocal journal
                journal = record(journal, outcome.events, before)

            pet = care(pet, ctx, snacker=True, seen=write)

    text = encode(SaveGame(pet, ctx.rng.getstate(), journal))

    assert pet.cause_of_death is DeathCause.OLD_AGE  # a whole life
    assert journal.tallies.snacks > 100
    assert len(text.encode()) < 64 * 1024


@pytest.mark.slow
def test_a_journal_full_of_moments_still_fits() -> None:
    pet = new_egg("Worst Case Pet", START, Random(0))
    minute = timedelta(minutes=1)
    tantrums = [Disciplined(minute * i, effective=True) for i in range(5_000)]
    mistakes = [CareMistake(minute * i, MistakeReason.HYGIENE) for i in range(5_000)]

    journal = record(Journal(), [*tantrums, *mistakes], pet)
    text = encode(SaveGame(pet, Random(0).getstate(), journal))

    assert [e.kind for e in journal.entries].count(EntryKind.MOMENT) == MAX_MOMENTS
    assert len(text.encode()) < 64 * 1024
