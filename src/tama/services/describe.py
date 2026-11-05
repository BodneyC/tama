"""Plain-text descriptions of the pet and its events.

Shared by the ``tama status`` command and the TUI (e.g. the "While you were away" summary),
so neither has to know the full event vocabulary.
"""

from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta, tzinfo
from enum import StrEnum

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
    HeirHatched,
    LaidEgg,
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
from tama.domain.lineage import founder
from tama.domain.minigames import GameKind, GameResult
from tama.domain.pet import Pet
from tama.domain.stage import DeathCause, LifeStage, Variant
from tama.domain.stats import Stat
from tama.domain.visit import VisitRefusal
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
MISTAKE_TEXT = {
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
DEATH_TEXT = {
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


def stage_phrase(stage: LifeStage, variant: Variant) -> str:
    """``a chubby adult``: the stage (and adult form) as a noun phrase."""
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
            return f"Grew into {stage_phrase(stage, variant)}"
        case Died(cause=cause):
            return DEATH_TEXT[cause]
        case LaidEgg():
            return "Left an egg"
        case HeirHatched(heir=heir):
            return f"Its egg hatched as {heir}"
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
            return MISTAKE_TEXT[reason]
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
        case Visited(friend=friend):
            return f"Spent time with {friend}"
        case PlayedWith(friend=friend, game=game, result=result):
            return played_with_text(friend, game, result)
        case Refused(action=action, reason=reason):
            return f"Refused {_REFUSED_ACTIONS[action]}: {reason.value.replace('_', ' ')}"
        case _:
            return type(event).__name__


GAME_NAMES = {
    GameKind.LEFT_RIGHT: "Left or Right",
    GameKind.FOUR_IN_A_ROW: "Four in a Row",
    GameKind.TIC_TAC_TOE: "Tic-Tac-Toe",
}
_PLAYED_WITH = {
    GameResult.WIN: "Beat {friend} at {game}",
    GameResult.DRAW: "Drew with {friend} at {game}",
    GameResult.LOSS: "Lost to {friend} at {game}",
}


def played_with_text(friend: str, game: GameKind, result: GameResult) -> str:
    """``Beat Pip at Four in a Row``: a game against another pet, from this pet's side."""
    return _PLAYED_WITH[result].format(friend=friend, game=GAME_NAMES[game])


FAMILY_SHOWN = 3
"""How many ancestors the family line shows before the pet; older ones become "…"."""


def lineage_text(pet: Pet) -> str | None:
    """``Generation 3 · founded by Mochi`` for an heir; ``None`` for a pet that began its line."""
    first = founder(pet)
    return None if first is None else f"Generation {pet.generation} · founded by {first}"


def family_line(pet: Pet) -> str | None:
    """``… → Bao → Mochi II → Mochi III``: its newest ancestors, then the pet (``None`` if none)."""
    if not pet.ancestors:
        return None
    names = [a.name for a in pet.ancestors] + [pet.name]
    shown = names[-(FAMILY_SHOWN + 1) :]
    return " → ".join((["…"] if len(names) > len(shown) else []) + shown)


_VISIT_REFUSALS = {
    VisitRefusal.EGG: "still an egg",
    VisitRefusal.DEAD: "no longer alive",
    VisitRefusal.ON_HOLIDAY: "on holiday",
    VisitRefusal.TOO_TIRED: "too tired",
}
_LEFT = {
    VisitRefusal.ASLEEP: "got sleepy",
    VisitRefusal.SICK: "felt poorly",
    VisitRefusal.MISBEHAVING: "threw a tantrum",
    VisitRefusal.TOO_TIRED: "was worn out",
    VisitRefusal.DEAD: "passed away",
    VisitRefusal.ON_HOLIDAY: "went on holiday",
}
_GONE = frozenset({VisitRefusal.DEAD, VisitRefusal.ON_HOLIDAY})


def visit_refusal_text(reason: VisitRefusal) -> str:
    """Why a pet can't visit, as shown greyed out in the visit picker (SPEC §3.2)."""
    return _VISIT_REFUSALS.get(reason, reason.value)


def visit_ended_text(*, host: str, guest: str, leaver: str, reason: VisitRefusal) -> str:
    """Why a visit ended by itself: ``Pip got sleepy and went home`` (SPEC §3.2).

    ``leaver`` is whichever pet could no longer carry on, the host or the guest.
    """
    what = _LEFT.get(reason, "had to stop")
    if leaver == host:
        return f"{host} {what}, so {guest} went home"
    return f"{guest} {what}" if reason in _GONE else f"{guest} {what} and went home"


def summarize(events: Iterable[Event]) -> list[str]:
    """Describe ``events``, merging repeats into ``"… ×n"`` lines in first-seen order."""
    counts = Counter(describe_event(event) for event in events)
    return [text if n == 1 else f"{text} ×{n}" for text, n in counts.items()]


def holiday_since(when: datetime, tz: tzinfo = UTC) -> str:
    """The day a holiday started, like ``3 Nov``, in the player's time zone."""
    local = when.astimezone(tz)
    return f"{local.day} {local:%b}"


class Tone(StrEnum):
    """How a part of the status line should look; the CLI picks the actual styling."""

    NAME = "name"
    PLAIN = "plain"
    GOOD = "good"  # a need at half or more
    FAIR = "fair"  # getting low, not yet calling for attention
    LOW = "low"  # below the attention threshold
    ALERT = "alert"  # what the pet needs
    AWAY = "away"  # on holiday
    GONE = "gone"  # passed away


type Segment = tuple[str, Tone]

_GOOD_AT = 50


def _need(label: str, value: int, balance: Balance) -> Segment:
    if value >= _GOOD_AT:
        tone = Tone.GOOD
    elif value >= balance.attention_threshold:
        tone = Tone.FAIR
    else:
        tone = Tone.LOW
    return f"{label} {value}", tone


def status_segments(pet: Pet, balance: Balance, tz: tzinfo = UTC) -> list[Segment]:
    """The status line in parts, each with how it should look (``status_line`` joins them)."""
    if pet.stage is LifeStage.DEAD:
        cause = str(pet.cause_of_death).replace("_", " ")
        parts = [pet.name, pet.species, f"passed away ({cause}) at {format_age(pet.age)}"]
        return [(part, Tone.GONE) for part in parts]
    if pet.stage is LifeStage.EGG:
        return [
            (pet.name, Tone.NAME),
            (f"{pet.species} egg", Tone.PLAIN),
            ("about to hatch", Tone.PLAIN),
        ]
    kind = (f"{pet.stage.value} {pet.species}", Tone.PLAIN)
    if pet.paused_since is not None:
        since = holiday_since(pet.paused_since, tz)
        return [(pet.name, Tone.NAME), kind, (f"on holiday since {since}", Tone.AWAY)]
    s = pet.stats
    segments: list[Segment] = [
        (pet.name, Tone.NAME),
        kind,
        (format_age(pet.age), Tone.PLAIN),
        _need("hunger", s.hunger, balance),
        _need("happy", s.happiness, balance),
        _need("energy", s.energy, balance),
        _need("clean", s.hygiene, balance),
        _need("health", s.health, balance),
    ]
    reasons = attention_reasons(pet, balance)
    if reasons:
        needs = ", ".join(r.value for r in AttentionReason if r in reasons)
        segments.append((f"needs: {needs}", Tone.ALERT))
    return segments


def status_line(pet: Pet, balance: Balance, tz: tzinfo = UTC) -> str:
    """One line describing the pet, suitable for a shell prompt."""
    return " · ".join(text for text, _ in status_segments(pet, balance, tz))
