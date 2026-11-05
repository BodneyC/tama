"""Journal entries and tallies in words (SPEC §2.9), for the journal screen, memorial and CLI."""

from datetime import UTC, timedelta, tzinfo

from tama.domain.events import MistakeReason
from tama.domain.journal import Entry, EntryKind, Journal, Tallies, Topic
from tama.domain.minigames import GameKind, GameResult
from tama.domain.stage import DeathCause, LifeStage, Variant
from tama.services.describe import (
    DEATH_TEXT,
    GAME_NAMES,
    MISTAKE_TEXT,
    format_age,
    played_with_text,
    stage_phrase,
)

_JOURNAL_TEXT = {
    Topic.JOURNAL_STARTED: "Started keeping a journal",
    Topic.LAID_EGG: "Left an egg",
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


def describe_entry(entry: Entry) -> str:  # noqa: PLR0911, PLR0912 - one arm per topic
    """A journal entry as a short sentence (SPEC §2.9)."""
    match entry.topic:
        case Topic.HATCHED:
            return f"Hatched from {entry.detail}'s egg" if entry.detail else "Hatched"
        case Topic.HEIR_HATCHED:
            return f"Its egg hatched as {entry.detail}"
        case Topic.EVOLVED:
            stage, variant = entry.detail.split("/")
            return f"Grew into {stage_phrase(LifeStage(stage), Variant(variant))}"
        case Topic.DIED:
            return DEATH_TEXT[DeathCause(entry.detail)]
        case Topic.BACK:
            return f"Came back from {format_age(timedelta(minutes=int(entry.detail)))} on holiday"
        case Topic.WIN:
            return f"First win at {GAME_NAMES[GameKind(entry.detail)]}"
        case Topic.TRICK:
            return f"Learned to {entry.detail}"
        case Topic.CARE_MISTAKE:
            mistake = MISTAKE_TEXT[MistakeReason(entry.detail)]
            if entry.kind is EntryKind.FIRST:
                return f"First care mistake: {mistake[0].lower()}{mistake[1:]}"
            return mistake
        case Topic.MILESTONE:
            tally, count = entry.detail.split(":")
            return _MILESTONES[tally].format(n=_ordinal(int(count)))
        case Topic.VISIT if entry.kind is EntryKind.FIRST:
            return f"First visit, with {entry.detail}"
        case Topic.VISIT:
            return f"Spent time with {entry.detail}"
        case Topic.PLAYED_WITH:
            game, result, friend = entry.detail.split("/", 2)
            return played_with_text(friend, GameKind(game), GameResult(result))
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
        f"Care mistakes {t.care_mistakes} · holidays {t.holidays} · visits {t.visits}",
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
