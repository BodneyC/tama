"""Every tunable number in the game, in one place.

Balancing the game should only ever mean changing values here (or passing a modified
``Balance``), never touching simulation logic. Rates are expressed as "one point per
``timedelta``" to match how the spec describes them.
"""

from dataclasses import dataclass
from datetime import time, timedelta
from fractions import Fraction

from tama.domain.stage import LifeStage
from tama.errors import InvalidArgumentError

HOUR = timedelta(hours=1)


@dataclass(frozen=True, slots=True)
class Balance:
    """Tunable game constants. See docs/SPEC.md §2-§3 for what each one means."""

    # Simulation granularity. Must divide an hour so hourly rolls land on step boundaries.
    step: timedelta = timedelta(minutes=1)

    # Life stages
    hatch_age: timedelta = timedelta(minutes=1)
    child_age: timedelta = HOUR
    teen_age: timedelta = timedelta(days=1)
    adult_age: timedelta = timedelta(days=3)
    elder_age: timedelta = timedelta(days=10)
    lifespan_min: timedelta = timedelta(days=14)
    lifespan_max: timedelta = timedelta(days=18)
    baby_decay_multiplier: Fraction = Fraction(3, 2)
    elder_decay_multiplier: Fraction = Fraction(3, 4)
    good_adult_max_care_mistakes: int = 3
    good_adult_min_discipline: int = 50

    # Natural drift: one point per period. Asleep drift ignores stage multipliers.
    hunger_awake: timedelta = timedelta(minutes=5)
    hunger_asleep: timedelta = timedelta(minutes=10)
    happiness_awake: timedelta = timedelta(minutes=6)
    happiness_asleep: timedelta = timedelta(minutes=12)
    energy_awake: timedelta = timedelta(minutes=5)
    energy_asleep_regen: timedelta = timedelta(minutes=1)
    hygiene_awake: timedelta = timedelta(minutes=6)
    hygiene_asleep: timedelta = timedelta(minutes=15)
    hygiene_per_poop: timedelta = timedelta(minutes=4)  # i.e. -15/hour for each uncleaned poop
    sick_happiness_multiplier: Fraction = Fraction(3, 2)
    # Gentle enough that a sickness or neglect that starts after bedtime is survivable by
    # morning (tools/balance.py: players who check in every 2 h or more see old age).
    sick_health: timedelta = timedelta(minutes=10)
    neglect_health: timedelta = timedelta(minutes=8)
    health_regen: timedelta = timedelta(minutes=10)

    # Poop
    poop_interval: timedelta = 2 * HOUR
    max_poops: int = 4

    # Sickness (rolled once per simulated hour)
    sickness_base_chance: float = 0.01
    sickness_per_poop_chance: float = 0.05
    sickness_dirty_chance: float = 0.10
    sickness_hungry_chance: float = 0.10
    sickness_risk_threshold: int = 20
    sickness_min_doses: int = 1
    sickness_max_doses: int = 2

    # Care mistakes
    neglect_grace: timedelta = timedelta(minutes=15)
    lights_on_asleep_grace: timedelta = timedelta(minutes=30)

    # Sleep (night is in the player's local time zone)
    sleepy_energy: int = 20
    night_start: time = time(22)
    night_end: time = time(7)

    # Misbehaviour (rolled once per simulated hour)
    misbehave_chance: float = 0.15
    misbehave_min_stage: LifeStage = LifeStage.CHILD
    misbehave_ignore_grace: timedelta = timedelta(minutes=5)
    misbehave_ignored_discipline: int = -10

    # Attention
    attention_threshold: int = 25

    # Actions
    start_weight: int = 5
    min_weight: int = 1
    meal_hunger: int = 30
    meal_weight: int = 1
    meal_refuse_at_hunger: int = 95
    snack_happiness: int = 15
    snack_hunger: int = 5
    snack_weight: int = 2
    snack_limit_per_hour: int = 3
    snack_sickness_chance: float = 0.5
    play_min_energy: int = 10
    play_energy: int = -10
    play_win_happiness: int = 20
    play_draw_happiness: int = 10
    play_lose_happiness: int = 5
    play_win_weight: int = -1
    discipline_gain: int = 25

    # The pet as a board-game opponent: the chance it plays a random move instead of a good one
    baby_mistake_chance: float = 0.6
    child_mistake_chance: float = 0.4
    teen_mistake_chance: float = 0.25
    adult_mistake_chance: float = 0.15
    elder_mistake_chance: float = 0.2  # a little rusty
    discipline_unwarranted_happiness: int = -20

    def __post_init__(self) -> None:
        """Validate constraints the simulation relies on."""
        if self.step <= timedelta(0) or HOUR % self.step:
            raise InvalidArgumentError(f"step must be positive and divide an hour, got {self.step}")

    def stage_age(self, stage: LifeStage) -> timedelta:
        """Return the age at which the pet enters ``stage``."""
        match stage:
            case LifeStage.EGG:
                return timedelta(0)
            case LifeStage.BABY:
                return self.hatch_age
            case LifeStage.CHILD:
                return self.child_age
            case LifeStage.TEEN:
                return self.teen_age
            case LifeStage.ADULT:
                return self.adult_age
            case LifeStage.ELDER:
                return self.elder_age
            case _:  # LifeStage.DEAD
                raise InvalidArgumentError("dead is not entered at a fixed age")

    def decay_multiplier(self, stage: LifeStage) -> Fraction:
        """Return how much faster (>1) or slower (<1) awake needs decay at ``stage``."""
        if stage is LifeStage.BABY:
            return self.baby_decay_multiplier
        if stage is LifeStage.ELDER:
            return self.elder_decay_multiplier
        return Fraction(1)

    def opponent_mistake_chance(self, stage: LifeStage) -> float:
        """Return how often a pet at ``stage`` plays a random move in a board game."""
        match stage:
            case LifeStage.BABY:
                return self.baby_mistake_chance
            case LifeStage.CHILD:
                return self.child_mistake_chance
            case LifeStage.TEEN:
                return self.teen_mistake_chance
            case LifeStage.ADULT:
                return self.adult_mistake_chance
            case LifeStage.ELDER:
                return self.elder_mistake_chance
            case _:  # eggs and dead pets
                raise InvalidArgumentError(f"a pet can't play board games as {stage.value}")


DEFAULT_BALANCE = Balance()
