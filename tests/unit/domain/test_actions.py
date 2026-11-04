from datetime import UTC, datetime, timedelta

import pytest

from tama.domain.actions import apply, apply_game_outcome, refusal
from tama.domain.balance import DEFAULT_BALANCE, Balance
from tama.domain.events import (
    Action,
    Ate,
    Cleaned,
    Disciplined,
    GotSick,
    LightsToggled,
    MedicineGiven,
    Played,
    RefusalReason,
    Refused,
    Woken,
)
from tama.domain.minigames import GameKind, GameResult
from tama.domain.pet import Timers
from tama.domain.stage import DeathCause, LifeStage
from tama.domain.stats import Stats
from tests.factories import make_ctx, make_pet

NIGHT = datetime(2026, 1, 1, 23, 0, tzinfo=UTC)


# --- Refusals -----------------------------------------------------------------------------


@pytest.mark.parametrize("action", list(Action))
def test_dead_pet_refuses_everything(action: Action) -> None:
    pet = make_pet(stage=LifeStage.DEAD, cause_of_death=DeathCause.OLD_AGE)

    out = apply(pet, action, make_ctx())

    assert out.pet == pet
    assert out.events == (Refused(pet.age, action, RefusalReason.DEAD),)
    assert out.refusal is RefusalReason.DEAD


@pytest.mark.parametrize(
    ("action", "refused"),
    [
        (Action.MEAL, True),
        (Action.SNACK, True),
        (Action.PLAY, True),
        (Action.DISCIPLINE, True),
        (Action.MEDICINE, True),
        (Action.WAKE, True),
        (Action.CLEAN, False),
        (Action.LIGHTS, False),
    ],
)
def test_egg_refusals(action: Action, refused: bool) -> None:
    egg = make_pet(stage=LifeStage.EGG)

    assert (refusal(egg, action, DEFAULT_BALANCE) is RefusalReason.EGG) is refused


@pytest.mark.parametrize(
    ("action", "refused"),
    [
        (Action.MEAL, True),
        (Action.SNACK, True),
        (Action.PLAY, True),
        (Action.DISCIPLINE, True),
        (Action.MEDICINE, True),
        (Action.WAKE, False),
        (Action.CLEAN, False),
        (Action.LIGHTS, False),
    ],
)
def test_asleep_refusals(action: Action, refused: bool) -> None:
    pet = make_pet(is_asleep=True, updated_at=NIGHT, sickness_doses=1)

    assert (refusal(pet, action, DEFAULT_BALANCE) is RefusalReason.ASLEEP) is refused


def test_accepted_action_has_no_refusal() -> None:
    assert apply(make_pet(), Action.CLEAN, make_ctx()).refusal is None


# --- Feeding ------------------------------------------------------------------------------


def test_meal_fills_hunger_and_adds_weight() -> None:
    pet = make_pet(stats=Stats(hunger=50))

    out = apply(pet, Action.MEAL, make_ctx())

    assert out.pet.stats.hunger == 80
    assert out.pet.weight == pet.weight + DEFAULT_BALANCE.meal_weight
    assert out.events == (Ate(pet.age, Action.MEAL),)


def test_a_full_pet_eats_a_meal_anyway_but_is_stuffed() -> None:
    b = DEFAULT_BALANCE
    pet = make_pet(stats=Stats(hunger=b.stuffed_at_hunger, happiness=50))

    out = apply(pet, Action.MEAL, make_ctx())

    assert out.pet.stats.hunger == 100
    assert out.pet.stats.happiness == 50 + b.stuffed_happiness
    assert out.pet.weight == pet.weight + b.meal_weight + b.stuffed_weight
    assert out.events == (Ate(pet.age, Action.MEAL, stuffed=True),)


def test_a_meal_just_below_full_is_an_ordinary_meal() -> None:
    pet = make_pet(stats=Stats(hunger=DEFAULT_BALANCE.stuffed_at_hunger - 1))

    out = apply(pet, Action.MEAL, make_ctx())

    assert out.events == (Ate(pet.age, Action.MEAL),)
    assert out.pet.weight == pet.weight + DEFAULT_BALANCE.meal_weight


def test_snack_cheers_up_and_adds_weight() -> None:
    pet = make_pet(stats=Stats(hunger=50, happiness=50))

    out = apply(pet, Action.SNACK, make_ctx())

    assert out.pet.stats.happiness == 65
    assert out.pet.stats.hunger == 55
    assert out.pet.weight == pet.weight + DEFAULT_BALANCE.snack_weight
    assert out.pet.recent_snacks == (pet.age,)
    assert out.events == (Ate(pet.age, Action.SNACK),)


def test_too_many_snacks_can_cause_sickness() -> None:
    pet = make_pet(recent_snacks=(timedelta(minutes=50),) * 3, age=timedelta(minutes=60))
    ctx = make_ctx(balance=Balance(snack_sickness_chance=1))

    out = apply(pet, Action.SNACK, ctx)

    assert out.pet.is_sick
    assert out.events[-1] == GotSick(pet.age, out.pet.sickness_doses)


def test_snack_sickness_is_a_chance_not_a_certainty() -> None:
    pet = make_pet(recent_snacks=(timedelta(minutes=50),) * 3, age=timedelta(minutes=60))
    ctx = make_ctx(balance=Balance(snack_sickness_chance=0))

    assert not apply(pet, Action.SNACK, ctx).pet.is_sick


def test_snacks_older_than_an_hour_are_forgotten() -> None:
    old = (timedelta(minutes=0),) * 3
    pet = make_pet(recent_snacks=old, age=timedelta(minutes=60))
    ctx = make_ctx(balance=Balance(snack_sickness_chance=1))

    out = apply(pet, Action.SNACK, ctx)

    assert not out.pet.is_sick
    assert out.pet.recent_snacks == (pet.age,)


def test_snacks_do_not_make_a_sick_pet_sicker() -> None:
    pet = make_pet(
        recent_snacks=(timedelta(minutes=50),) * 3, age=timedelta(minutes=60), sickness_doses=1
    )
    ctx = make_ctx(balance=Balance(snack_sickness_chance=1))

    out = apply(pet, Action.SNACK, ctx)

    assert out.pet.sickness_doses == 1
    assert not any(isinstance(e, GotSick) for e in out.events)


# --- Play ---------------------------------------------------------------------------------


def test_play_is_accepted_without_changing_the_pet() -> None:
    pet = make_pet()

    out = apply(pet, Action.PLAY, make_ctx())

    assert out.pet == pet
    assert out.events == ()


@pytest.mark.parametrize("action", [Action.MEAL, Action.SNACK, Action.PLAY])
def test_a_misbehaving_pet_refuses_food_and_play(action: Action) -> None:
    pet = make_pet(misbehaving=True, stats=Stats(hunger=10))

    out = apply(pet, action, make_ctx())

    assert out.refusal is RefusalReason.MISBEHAVING
    assert out.pet == pet


@pytest.mark.parametrize("action", [Action.CLEAN, Action.LIGHTS, Action.DISCIPLINE])
def test_a_misbehaving_pet_still_accepts_care_and_discipline(action: Action) -> None:
    pet = make_pet(misbehaving=True, poop_count=1)

    assert apply(pet, action, make_ctx()).refusal is None


def test_a_misbehaving_pet_still_takes_medicine() -> None:
    pet = make_pet(misbehaving=True, sickness_doses=1)

    assert apply(pet, Action.MEDICINE, make_ctx()).refusal is None


def test_play_refused_when_too_tired() -> None:
    pet = make_pet(stats=Stats(energy=9))

    assert apply(pet, Action.PLAY, make_ctx()).refusal is RefusalReason.TOO_TIRED


def test_winning_a_game() -> None:
    pet = make_pet(stats=Stats(happiness=50, energy=50), weight=10)

    out = apply_game_outcome(pet, GameResult.WIN, game=GameKind.LEFT_RIGHT, ctx=make_ctx())

    assert out.pet.stats.happiness == 70
    assert out.pet.stats.energy == 40
    assert out.pet.weight == 9
    assert out.events == (Played(pet.age, GameResult.WIN, GameKind.LEFT_RIGHT),)


def test_losing_a_game() -> None:
    pet = make_pet(stats=Stats(happiness=50, energy=50), weight=10)

    out = apply_game_outcome(pet, GameResult.LOSS, game=GameKind.LEFT_RIGHT, ctx=make_ctx())

    assert out.pet.stats.happiness == 55
    assert out.pet.stats.energy == 40
    assert out.pet.weight == 10
    assert out.events == (Played(pet.age, GameResult.LOSS, GameKind.LEFT_RIGHT),)


def test_drawing_a_game() -> None:
    pet = make_pet(stats=Stats(happiness=50, energy=50), weight=10)

    out = apply_game_outcome(pet, GameResult.DRAW, game=GameKind.LEFT_RIGHT, ctx=make_ctx())

    assert out.pet.stats.happiness == 60
    assert out.pet.stats.energy == 40
    assert out.pet.weight == 10
    assert out.events == (Played(pet.age, GameResult.DRAW, GameKind.LEFT_RIGHT),)


def test_weight_never_drops_below_minimum() -> None:
    pet = make_pet(weight=1)

    assert (
        apply_game_outcome(pet, GameResult.WIN, game=GameKind.LEFT_RIGHT, ctx=make_ctx()).pet.weight
        == 1
    )


def test_game_outcome_refused_for_dead_pet() -> None:
    pet = make_pet(stage=LifeStage.DEAD, cause_of_death=DeathCause.POOR_HEALTH)

    out = apply_game_outcome(pet, GameResult.WIN, game=GameKind.LEFT_RIGHT, ctx=make_ctx())

    assert out.pet == pet
    assert out.refusal is RefusalReason.DEAD


# --- Care ---------------------------------------------------------------------------------


def test_clean_removes_poop_and_restores_hygiene() -> None:
    pet = make_pet(poop_count=3, stats=Stats(hygiene=20))

    out = apply(pet, Action.CLEAN, make_ctx())

    assert out.pet.poop_count == 0
    assert out.pet.stats.hygiene == 100
    assert out.events == (Cleaned(pet.age, poops_removed=3),)


def test_medicine_refused_when_not_sick() -> None:
    assert apply(make_pet(), Action.MEDICINE, make_ctx()).refusal is RefusalReason.NOT_SICK


@pytest.mark.parametrize(("doses", "cured"), [(2, False), (1, True)])
def test_medicine_uses_up_one_dose(doses: int, cured: bool) -> None:
    pet = make_pet(sickness_doses=doses)

    out = apply(pet, Action.MEDICINE, make_ctx())

    assert out.pet.sickness_doses == doses - 1
    assert out.pet.is_sick is not cured
    assert out.events == (MedicineGiven(pet.age, cured=cured),)


@pytest.mark.parametrize("lights_on", [True, False])
def test_lights_toggle(lights_on: bool) -> None:
    pet = make_pet(lights_on=lights_on)

    out = apply(pet, Action.LIGHTS, make_ctx())

    assert out.pet.lights_on is not lights_on
    assert out.events == (LightsToggled(pet.age, on=not lights_on),)


def test_disciplining_misbehaviour_raises_discipline() -> None:
    pet = make_pet(
        misbehaving=True,
        stats=Stats(discipline=10),
        timers=Timers(misbehaving=timedelta(minutes=2)),
    )

    out = apply(pet, Action.DISCIPLINE, make_ctx())

    assert not out.pet.misbehaving
    assert out.pet.stats.discipline == 35
    assert out.pet.timers.misbehaving == timedelta(0)
    assert out.events == (Disciplined(pet.age, effective=True),)


def test_unwarranted_discipline_upsets_the_pet() -> None:
    pet = make_pet(stats=Stats(happiness=50, discipline=10))

    out = apply(pet, Action.DISCIPLINE, make_ctx())

    assert out.pet.stats.happiness == 30
    assert out.pet.stats.discipline == 10
    assert out.events == (Disciplined(pet.age, effective=False),)


def test_disciplining_a_woken_tantrum_earns_nothing() -> None:
    pet = make_pet(misbehaving=True, woken_tantrum=True, stats=Stats(discipline=10))

    out = apply(pet, Action.DISCIPLINE, make_ctx())

    assert not out.pet.misbehaving
    assert not out.pet.woken_tantrum
    assert out.pet.stats.discipline == 10
    assert out.events == (Disciplined(pet.age, effective=True),)


# --- Waking -------------------------------------------------------------------------------


def test_wake_refused_when_already_awake() -> None:
    pet = make_pet()

    out = apply(pet, Action.WAKE, make_ctx())

    assert out.pet == pet
    assert out.refusal is RefusalReason.AWAKE


def test_waking_upsets_tires_and_starts_a_tantrum() -> None:
    pet = make_pet(
        is_asleep=True,
        lights_on=False,
        updated_at=NIGHT,
        stats=Stats(happiness=60, energy=50),
        timers=Timers(lights_on_asleep=timedelta(minutes=3)),
    )

    out = apply(pet, Action.WAKE, make_ctx())

    assert not out.pet.is_asleep
    assert out.pet.stats.happiness == 40
    assert out.pet.stats.energy == 30
    assert out.pet.misbehaving
    assert out.pet.woken_tantrum
    assert out.pet.timers.misbehaving == timedelta(0)
    assert out.pet.stay_awake == DEFAULT_BALANCE.wake_stay_awake
    assert out.events == (Woken(pet.age),)


def test_waking_mid_tantrum_keeps_the_tantrum_it_had() -> None:
    timers = Timers(misbehaving=timedelta(minutes=12))
    pet = make_pet(is_asleep=True, updated_at=NIGHT, misbehaving=True, timers=timers)

    out = apply(pet, Action.WAKE, make_ctx())

    assert out.pet.misbehaving
    assert not out.pet.woken_tantrum  # a real tantrum still earns discipline
    assert out.pet.timers == timers


def test_a_woken_pet_takes_medicine() -> None:
    pet = make_pet(is_asleep=True, updated_at=NIGHT, sickness_doses=1)

    woken = apply(pet, Action.WAKE, make_ctx()).pet
    out = apply(woken, Action.MEDICINE, make_ctx())

    assert not out.pet.is_sick
    assert out.events == (MedicineGiven(pet.age, cured=True),)
