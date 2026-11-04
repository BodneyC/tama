from dataclasses import replace
from datetime import timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tama.domain.events import (
    Action,
    Ate,
    CareMistake,
    Cleaned,
    Died,
    Disciplined,
    Event,
    Evolved,
    GotSick,
    HeirHatched,
    LaidEgg,
    LightsToggled,
    MedicineGiven,
    Misbehaved,
    MisbehaviourIgnored,
    MistakeReason,
    PausedForHoliday,
    Played,
    ResumedFromHoliday,
)
from tama.domain.journal import (
    MAX_MOMENTS,
    Entry,
    EntryKind,
    GameTally,
    Journal,
    Tallies,
    Topic,
    record,
)
from tama.domain.minigames import GameKind, GameResult
from tama.domain.pet import AncestorRecord, Pet
from tama.domain.simulation import advance
from tama.domain.stage import DeathCause, LifeStage, Variant
from tests.factories import FIXED_NOW, make_ctx, make_pet
from tests.strategies import durations, pets

MIN = timedelta(minutes=1)
PET = make_pet()
NOW = PET.updated_at
LIFE, FIRST, MOMENT = EntryKind.LIFE, EntryKind.FIRST, EntryKind.MOMENT
FOUR, TTT = GameKind.FOUR_IN_A_ROW, GameKind.TIC_TAC_TOE


def write(*events: Event, journal: Journal | None = None, before: Pet = PET) -> Journal:
    return record(journal or Journal(), events, before)


def entry(kind: EntryKind, topic: Topic, detail: str = "", later: timedelta = MIN) -> Entry:
    return Entry(kind, topic, NOW + later, PET.age + later, detail)


# --- When things happened ----------------------------------------------------------------------


def test_an_entry_is_dated_by_how_far_the_event_is_past_the_pet_before_it() -> None:
    journal = write(GotSick(PET.age + 90 * MIN, 1))

    assert journal.entries == (entry(FIRST, Topic.SICKNESS, later=90 * MIN),)


def test_time_carried_over_from_a_part_step_is_not_counted_twice() -> None:
    before = replace(PET, carry=timedelta(seconds=20))

    journal = write(GotSick(PET.age + MIN, 1), before=before)

    assert journal.entries[0].at == NOW - timedelta(seconds=20) + MIN


# --- Life ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("event", "topic", "detail"),
    [
        (Evolved(PET.age + MIN, LifeStage.EGG, LifeStage.BABY, Variant.DEFAULT), Topic.HATCHED, ""),
        (
            Evolved(PET.age + MIN, LifeStage.TEEN, LifeStage.ADULT, Variant.CHUBBY),
            Topic.EVOLVED,
            "adult/chubby",
        ),
        (Died(PET.age + MIN, DeathCause.OLD_AGE), Topic.DIED, "old_age"),
        (PausedForHoliday(PET.age + MIN), Topic.HOLIDAY, ""),
        (ResumedFromHoliday(PET.age + MIN, timedelta(days=3, minutes=7)), Topic.BACK, "4327"),
        (LaidEgg(PET.age + MIN), Topic.LAID_EGG, ""),
        (HeirHatched(PET.age + MIN, "Mochi II"), Topic.HEIR_HATCHED, "Mochi II"),
    ],
)
def test_life_events_are_always_written(event: Event, topic: Topic, detail: str) -> None:
    once = write(event)
    twice = write(event, journal=once)

    assert once.entries == (entry(LIFE, topic, detail),)
    assert twice.entries == once.entries * 2


def test_an_heir_hatching_names_whose_egg_it_was() -> None:
    parent = AncestorRecord("Mochi", FIXED_NOW, 1, Variant.GOOD, timedelta(days=16))
    heir = replace(PET, ancestors=(parent,), generation=2)
    hatched = Evolved(PET.age + MIN, LifeStage.EGG, LifeStage.BABY, Variant.DEFAULT)

    assert write(hatched, before=heir).entries == (entry(LIFE, Topic.HATCHED, "Mochi"),)


# --- Firsts --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("event", "topic", "detail"),
    [
        (Ate(PET.age + MIN, Action.MEAL), Topic.MEAL, ""),
        (Ate(PET.age + MIN, Action.SNACK), Topic.SNACK, ""),
        (Misbehaved(PET.age + MIN), Topic.TANTRUM, ""),
        (GotSick(PET.age + MIN, 2), Topic.SICKNESS, ""),
        (Played(PET.age + MIN, GameResult.WIN, FOUR), Topic.WIN, "four_in_a_row"),
    ],
)
def test_only_the_first_time_is_written(event: Event, topic: Topic, detail: str) -> None:
    journal = write(event, event)

    assert journal.entries == (entry(FIRST, topic, detail),)


def test_the_first_win_is_written_for_each_game() -> None:
    journal = write(
        Played(PET.age + MIN, GameResult.WIN, FOUR),
        Played(PET.age + MIN, GameResult.WIN, TTT),
        Played(PET.age + MIN, GameResult.WIN, FOUR),
    )

    assert [e.detail for e in journal.entries] == ["four_in_a_row", "tic_tac_toe"]


def test_games_that_were_not_won_are_not_firsts() -> None:
    journal = write(
        Played(PET.age + MIN, GameResult.DRAW, FOUR), Played(PET.age + MIN, GameResult.LOSS, TTT)
    )

    assert journal.entries == ()


def test_the_first_care_mistake_is_a_first_and_later_ones_are_moments() -> None:
    hunger = CareMistake(PET.age + MIN, MistakeReason.HUNGER)
    lights = CareMistake(PET.age + MIN, MistakeReason.LIGHTS)

    journal = write(hunger, lights)

    assert journal.entries == (
        entry(FIRST, Topic.CARE_MISTAKE, "hunger"),
        entry(MOMENT, Topic.CARE_MISTAKE, "lights"),
    )


# --- Moments -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("event", "topic"),
    [
        (MedicineGiven(PET.age + MIN, cured=True), Topic.CURED),
        (Disciplined(PET.age + MIN, effective=True), Topic.TANTRUM_CAUGHT),
        (MisbehaviourIgnored(PET.age + MIN), Topic.TANTRUM_IGNORED),
    ],
)
def test_moments(event: Event, topic: Topic) -> None:
    assert write(event).entries == (entry(MOMENT, topic),)


@pytest.mark.parametrize(
    "event",
    [
        MedicineGiven(PET.age + MIN, cured=False),
        Disciplined(PET.age + MIN, effective=False),
        LightsToggled(PET.age + MIN, on=False),
        Cleaned(PET.age + MIN, 2),
    ],
)
def test_everyday_events_write_nothing(event: Event) -> None:
    assert write(event).entries == ()


def test_round_numbers_of_meals_and_wins_are_moments() -> None:
    meals = [Ate(PET.age + MIN, Action.MEAL)] * 10
    wins = [Played(PET.age + MIN, GameResult.WIN, game) for game in (FOUR, TTT) * 5]

    journal = write(*meals, *wins)

    milestones = [e for e in journal.entries if e.kind is MOMENT]
    assert milestones == [
        entry(MOMENT, Topic.MILESTONE, "meals:10"),
        entry(MOMENT, Topic.MILESTONE, "games_won:10"),
    ]


def test_moments_are_capped_but_life_and_firsts_are_kept() -> None:
    hatched = Evolved(PET.age + MIN, LifeStage.EGG, LifeStage.BABY, Variant.DEFAULT)
    caught = [Disciplined(PET.age + MIN * i, effective=True) for i in range(2, MAX_MOMENTS + 12)]

    journal = write(hatched, Misbehaved(PET.age + MIN), *caught)

    kinds = [e.kind for e in journal.entries]
    assert kinds[:2] == [LIFE, FIRST]
    assert kinds.count(MOMENT) == MAX_MOMENTS
    assert journal.entries[-1].age == caught[-1].age  # the newest are kept


# --- Tallies -------------------------------------------------------------------------------


def test_tallies_count_the_whole_life() -> None:
    journal = write(
        Ate(PET.age, Action.MEAL),
        Ate(PET.age, Action.MEAL, stuffed=True),
        Ate(PET.age, Action.SNACK),
        Played(PET.age, GameResult.WIN, FOUR),
        Played(PET.age, GameResult.DRAW, FOUR),
        Played(PET.age, GameResult.LOSS, TTT),
        Disciplined(PET.age, effective=True),
        MisbehaviourIgnored(PET.age),
        GotSick(PET.age, 2),
        MedicineGiven(PET.age, cured=False),
        MedicineGiven(PET.age, cured=True),
        Cleaned(PET.age, 3),
        Cleaned(PET.age, 0),
        PausedForHoliday(PET.age),
        CareMistake(PET.age, MistakeReason.HYGIENE),
    )

    assert journal.tallies == Tallies(
        meals=2,
        snacks=1,
        tantrums_caught=1,
        tantrums_ignored=1,
        sicknesses=1,
        doses=2,
        poops_cleaned=3,
        holidays=1,
        care_mistakes=1,
        games=((FOUR, GameTally(won=1, drawn=1)), (TTT, GameTally(lost=1))),
    )
    assert journal.tallies.games_won == 1
    assert journal.tallies.game(GameKind.LEFT_RIGHT) == GameTally()


def test_recording_nothing_changes_nothing() -> None:
    journal = write(Ate(PET.age, Action.MEAL))

    assert record(journal, (), PET) is journal


# --- The journal follows the simulation's tick-splitting equivalence (ADR 0002, 0009) ------


@settings(deadline=None, max_examples=60)
@given(
    pets(alive=True), durations(timedelta(hours=30)), durations(timedelta(hours=30)), st.integers()
)
def test_splitting_time_writes_the_same_journal(
    pet: Pet, first: timedelta, second: timedelta, seed: int
) -> None:
    whole_ctx, split_ctx = make_ctx(seed), make_ctx(seed)

    whole = advance(pet, first + second, whole_ctx)
    part = advance(pet, first, split_ctx)
    rest = advance(part.pet, second, split_ctx)

    expected = record(Journal(), whole.events, pet)
    assert record(record(Journal(), part.events, pet), rest.events, part.pet) == expected


def test_a_simulated_day_is_dated_in_step_with_the_clock() -> None:
    egg = replace(make_pet(stage=LifeStage.EGG), age=timedelta(0), updated_at=FIXED_NOW)

    out = advance(egg, timedelta(hours=2), make_ctx())
    journal = record(Journal(), out.events, egg)

    hatched = journal.entries[0]
    assert hatched.topic is Topic.HATCHED
    assert hatched.at == FIXED_NOW + hatched.age
