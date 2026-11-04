"""Generations: the egg a pet leaves when it dies of old age, and its heir (SPEC §2.8).

See ADR 0010. The egg is a flag on the dead parent; hatching it makes an ordinary new pet that
carries the family line (copied ancestor records) and, from a good parent, a little discipline.
"""

import re
from dataclasses import replace
from datetime import datetime
from random import Random

from tama.domain.balance import Balance
from tama.domain.events import HeirHatched, Outcome
from tama.domain.pet import MAX_NAME_LENGTH, AncestorRecord, Pet, new_egg, validate_name
from tama.domain.stage import Variant
from tama.domain.stats import Stat
from tama.errors import NoEggError

_NUMERAL = re.compile(r"^(?P<base>.+) (?P<numeral>[IVXLCDM]+)$")
_ROMAN = (
    (1000, "M"),
    (900, "CM"),
    (500, "D"),
    (400, "CD"),
    (100, "C"),
    (90, "XC"),
    (50, "L"),
    (40, "XL"),
    (10, "X"),
    (9, "IX"),
    (5, "V"),
    (4, "IV"),
    (1, "I"),
)


def to_roman(n: int) -> str:
    """``n`` (1 or more) as a Roman numeral."""
    out = []
    for value, letters in _ROMAN:
        count, n = divmod(n, value)
        out.append(letters * count)
    return "".join(out)


def from_roman(numeral: str) -> int | None:
    """The value of a properly written Roman numeral, else ``None`` (``IIII``, ``VX``...)."""
    total, rest = 0, numeral
    for value, letters in _ROMAN:
        while rest.startswith(letters):
            total, rest = total + value, rest[len(letters) :]
    return total if not rest and total and to_roman(total) == numeral else None


def heir_name(name: str) -> str | None:
    """The next name in the line: Mochi → Mochi II → Mochi III; ``None`` if it wouldn't fit."""
    base, number = name, 1
    match = _NUMERAL.match(name)
    if match is not None:
        value = from_roman(match["numeral"])
        if value is not None:
            base, number = match["base"], value
    heir = f"{base} {to_roman(number + 1)}"
    return heir if len(heir) <= MAX_NAME_LENGTH else None


def founder(pet: Pet) -> str | None:
    """The name of the first pet in ``pet``'s line, or ``None`` if it started the line."""
    return pet.ancestors[0].name if pet.ancestors else None


def hatch_heir(
    parent: Pet, name: str, now: datetime, rng: Random, balance: Balance
) -> tuple[Pet, Outcome]:
    """Hatch the egg ``parent`` left: a new pet called ``name``, and the parent's outcome.

    Args:
        parent: A pet that died of old age and whose egg is still waiting.
        name: The heir's name.
        now: When it hatches (the new egg's birth).
        rng: The heir's own RNG (its lifespan is drawn from it).
        balance: Game constants.

    Returns:
        The heir, and the parent with its egg marked hatched plus a ``HeirHatched`` event.

    Raises:
        NoEggError: If ``parent`` has no egg waiting.
        InvalidArgumentError: If ``name`` is not a valid name.
    """
    if not parent.egg_waiting:
        raise NoEggError(f"{parent.name} has no egg to hatch")
    record = AncestorRecord(
        parent.name, parent.born_at, parent.generation, parent.variant, parent.age
    )
    egg = new_egg(validate_name(name), now, rng, balance, species=parent.species)
    discipline = balance.heir_discipline if parent.variant is Variant.GOOD else 0
    heir = replace(
        egg,
        generation=parent.generation + 1,
        ancestors=(*parent.ancestors, record),
        stats=egg.stats.with_value(Stat.DISCIPLINE, discipline),
    )
    hatched = replace(parent, heir_hatched=True)
    return heir, Outcome(hatched, (HeirHatched(parent.age, heir.name),))
