"""Tricks a disciplined pet knows and shows off (SPEC §2.10).

Known tricks are derived from the pet's discipline and stage, never stored, so a pet that loses
discipline to ignored tantrums forgets a trick until it climbs back. They are for show only.
"""

from tama.domain.balance import Balance
from tama.domain.events import LearnedTrick
from tama.domain.pet import Pet
from tama.domain.stage import Trick


def known_tricks(pet: Pet, balance: Balance) -> tuple[Trick, ...]:
    """The tricks ``pet`` knows now, in ``Balance.trick_thresholds`` order."""
    if not pet.is_alive or pet.stage.order < balance.trick_min_stage.order:
        return ()
    discipline = pet.stats.discipline
    return tuple(trick for trick, needed in balance.trick_thresholds if discipline >= needed)


def learned_tricks(before: Pet, after: Pet, balance: Balance) -> tuple[LearnedTrick, ...]:
    """A ``LearnedTrick`` for each trick ``after`` knows that ``before`` didn't."""
    old = set(known_tricks(before, balance))
    return tuple(
        LearnedTrick(after.age, trick) for trick in known_tricks(after, balance) if trick not in old
    )


def can_show_off(pet: Pet, balance: Balance) -> bool:
    """Whether an idle ``pet`` is in the mood to perform one of its tricks now and then.

    It must be awake, content, well, behaving, in the light and know at least one trick.
    """
    return (
        not pet.is_asleep
        and not pet.on_holiday
        and not pet.is_sick
        and not pet.misbehaving
        and pet.lights_on
        and pet.stats.happiness >= balance.show_off_happiness
        and bool(known_tricks(pet, balance))
    )
