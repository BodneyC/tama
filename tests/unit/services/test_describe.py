from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from tama.domain.balance import DEFAULT_BALANCE
from tama.domain.events import (
    Action,
    Ate,
    CareMistake,
    Cleaned,
    Died,
    Disciplined,
    Event,
    Evolved,
    FellAsleep,
    GotSick,
    HeirHatched,
    LaidEgg,
    LearnedTrick,
    LightsToggled,
    MedicineGiven,
    Misbehaved,
    MisbehaviourIgnored,
    MistakeReason,
    NeedLow,
    PausedForHoliday,
    PauseRefused,
    Played,
    PlayedWith,
    Pooped,
    RefusalReason,
    Refused,
    ResumedFromHoliday,
    Visited,
    WeightLeftBand,
    Woken,
    WokeUp,
)
from tama.domain.journal import Entry, EntryKind, GameTally, Tallies, Topic
from tama.domain.minigames import GameKind, GameResult
from tama.domain.pet import AncestorRecord
from tama.domain.stage import DeathCause, LifeStage, Trick, Variant
from tama.domain.stats import Stat, Stats
from tama.domain.visit import VisitRefusal
from tama.domain.weight import WeightStatus
from tama.services.describe import (
    Tone,
    describe_event,
    family_line,
    format_age,
    holiday_since,
    lineage_text,
    status_line,
    status_segments,
    summarize,
    tricks_text,
    visit_ended_text,
    visit_refusal_text,
)
from tama.services.describe_journal import describe_entry, entry_line, life_in_numbers, tally_lines
from tests.factories import FIXED_NOW, make_pet

AGE = timedelta(hours=1)


@pytest.mark.parametrize(
    ("age", "text"),
    [
        (timedelta(0), "0m"),
        (timedelta(seconds=59), "0m"),
        (timedelta(minutes=45), "45m"),
        (timedelta(hours=3, minutes=7), "3h 7m"),
        (timedelta(days=2, hours=4, minutes=30), "2d 4h"),
        (timedelta(days=12), "12d 0h"),
    ],
)
def test_format_age(age: timedelta, text: str) -> None:
    assert format_age(age) == text


@pytest.mark.parametrize(
    ("event", "text"),
    [
        (Evolved(AGE, LifeStage.EGG, LifeStage.BABY, Variant.DEFAULT), "Hatched"),
        (Evolved(AGE, LifeStage.BABY, LifeStage.CHILD, Variant.DEFAULT), "Grew into a child"),
        (
            Evolved(AGE, LifeStage.TEEN, LifeStage.ADULT, Variant.GOOD),
            "Grew into a well-behaved adult",
        ),
        (
            Evolved(AGE, LifeStage.TEEN, LifeStage.ADULT, Variant.SCRUFFY),
            "Grew into a scruffy adult",
        ),
        (
            Evolved(AGE, LifeStage.TEEN, LifeStage.ADULT, Variant.CHUBBY),
            "Grew into a chubby adult",
        ),
        (Evolved(AGE, LifeStage.TEEN, LifeStage.ADULT, Variant.DEFAULT), "Grew into an adult"),
        (Evolved(AGE, LifeStage.ADULT, LifeStage.ELDER, Variant.GOOD), "Grew into an elder"),
        (Died(AGE, DeathCause.OLD_AGE), "Passed away peacefully of old age"),
        (Died(AGE, DeathCause.POOR_HEALTH), "Passed away from poor health"),
        (FellAsleep(AGE), "Fell asleep"),
        (LaidEgg(AGE), "Left an egg"),
        (HeirHatched(AGE, "Mochi II"), "Its egg hatched as Mochi II"),
        (WokeUp(AGE), "Woke up"),
        (Pooped(AGE, 2), "Pooped"),
        (GotSick(AGE, 1), "Got sick"),
        (NeedLow(AGE, Stat.HUNGER), "Got hungry"),
        (NeedLow(AGE, Stat.HAPPINESS), "Got unhappy"),
        (NeedLow(AGE, Stat.HYGIENE), "Got dirty"),
        (CareMistake(AGE, MistakeReason.HUNGER), "Was left starving"),
        (CareMistake(AGE, MistakeReason.HAPPINESS), "Was left miserable"),
        (CareMistake(AGE, MistakeReason.HYGIENE), "Was left filthy"),
        (CareMistake(AGE, MistakeReason.LIGHTS), "Slept with the lights on"),
        (CareMistake(AGE, MistakeReason.WEIGHT), "Was left at an unhealthy weight"),
        (WeightLeftBand(AGE, WeightStatus.OVER), "Got overweight"),
        (WeightLeftBand(AGE, WeightStatus.UNDER), "Got underweight"),
        (Misbehaved(AGE), "Misbehaved"),
        (MisbehaviourIgnored(AGE), "Got away with misbehaving"),
        (Ate(AGE, Action.MEAL), "Ate a meal"),
        (Ate(AGE, Action.SNACK), "Ate a snack"),
        (Ate(AGE, Action.MEAL, stuffed=True), "Ate a meal anyway and is stuffed"),
        (Played(AGE, GameResult.WIN, GameKind.LEFT_RIGHT), "Won a game"),
        (Played(AGE, GameResult.DRAW, GameKind.LEFT_RIGHT), "Drew a game"),
        (Played(AGE, GameResult.LOSS, GameKind.LEFT_RIGHT), "Lost a game"),
        (Cleaned(AGE, 2), "Was cleaned up"),
        (MedicineGiven(AGE, cured=True), "Was cured"),
        (MedicineGiven(AGE, cured=False), "Took some medicine"),
        (LightsToggled(AGE, on=True), "Lights on"),
        (LightsToggled(AGE, on=False), "Lights off"),
        (Disciplined(AGE, effective=True), "Was disciplined"),
        (Disciplined(AGE, effective=False), "Was scolded for nothing"),
        (Refused(AGE, Action.PLAY, RefusalReason.TOO_TIRED), "Refused to play: too tired"),
        (Refused(AGE, Action.PLAY, RefusalReason.ASLEEP), "Refused to play: asleep"),
        (
            Refused(AGE, Action.MEAL, RefusalReason.MISBEHAVING),
            "Turned its nose up at a meal: misbehaving",
        ),
        (
            Refused(AGE, Action.SNACK, RefusalReason.MISBEHAVING),
            "Turned its nose up at a snack: misbehaving",
        ),
        (Refused(AGE, Action.PLAY, RefusalReason.MISBEHAVING), "Sulked and wouldn't play"),
        (Refused(AGE, Action.MEAL, RefusalReason.ON_HOLIDAY), "Refused a meal: on holiday"),
        (
            Refused(AGE, Action.MEDICINE, RefusalReason.ASLEEP),
            "Fast asleep: wake it up to give medicine",
        ),
        (Refused(AGE, Action.WAKE, RefusalReason.AWAKE), "Already awake"),
        (Refused(AGE, Action.WAKE, RefusalReason.EGG), "Refused to be woken: egg"),
        (Woken(AGE), "Was woken up and threw a tantrum"),
        (LearnedTrick(AGE, Trick.SPIN), "Learned to spin!"),
        (PausedForHoliday(AGE), "Went on holiday"),
        (ResumedFromHoliday(AGE, timedelta(days=3, hours=2)), "Was on holiday for 3d 2h"),
        (PauseRefused(AGE, ("hungry", "lights")), "Can't go on holiday: hungry, lights on"),
        (PauseRefused(AGE, ("on_holiday",)), "Can't go on holiday: already on holiday"),
        (Visited(AGE, "Pip", cheered=True), "Spent time with Pip"),
        (
            PlayedWith(AGE, "Pip", GameKind.FOUR_IN_A_ROW, GameResult.WIN),
            "Beat Pip at Four in a Row",
        ),
        (
            PlayedWith(AGE, "Pip", GameKind.TIC_TAC_TOE, GameResult.DRAW),
            "Drew with Pip at Tic-Tac-Toe",
        ),
        (
            PlayedWith(AGE, "Pip", GameKind.TIC_TAC_TOE, GameResult.LOSS),
            "Lost to Pip at Tic-Tac-Toe",
        ),
    ],
)
def test_describe_event(event: Event, text: str) -> None:
    assert describe_event(event) == text


def test_summarize_groups_repeats_in_first_seen_order() -> None:
    events = [
        Pooped(AGE, 1),
        FellAsleep(AGE),
        Pooped(AGE, 2),
        WokeUp(AGE),
        Pooped(AGE, 3),
        FellAsleep(AGE),
    ]

    assert summarize(events) == ["Pooped ×3", "Fell asleep ×2", "Woke up"]


def test_summarize_nothing() -> None:
    assert summarize([]) == []


def test_status_line_for_a_content_pet() -> None:
    pet = make_pet(stats=Stats(hunger=80, happiness=70, energy=60, hygiene=90, health=100))

    assert status_line(pet, DEFAULT_BALANCE) == (
        "Mochi · child tama · 1h 0m · hunger 80 · happy 70 · energy 60 · clean 90 · health 100"
    )


def test_status_line_lists_attention_reasons() -> None:
    pet = make_pet(sickness_doses=1, poop_count=2)

    assert status_line(pet, DEFAULT_BALANCE).endswith(" · needs: sick, poop")


def test_status_line_for_egg_and_dead_pets() -> None:
    egg = make_pet(stage=LifeStage.EGG)
    dead = make_pet(stage=LifeStage.DEAD, cause_of_death=DeathCause.OLD_AGE)

    assert status_line(egg, DEFAULT_BALANCE) == "Mochi · tama egg · about to hatch"
    assert status_line(dead, DEFAULT_BALANCE) == "Mochi · tama · passed away (old age) at 15d 0h"


def test_status_segments_say_how_each_part_should_look() -> None:
    pet = make_pet(stats=Stats(hunger=80, happiness=30, energy=10, hygiene=50, health=100))

    assert status_segments(pet, DEFAULT_BALANCE) == [
        ("Mochi", Tone.NAME),
        ("child tama", Tone.PLAIN),
        ("1h 0m", Tone.PLAIN),
        ("hunger 80", Tone.GOOD),
        ("happy 30", Tone.FAIR),
        ("energy 10", Tone.LOW),
        ("clean 50", Tone.GOOD),
        ("health 100", Tone.GOOD),
    ]


def test_needs_are_an_alert() -> None:
    segments = status_segments(make_pet(poop_count=1), DEFAULT_BALANCE)

    assert segments[-1] == ("needs: poop", Tone.ALERT)


def test_eggs_holidays_and_the_dead_have_their_own_tones() -> None:
    egg = make_pet(stage=LifeStage.EGG)
    away = make_pet(paused_since=FIXED_NOW)
    dead = make_pet(stage=LifeStage.DEAD, cause_of_death=DeathCause.OLD_AGE)

    assert [tone for _, tone in status_segments(egg, DEFAULT_BALANCE)] == [
        Tone.NAME,
        Tone.PLAIN,
        Tone.PLAIN,
    ]
    assert status_segments(away, DEFAULT_BALANCE)[-1][1] is Tone.AWAY
    assert {tone for _, tone in status_segments(dead, DEFAULT_BALANCE)} == {Tone.GONE}


def test_status_line_names_the_species() -> None:
    assert status_line(make_pet(species="owl"), DEFAULT_BALANCE).startswith("Mochi · child owl · ")
    egg = make_pet(species="bear", stage=LifeStage.EGG)
    assert status_line(egg, DEFAULT_BALANCE) == "Mochi · bear egg · about to hatch"


def test_unknown_event_types_fall_back_to_class_name() -> None:
    assert describe_event(Event(AGE)) == "Event"


def test_status_line_for_a_pet_on_holiday() -> None:
    pet = make_pet(
        stage=LifeStage.ADULT, species="owl", paused_since=datetime(2026, 11, 3, 23, tzinfo=UTC)
    )

    assert status_line(pet, DEFAULT_BALANCE) == "Mochi · adult owl · on holiday since 3 Nov"


def test_holiday_dates_are_in_the_players_time_zone() -> None:
    late = datetime(2026, 11, 3, 23, tzinfo=UTC)

    assert holiday_since(late, timezone(timedelta(hours=2))) == "4 Nov"
    assert holiday_since(late) == "3 Nov"


# --- Journal entries (SPEC §2.9) ------------------------------------------------------------


def journal_entry(kind: EntryKind, topic: Topic, detail: str = "") -> Entry:
    return Entry(kind, topic, datetime(2026, 11, 3, 14, 5, tzinfo=UTC), AGE, detail)


L, F, M = EntryKind.LIFE, EntryKind.FIRST, EntryKind.MOMENT


@pytest.mark.parametrize(
    ("entry", "text"),
    [
        (journal_entry(L, Topic.JOURNAL_STARTED), "Started keeping a journal"),
        (journal_entry(L, Topic.HATCHED), "Hatched"),
        (journal_entry(L, Topic.HATCHED, "Mochi"), "Hatched from Mochi's egg"),
        (journal_entry(L, Topic.LAID_EGG), "Left an egg"),
        (journal_entry(L, Topic.HEIR_HATCHED, "Mochi II"), "Its egg hatched as Mochi II"),
        (journal_entry(L, Topic.EVOLVED, "teen/default"), "Grew into a teen"),
        (journal_entry(L, Topic.EVOLVED, "adult/chubby"), "Grew into a chubby adult"),
        (journal_entry(L, Topic.EVOLVED, "elder/good"), "Grew into an elder"),
        (journal_entry(L, Topic.DIED, "old_age"), "Passed away peacefully of old age"),
        (journal_entry(L, Topic.HOLIDAY), "Went on holiday"),
        (journal_entry(L, Topic.BACK, "4327"), "Came back from 3d 0h on holiday"),
        (journal_entry(F, Topic.MEAL), "First meal"),
        (journal_entry(F, Topic.SNACK), "First snack"),
        (journal_entry(F, Topic.TANTRUM), "First tantrum"),
        (journal_entry(F, Topic.SICKNESS), "Fell sick for the first time"),
        (journal_entry(F, Topic.WIN, "four_in_a_row"), "First win at Four in a Row"),
        (journal_entry(F, Topic.TRICK, "spin"), "Learned to spin"),
        (journal_entry(F, Topic.CARE_MISTAKE, "hunger"), "First care mistake: was left starving"),
        (journal_entry(M, Topic.CARE_MISTAKE, "lights"), "Slept with the lights on"),
        (journal_entry(M, Topic.CURED, ""), "Got better"),
        (journal_entry(M, Topic.TANTRUM_CAUGHT), "Was disciplined for a tantrum"),
        (journal_entry(M, Topic.TANTRUM_IGNORED), "Got away with a tantrum"),
        (journal_entry(M, Topic.MILESTONE, "meals:10"), "Ate its 10th meal"),
        (journal_entry(M, Topic.MILESTONE, "games_won:50"), "Won its 50th game"),
        (journal_entry(F, Topic.VISIT, "Pip"), "First visit, with Pip"),
        (journal_entry(M, Topic.VISIT, "Pip"), "Spent time with Pip"),
        (journal_entry(M, Topic.PLAYED_WITH, "four_in_a_row/win/Pip"), "Beat Pip at Four in a Row"),
        (journal_entry(M, Topic.PLAYED_WITH, "tic_tac_toe/loss/A/B"), "Lost to A/B at Tic-Tac-Toe"),
    ],
)
def test_journal_entries(entry: Entry, text: str) -> None:
    assert describe_entry(entry) == text


def test_an_entry_line_has_the_local_date_time_and_age() -> None:
    entry = journal_entry(L, Topic.HATCHED)

    line = entry_line(entry, timezone(timedelta(hours=-5)))

    assert line == "3 Nov 09:05  1h 0m   Hatched"


def test_tallies_summarise_a_life() -> None:
    tallies = Tallies(
        meals=12,
        snacks=3,
        tantrums_caught=4,
        tantrums_ignored=1,
        sicknesses=2,
        doses=3,
        poops_cleaned=9,
        holidays=1,
        care_mistakes=2,
        visits=5,
        games=(
            (GameKind.FOUR_IN_A_ROW, GameTally(won=2, drawn=1, lost=3)),
            (GameKind.TIC_TAC_TOE, GameTally(won=1)),
        ),
    )

    assert tally_lines(tallies) == [
        "Meals 12 · snacks 3 · poops cleaned 9",
        "Tantrums 4 caught, 1 ignored · sick 2 times, 3 doses",
        "Care mistakes 2 · holidays 1 · visits 5",
        "Four in a Row: won 2, drew 1, lost 3",
        "Tic-Tac-Toe: won 1, drew 0, lost 0",
    ]


def test_tallies_of_a_new_journal() -> None:
    assert tally_lines(Tallies()) == [
        "Meals 0 · snacks 0 · poops cleaned 0",
        "Tantrums 0 caught, 0 ignored · sick 0 times, 0 doses",
        "Care mistakes 0 · holidays 0 · visits 0",
        "No games played yet",
    ]


@pytest.mark.parametrize(
    ("tallies", "text"),
    [
        (Tallies(), "0 meals, 0 snacks, 0 wins"),
        (
            Tallies(meals=1, snacks=2, games=((GameKind.TIC_TAC_TOE, GameTally(won=1)),)),
            "1 meal, 2 snacks, 1 win",
        ),
    ],
)
def test_life_in_numbers(tallies: Tallies, text: str) -> None:
    assert life_in_numbers(tallies) == text


# --- Family line (SPEC §2.8) ----------------------------------------------------------------


def line_of(*names: str) -> tuple[AncestorRecord, ...]:
    return tuple(
        AncestorRecord(name, FIXED_NOW, n, Variant.GOOD, timedelta(days=15))
        for n, name in enumerate(names, start=1)
    )


@pytest.mark.parametrize(
    ("discipline", "text"), [(0, "none yet"), (25, "wave"), (100, "wave, spin, dance, bow")]
)
def test_tricks_text_lists_the_tricks_it_knows(discipline: int, text: str) -> None:
    pet = make_pet(stats=Stats(discipline=discipline))

    assert tricks_text(pet, DEFAULT_BALANCE) == text


@pytest.mark.parametrize("stage", [LifeStage.EGG, LifeStage.BABY])
def test_too_young_for_tricks_has_no_tricks_line(stage: LifeStage) -> None:
    assert tricks_text(make_pet(stage=stage, stats=Stats(discipline=100)), DEFAULT_BALANCE) is None


def test_a_founder_has_no_lineage_to_show() -> None:
    assert lineage_text(make_pet()) is None
    assert family_line(make_pet()) is None


def test_lineage_names_the_generation_and_founder() -> None:
    pet = make_pet(generation=3, ancestors=line_of("Mochi", "Mochi II"))

    assert lineage_text(pet) == "Generation 3 · founded by Mochi"


@pytest.mark.parametrize(
    ("names", "line"),
    [
        (("Mochi",), "Mochi → Mochi II"),
        (("Mochi", "Mochi II"), "Mochi → Mochi II → Mochi III"),
        (("Mochi", "Bao", "Mochi II"), "Mochi → Bao → Mochi II → Mochi III"),
        (("Mochi", "Pip", "Bao", "Mochi II"), "… → Pip → Bao → Mochi II → Mochi III"),
    ],
)
def test_the_family_line_ends_with_the_pet(names: tuple[str, ...], line: str) -> None:
    pet = replace(
        make_pet(), name="Mochi II" if len(names) == 1 else "Mochi III", ancestors=line_of(*names)
    )

    assert family_line(pet) == line


@pytest.mark.parametrize(
    ("reason", "text"),
    [
        (VisitRefusal.EGG, "still an egg"),
        (VisitRefusal.DEAD, "no longer alive"),
        (VisitRefusal.ON_HOLIDAY, "on holiday"),
        (VisitRefusal.ASLEEP, "asleep"),
        (VisitRefusal.SICK, "sick"),
        (VisitRefusal.MISBEHAVING, "misbehaving"),
        (VisitRefusal.TOO_TIRED, "too tired"),
    ],
)
def test_visit_refusals_in_words(reason: VisitRefusal, text: str) -> None:
    assert visit_refusal_text(reason) == text


@pytest.mark.parametrize(
    ("reason", "guest_text", "host_text"),
    [
        (VisitRefusal.ASLEEP, "Pip got sleepy and went home", "Mochi got sleepy, so Pip went home"),
        (VisitRefusal.SICK, "Pip felt poorly and went home", "Mochi felt poorly, so Pip went home"),
        (
            VisitRefusal.MISBEHAVING,
            "Pip threw a tantrum and went home",
            "Mochi threw a tantrum, so Pip went home",
        ),
        (
            VisitRefusal.TOO_TIRED,
            "Pip was worn out and went home",
            "Mochi was worn out, so Pip went home",
        ),
        (VisitRefusal.DEAD, "Pip passed away", "Mochi passed away, so Pip went home"),
        (
            VisitRefusal.ON_HOLIDAY,
            "Pip went on holiday",
            "Mochi went on holiday, so Pip went home",
        ),
    ],
)
def test_why_a_visit_ended(reason: VisitRefusal, guest_text: str, host_text: str) -> None:
    assert visit_ended_text(host="Mochi", guest="Pip", leaver="Pip", reason=reason) == guest_text
    assert visit_ended_text(host="Mochi", guest="Pip", leaver="Mochi", reason=reason) == host_text
