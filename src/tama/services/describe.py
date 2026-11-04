"""Plain-text descriptions of the pet and its events.

Shared by the ``tama status`` command and the TUI (e.g. the "While you were away" summary),
so neither has to know the full event vocabulary.
"""

from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta, tzinfo

from tama.domain.attention import AttentionReason, attention_reasons
from tama.domain.balance import Balance
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
    WeightLeftBand,
    Woken,
    WokeUp,
)
from tama.domain.journal import Entry, EntryKind, Journal, Tallies, Topic
from tama.domain.minigames import GameKind, GameResult
from tama.domain.pet import Pet
from tama.domain.stage import DeathCause, LifeStage, Variant
from tama.domain.stats import Stat
from tama.domain.weight import WeightStatus

_NEED_LOW = {Stat.HUNGER: "Got hungry", Stat.HAPPINESS: "Got unhappy", Stat.HYGIENE: "Got dirty"}
_PLAYED = {
    GameResult.WIN: "Won a game",
    GameResult.DRAW: "Drew a game",
    GameResult.LOSS: "Lost a game",
}
_BLOCKERS = {
    "lights": "lights on",
    "on_holiday": "already on holiday",
    "egg": "still an egg",
    "dead": "no longer alive",
}
_MISTAKES = {
    MistakeReason.HUNGER: "Was left starving",
    MistakeReason.HAPPINESS: "Was left miserable",
    MistakeReason.HYGIENE: "Was left filthy",
    MistakeReason.LIGHTS: "Slept with the lights on",
    MistakeReason.WEIGHT: "Was left at an unhealthy weight",
}
_WEIGHT = {WeightStatus.OVER: "Got overweight", WeightStatus.UNDER: "Got underweight"}
_ADULTS = {
    Variant.GOOD: "a well-behaved adult",
    Variant.SCRUFFY: "a scruffy adult",
    Variant.CHUBBY: "a chubby adult",
}
_DEATHS = {
    DeathCause.OLD_AGE: "Passed away peacefully of old age",
    DeathCause.POOR_HEALTH: "Passed away from poor health",
}
_REFUSED_ACTIONS = {
    Action.MEAL: "a meal",
    Action.SNACK: "a snack",
    Action.PLAY: "to play",
    Action.CLEAN: "to be cleaned",
    Action.MEDICINE: "medicine",
    Action.LIGHTS: "the lights",
    Action.DISCIPLINE: "discipline",
    Action.WAKE: "to be woken",
}


def format_age(age: timedelta) -> str:
    """Format a duration compactly: ``45m``, ``3h 7m``, ``2d 4h``."""
    minutes = int(age.total_seconds() // 60)
    days, minutes = divmod(minutes, 24 * 60)
    hours, minutes = divmod(minutes, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _stage_phrase(stage: LifeStage, variant: Variant) -> str:
    if stage is LifeStage.ADULT:
        return _ADULTS.get(variant, "an adult")
    article = "an" if stage.value[0] in "aeiou" else "a"
    return f"{article} {stage.value}"


def describe_event(event: Event) -> str:  # noqa: PLR0911, PLR0912 - one arm per event type
    """A short, past-tense description of ``event``."""
    match event:
        case Evolved(from_stage=LifeStage.EGG):
            return "Hatched"
        case Evolved(to_stage=stage, variant=variant):
            return f"Grew into {_stage_phrase(stage, variant)}"
        case Died(cause=cause):
            return _DEATHS[cause]
        case FellAsleep():
            return "Fell asleep"
        case WokeUp():
            return "Woke up"
        case Pooped():
            return "Pooped"
        case GotSick():
            return "Got sick"
        case NeedLow(stat=stat):
            return _NEED_LOW[stat]
        case CareMistake(reason=reason):
            return _MISTAKES[reason]
        case Misbehaved():
            return "Misbehaved"
        case MisbehaviourIgnored():
            return "Got away with misbehaving"
        case Ate(stuffed=True):
            return "Ate a meal anyway and is stuffed"
        case Ate(food=food):
            return f"Ate a {food.value}"
        case WeightLeftBand(status=status):
            return _WEIGHT[status]
        case Played(result=result):
            return _PLAYED[result]
        case Cleaned():
            return "Was cleaned up"
        case MedicineGiven(cured=cured):
            return "Was cured" if cured else "Took some medicine"
        case LightsToggled(on=on):
            return "Lights on" if on else "Lights off"
        case Disciplined(effective=effective):
            return "Was disciplined" if effective else "Was scolded for nothing"
        case Refused(action=Action.MEAL | Action.SNACK as food, reason=RefusalReason.MISBEHAVING):
            return f"Turned its nose up at {_REFUSED_ACTIONS[food]}: misbehaving"
        case Refused(action=Action.PLAY, reason=RefusalReason.MISBEHAVING):
            return "Sulked and wouldn't play"
        case Refused(action=Action.MEDICINE, reason=RefusalReason.ASLEEP):
            return "Fast asleep: wake it up to give medicine"
        case Refused(action=Action.WAKE, reason=RefusalReason.AWAKE):
            return "Already awake"
        case Woken():
            return "Was woken up and threw a tantrum"
        case PausedForHoliday():
            return "Went on holiday"
        case ResumedFromHoliday(length=length):
            return f"Was on holiday for {format_age(length)}"
        case PauseRefused(blockers=blockers):
            return "Can't go on holiday: " + ", ".join(_BLOCKERS.get(b, b) for b in blockers)
        case Refused(action=action, reason=reason):
            return f"Refused {_REFUSED_ACTIONS[action]}: {reason.value.replace('_', ' ')}"
        case _:
            return type(event).__name__


GAME_NAMES = {
    GameKind.LEFT_RIGHT: "Left or Right",
    GameKind.FOUR_IN_A_ROW: "Four in a Row",
    GameKind.TIC_TAC_TOE: "Tic-Tac-Toe",
}
_JOURNAL_TEXT = {
    Topic.JOURNAL_STARTED: "Started keeping a journal",
    Topic.HATCHED: "Hatched",
    Topic.HOLIDAY: "Went on holiday",
    Topic.MEAL: "First meal",
    Topic.SNACK: "First snack",
    Topic.TANTRUM: "First tantrum",
    Topic.SICKNESS: "Fell sick for the first time",
    Topic.CURED: "Got better",
    Topic.TANTRUM_CAUGHT: "Was disciplined for a tantrum",
    Topic.TANTRUM_IGNORED: "Got away with a tantrum",
}
_MILESTONES = {"meals": "Ate its {n} meal", "games_won": "Won its {n} game"}


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def describe_entry(entry: Entry) -> str:  # noqa: PLR0911 - one arm per topic with a detail
    """A journal entry as a short sentence (SPEC §2.9)."""
    match entry.topic:
        case Topic.EVOLVED:
            stage, variant = entry.detail.split("/")
            return f"Grew into {_stage_phrase(LifeStage(stage), Variant(variant))}"
        case Topic.DIED:
            return _DEATHS[DeathCause(entry.detail)]
        case Topic.BACK:
            return f"Came back from {format_age(timedelta(minutes=int(entry.detail)))} on holiday"
        case Topic.WIN:
            return f"First win at {GAME_NAMES[GameKind(entry.detail)]}"
        case Topic.CARE_MISTAKE:
            mistake = _MISTAKES[MistakeReason(entry.detail)]
            if entry.kind is EntryKind.FIRST:
                return f"First care mistake: {mistake[0].lower()}{mistake[1:]}"
            return mistake
        case Topic.MILESTONE:
            tally, count = entry.detail.split(":")
            return _MILESTONES[tally].format(n=_ordinal(int(count)))
        case topic:
            return _JOURNAL_TEXT[topic]


def entry_line(entry: Entry, tz: tzinfo = UTC) -> str:
    """``3 Nov 14:05  1h 0m   Hatched``: when (local time), the pet's age, and what happened."""
    local = entry.at.astimezone(tz)
    when = f"{local.day} {local:%b %H:%M}"
    return f"{when:<12} {format_age(entry.age):<8}{describe_entry(entry)}"


EMPTY_JOURNAL = "Nothing written yet."


def journal_entries(journal: Journal, tz: tzinfo = UTC) -> list[str]:
    """Every entry as an ``entry_line``, newest first (or a line saying there are none)."""
    return [entry_line(entry, tz) for entry in reversed(journal.entries)] or [EMPTY_JOURNAL]


def tally_lines(tallies: Tallies) -> list[str]:
    """A life in numbers: what the journal has counted (SPEC §2.9)."""
    t = tallies
    games = [
        f"{GAME_NAMES[kind]}: won {g.won}, drew {g.drawn}, lost {g.lost}" for kind, g in t.games
    ]
    return [
        f"Meals {t.meals} · snacks {t.snacks} · poops cleaned {t.poops_cleaned}",
        f"Tantrums {t.tantrums_caught} caught, {t.tantrums_ignored} ignored"
        f" · sick {t.sicknesses} times, {t.doses} doses",
        f"Care mistakes {t.care_mistakes} · holidays {t.holidays}",
        *(games or ["No games played yet"]),
    ]


def life_in_numbers(tallies: Tallies) -> str:
    """One short line for the memorial: ``82 meals, 1 snack, 40 wins``."""
    t = tallies
    return ", ".join(
        _plural(n, word)
        for n, word in ((t.meals, "meal"), (t.snacks, "snack"), (t.games_won, "win"))
    )


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def summarize(events: Iterable[Event]) -> list[str]:
    """Describe ``events``, merging repeats into ``"… ×n"`` lines in first-seen order."""
    counts = Counter(describe_event(event) for event in events)
    return [text if n == 1 else f"{text} ×{n}" for text, n in counts.items()]


def holiday_since(when: datetime, tz: tzinfo = UTC) -> str:
    """The day a holiday started, like ``3 Nov``, in the player's time zone."""
    local = when.astimezone(tz)
    return f"{local.day} {local:%b}"


def status_line(pet: Pet, balance: Balance, tz: tzinfo = UTC) -> str:
    """One line describing the pet, suitable for a shell prompt."""
    if pet.stage is LifeStage.DEAD:
        cause = str(pet.cause_of_death).replace("_", " ")
        return f"{pet.name} · {pet.species} · passed away ({cause}) at {format_age(pet.age)}"
    if pet.stage is LifeStage.EGG:
        return f"{pet.name} · {pet.species} egg · about to hatch"
    if pet.paused_since is not None:
        since = holiday_since(pet.paused_since, tz)
        return f"{pet.name} · {pet.stage.value} {pet.species} · on holiday since {since}"
    s = pet.stats
    parts = [
        pet.name,
        f"{pet.stage.value} {pet.species}",
        format_age(pet.age),
        f"hunger {s.hunger}",
        f"happy {s.happiness}",
        f"energy {s.energy}",
        f"clean {s.hygiene}",
        f"health {s.health}",
    ]
    reasons = attention_reasons(pet, balance)
    if reasons:
        parts.append("needs: " + ", ".join(r.value for r in AttentionReason if r in reasons))
    return " · ".join(parts)
