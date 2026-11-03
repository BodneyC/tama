"""Plain-text descriptions of the pet and its events.

Shared by the ``tama status`` command and the TUI (e.g. the "While you were away" summary),
so neither has to know the full event vocabulary.
"""

from collections import Counter
from collections.abc import Iterable
from datetime import timedelta

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
    Played,
    Pooped,
    Refused,
    WokeUp,
)
from tama.domain.pet import Pet
from tama.domain.stage import DeathCause, LifeStage, Variant
from tama.domain.stats import Stat

_NEED_LOW = {Stat.HUNGER: "Got hungry", Stat.HAPPINESS: "Got unhappy", Stat.HYGIENE: "Got dirty"}
_MISTAKES = {
    MistakeReason.HUNGER: "Was left starving",
    MistakeReason.HAPPINESS: "Was left miserable",
    MistakeReason.HYGIENE: "Was left filthy",
    MistakeReason.LIGHTS: "Slept with the lights on",
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
        return "a well-behaved adult" if variant is Variant.GOOD else "a scruffy adult"
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
        case Ate(food=food):
            return f"Ate a {food.value}"
        case Played(won=won):
            return "Won a game" if won else "Lost a game"
        case Cleaned():
            return "Was cleaned up"
        case MedicineGiven(cured=cured):
            return "Was cured" if cured else "Took some medicine"
        case LightsToggled(on=on):
            return "Lights on" if on else "Lights off"
        case Disciplined(effective=effective):
            return "Was disciplined" if effective else "Was scolded for nothing"
        case Refused(action=action, reason=reason):
            return f"Refused {_REFUSED_ACTIONS[action]}: {reason.value.replace('_', ' ')}"
        case _:
            return type(event).__name__


def summarize(events: Iterable[Event]) -> list[str]:
    """Describe ``events``, merging repeats into ``"… ×n"`` lines in first-seen order."""
    counts = Counter(describe_event(event) for event in events)
    return [text if n == 1 else f"{text} ×{n}" for text, n in counts.items()]


def status_line(pet: Pet, balance: Balance) -> str:
    """One line describing the pet, suitable for a shell prompt."""
    if pet.stage is LifeStage.DEAD:
        cause = str(pet.cause_of_death).replace("_", " ")
        return f"{pet.name} · {pet.species} · passed away ({cause}) at {format_age(pet.age)}"
    if pet.stage is LifeStage.EGG:
        return f"{pet.name} · {pet.species} egg · about to hatch"
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
