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
    LightsToggled,
    MedicineGiven,
    Misbehaved,
    MisbehaviourIgnored,
    MistakeReason,
    NeedLow,
    PausedForHoliday,
    PauseRefused,
    Played,
    Pooped,
    RefusalReason,
    Refused,
    ResumedFromHoliday,
    WokeUp,
)
from tama.domain.minigames import GameResult
from tama.domain.stage import DeathCause, LifeStage, Variant
from tama.domain.stats import Stat, Stats
from tama.services.describe import (
    describe_event,
    format_age,
    holiday_since,
    status_line,
    summarize,
)
from tests.factories import make_pet

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
        (Evolved(AGE, LifeStage.ADULT, LifeStage.ELDER, Variant.GOOD), "Grew into an elder"),
        (Died(AGE, DeathCause.OLD_AGE), "Passed away peacefully of old age"),
        (Died(AGE, DeathCause.POOR_HEALTH), "Passed away from poor health"),
        (FellAsleep(AGE), "Fell asleep"),
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
        (Misbehaved(AGE), "Misbehaved"),
        (MisbehaviourIgnored(AGE), "Got away with misbehaving"),
        (Ate(AGE, Action.MEAL), "Ate a meal"),
        (Ate(AGE, Action.SNACK), "Ate a snack"),
        (Played(AGE, GameResult.WIN), "Won a game"),
        (Played(AGE, GameResult.DRAW), "Drew a game"),
        (Played(AGE, GameResult.LOSS), "Lost a game"),
        (Cleaned(AGE, 2), "Was cleaned up"),
        (MedicineGiven(AGE, cured=True), "Was cured"),
        (MedicineGiven(AGE, cured=False), "Took some medicine"),
        (LightsToggled(AGE, on=True), "Lights on"),
        (LightsToggled(AGE, on=False), "Lights off"),
        (Disciplined(AGE, effective=True), "Was disciplined"),
        (Disciplined(AGE, effective=False), "Was scolded for nothing"),
        (Refused(AGE, Action.MEAL, RefusalReason.NOT_HUNGRY), "Refused a meal: not hungry"),
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
        (PausedForHoliday(AGE), "Went on holiday"),
        (ResumedFromHoliday(AGE, timedelta(days=3, hours=2)), "Was on holiday for 3d 2h"),
        (PauseRefused(AGE, ("hungry", "lights")), "Can't go on holiday: hungry, lights on"),
        (PauseRefused(AGE, ("on_holiday",)), "Can't go on holiday: already on holiday"),
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
