"""Life-stage transitions, adult form selection and death."""

from dataclasses import replace

from tama.domain.balance import Balance
from tama.domain.events import Died, Event, Evolved
from tama.domain.pet import ZERO, Pet
from tama.domain.stage import DeathCause, LifeStage, Variant

_NEXT_STAGE: dict[LifeStage, LifeStage] = {
    LifeStage.EGG: LifeStage.BABY,
    LifeStage.BABY: LifeStage.CHILD,
    LifeStage.CHILD: LifeStage.TEEN,
    LifeStage.TEEN: LifeStage.ADULT,
    LifeStage.ADULT: LifeStage.ELDER,
}


def adult_variant(pet: Pet, balance: Balance) -> Variant:
    """Choose the adult form a teen grows into, based on how well it was cared for."""
    well_raised = (
        pet.care_mistakes <= balance.good_adult_max_care_mistakes
        and pet.stats.discipline >= balance.good_adult_min_discipline
    )
    return Variant.GOOD if well_raised else Variant.SCRUFFY


def die(pet: Pet, cause: DeathCause, events: list[Event]) -> Pet:
    """Return ``pet`` dead of ``cause``, recording a ``Died`` event."""
    events.append(Died(pet.age, cause))
    return replace(
        pet,
        stage=LifeStage.DEAD,
        cause_of_death=cause,
        is_asleep=False,
        misbehaving=False,
        woken_tantrum=False,
        stay_awake=ZERO,
    )


def progress(pet: Pet, balance: Balance, events: list[Event]) -> Pet:
    """Apply any stage change due at the pet's current age (evolving or dying of old age)."""
    if pet.stage is LifeStage.ELDER and pet.age >= pet.lifespan:
        return die(pet, DeathCause.OLD_AGE, events)
    next_stage = _NEXT_STAGE.get(pet.stage)
    if next_stage is None or pet.age < balance.stage_age(next_stage):
        return pet
    variant = adult_variant(pet, balance) if next_stage is LifeStage.ADULT else pet.variant
    events.append(Evolved(pet.age, pet.stage, next_stage, variant))
    return replace(pet, stage=next_stage, variant=variant)
