"""A pet's journal: its life story and lifetime tallies, written from events (SPEC §2.9).

``record`` is the only way to write to it, and it only reads domain events, so the journal
covers offline catch-up as well as live play and inherits the simulation's tick-splitting
equivalence (ADR 0009). Entries are structured (a topic plus a short detail); turning them into
sentences is the presentation layer's job.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Self

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
    MedicineGiven,
    Misbehaved,
    MisbehaviourIgnored,
    PausedForHoliday,
    Played,
    ResumedFromHoliday,
)
from tama.domain.minigames import GameKind, GameResult
from tama.domain.pet import Pet
from tama.domain.stage import LifeStage

MAX_MOMENTS = 100
"""Moments beyond this many are forgotten, oldest first; life entries and firsts are kept."""
MILESTONES = (10, 50, 100, 250, 500, 1000)
"""Round numbers of meals eaten and games won worth a moment."""
_MINUTE = timedelta(minutes=1)


class EntryKind(StrEnum):
    """How notable an entry is, which decides whether it is ever forgotten."""

    LIFE = "life"
    FIRST = "first"
    MOMENT = "moment"


class Topic(StrEnum):
    """What an entry is about. ``Entry.detail`` says more for some topics (see each)."""

    JOURNAL_STARTED = "journal_started"
    HATCHED = "hatched"  # whose egg it was, for an heir
    EVOLVED = "evolved"  # "<stage>/<variant>"
    DIED = "died"  # the cause
    HOLIDAY = "holiday"
    BACK = "back_from_holiday"  # whole minutes away
    LAID_EGG = "laid_egg"
    HEIR_HATCHED = "heir_hatched"  # the heir's name
    MEAL = "meal"
    SNACK = "snack"
    TANTRUM = "tantrum"
    SICKNESS = "sickness"
    WIN = "win"  # the game
    CARE_MISTAKE = "care_mistake"  # the reason
    CURED = "cured"
    TANTRUM_CAUGHT = "tantrum_caught"
    TANTRUM_IGNORED = "tantrum_ignored"
    MILESTONE = "milestone"  # "<tally>:<count>", e.g. "meals:50"


@dataclass(frozen=True, slots=True)
class Entry:
    """One line of the journal: what happened, when (wall clock and pet age)."""

    kind: EntryKind
    topic: Topic
    at: datetime
    age: timedelta
    detail: str = ""


@dataclass(frozen=True, slots=True)
class GameTally:
    """Results of one game over a whole life, from the player's side."""

    won: int = 0
    drawn: int = 0
    lost: int = 0

    def add(self, result: GameResult) -> Self:
        """Count one more ``result``."""
        match result:
            case GameResult.WIN:
                return replace(self, won=self.won + 1)
            case GameResult.DRAW:
                return replace(self, drawn=self.drawn + 1)
            case _:
                return replace(self, lost=self.lost + 1)


@dataclass(frozen=True, slots=True)
class Tallies:
    """Lifetime counts. ``games`` holds one tally per game played, in ``GameKind`` order."""

    meals: int = 0
    snacks: int = 0
    tantrums_caught: int = 0
    tantrums_ignored: int = 0
    sicknesses: int = 0
    doses: int = 0
    poops_cleaned: int = 0
    holidays: int = 0
    care_mistakes: int = 0
    games: tuple[tuple[GameKind, GameTally], ...] = ()

    def game(self, kind: GameKind) -> GameTally:
        """The tally for ``kind`` (all zero if never played)."""
        return dict(self.games).get(kind, GameTally())

    @property
    def games_won(self) -> int:
        """Games won, over every game."""
        return sum(tally.won for _, tally in self.games)

    def with_game(self, kind: GameKind, result: GameResult) -> Self:
        """Count one more ``result`` of ``kind``."""
        games = dict(self.games) | {kind: self.game(kind).add(result)}
        return replace(self, games=tuple((k, games[k]) for k in GameKind if k in games))


@dataclass(frozen=True, slots=True)
class Journal:
    """Entries in the order they happened, and the lifetime tallies."""

    entries: tuple[Entry, ...] = ()
    tallies: Tallies = field(default_factory=Tallies)

    def has_first(self, topic: Topic, detail: str = "") -> bool:
        """Whether the first time for ``topic`` (and ``detail``) has been written."""
        return any(
            e.kind is EntryKind.FIRST and e.topic is topic and e.detail == detail
            for e in self.entries
        )


def record(journal: Journal, events: Iterable[Event], before: Pet) -> Journal:
    """Write ``events`` into ``journal``.

    Args:
        journal: The journal so far.
        events: What a domain call returned, in order.
        before: The pet as it was *before* that call. Its last simulated step is the time line
            the events' ages are measured along, so each entry gets its wall-clock time.

    Returns:
        The updated journal (``journal`` itself if nothing was worth writing or counting).
    """
    start = before.updated_at - before.carry
    writer = _Writer(journal, before, lambda age: start + (age - before.age))
    for event in events:
        writer.write(event)
    return writer.journal


class _Writer:
    """Applies events to a journal one by one (keeps ``record`` readable)."""

    def __init__(
        self, journal: Journal, before: Pet, when: Callable[[timedelta], datetime]
    ) -> None:
        self.journal = journal
        self._before = before
        self._when = when

    def write(self, event: Event) -> None:
        if not self._life(event):
            self._care(event)

    def _life(self, event: Event) -> bool:
        """Write a life event; ``False`` if ``event`` isn't one."""
        t = self.journal.tallies
        match event:
            case Evolved(from_stage=LifeStage.EGG):
                parent = self._before.ancestors[-1].name if self._before.ancestors else ""
                self._add(EntryKind.LIFE, Topic.HATCHED, event, parent)
            case Evolved(to_stage=stage, variant=variant):
                self._add(EntryKind.LIFE, Topic.EVOLVED, event, f"{stage}/{variant}")
            case Died(cause=cause):
                self._add(EntryKind.LIFE, Topic.DIED, event, cause.value)
            case PausedForHoliday():
                self._count(replace(t, holidays=t.holidays + 1))
                self._add(EntryKind.LIFE, Topic.HOLIDAY, event)
            case ResumedFromHoliday(length=length):
                self._add(EntryKind.LIFE, Topic.BACK, event, str(length // _MINUTE))
            case LaidEgg():
                self._add(EntryKind.LIFE, Topic.LAID_EGG, event)
            case HeirHatched(heir=heir):
                self._add(EntryKind.LIFE, Topic.HEIR_HATCHED, event, heir)
            case _:
                return False
        return True

    def _care(self, event: Event) -> None:  # noqa: PLR0912 - one arm per event type
        t = self.journal.tallies
        match event:
            case Ate(food=Action.SNACK):
                self._count(replace(t, snacks=t.snacks + 1))
                self._first(Topic.SNACK, event)
            case Ate():
                self._count(replace(t, meals=t.meals + 1))
                self._first(Topic.MEAL, event)
                self._milestone("meals", t.meals + 1, event)
            case Played(result=result, game=game):
                self._count(t.with_game(game, result))
                if result is GameResult.WIN:
                    self._first(Topic.WIN, event, game.value)
                    self._milestone("games_won", t.games_won + 1, event)
            case Misbehaved():
                self._first(Topic.TANTRUM, event)
            case Disciplined(effective=True):
                self._count(replace(t, tantrums_caught=t.tantrums_caught + 1))
                self._add(EntryKind.MOMENT, Topic.TANTRUM_CAUGHT, event)
            case MisbehaviourIgnored():
                self._count(replace(t, tantrums_ignored=t.tantrums_ignored + 1))
                self._add(EntryKind.MOMENT, Topic.TANTRUM_IGNORED, event)
            case GotSick():
                self._count(replace(t, sicknesses=t.sicknesses + 1))
                self._first(Topic.SICKNESS, event)
            case MedicineGiven(cured=cured):
                self._count(replace(t, doses=t.doses + 1))
                if cured:
                    self._add(EntryKind.MOMENT, Topic.CURED, event)
            case Cleaned(poops_removed=poops) if poops:
                self._count(replace(t, poops_cleaned=t.poops_cleaned + poops))
            case CareMistake(reason=reason):
                self._count(replace(t, care_mistakes=t.care_mistakes + 1))
                first = t.care_mistakes == 0
                kind = EntryKind.FIRST if first else EntryKind.MOMENT
                self._add(kind, Topic.CARE_MISTAKE, event, reason.value)
            case _:
                pass

    def _count(self, tallies: Tallies) -> None:
        self.journal = replace(self.journal, tallies=tallies)

    def _first(self, topic: Topic, event: Event, detail: str = "") -> None:
        if not self.journal.has_first(topic, detail):
            self._add(EntryKind.FIRST, topic, event, detail)

    def _milestone(self, tally: str, count: int, event: Event) -> None:
        if count in MILESTONES:
            self._add(EntryKind.MOMENT, Topic.MILESTONE, event, f"{tally}:{count}")

    def _add(self, kind: EntryKind, topic: Topic, event: Event, detail: str = "") -> None:
        entries = (
            *self.journal.entries,
            Entry(kind, topic, self._when(event.age), event.age, detail),
        )
        if sum(e.kind is EntryKind.MOMENT for e in entries) > MAX_MOMENTS:
            oldest = next(i for i, e in enumerate(entries) if e.kind is EntryKind.MOMENT)
            entries = entries[:oldest] + entries[oldest + 1 :]
        self.journal = replace(self.journal, entries=entries)
