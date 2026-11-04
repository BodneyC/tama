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
_BANDED_STAGES = (LifeStage.BABY, LifeStage.CHILD, LifeStage.TEEN, LifeStage.ADULT, LifeStage.ELDER)


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
    # Waking the pet early (SPEC §2.4): it stays up a while, grumpy and more tired.
    wake_happiness: int = -20
    wake_energy: int = -20
    wake_stay_awake: timedelta = timedelta(minutes=30)

    # Misbehaviour (rolled once per simulated hour)
    misbehave_chance: float = 0.15
    misbehave_min_stage: LifeStage = LifeStage.CHILD
    # Long enough for a player checking in every half hour or so to catch most episodes
    # (tools/balance.py: 86% caught; 5 min caught only 24%, so good adults were rare).
    misbehave_ignore_grace: timedelta = timedelta(minutes=30)
    misbehave_ignored_discipline: int = -10

    # Attention
    attention_threshold: int = 25

    # Actions
    start_weight: int = 5
    min_weight: int = 1
    meal_hunger: int = 30
    meal_weight: int = 2  # tools/balance.py: at 1 g, won games kept every pet underweight
    # A meal when this full is eaten anyway, but the pet is stuffed (SPEC §3).
    stuffed_at_hunger: int = 95
    stuffed_weight: int = 2  # on top of meal_weight
    stuffed_happiness: int = -5
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

    # Weight (SPEC §2.7). Awake, the pet burns this share of its own weight per hour (scaled by
    # the stage multiplier), so its weight settles where what it eats meets what it burns.
    weight_burn: Fraction = Fraction(1, 64)
    # Healthy band (lowest, highest grams) per stage; it rises as the pet grows.
    baby_weight: tuple[int, int] = (4, 10)
    child_weight: tuple[int, int] = (4, 16)
    teen_weight: tuple[int, int] = (7, 24)
    adult_weight: tuple[int, int] = (12, 44)
    elder_weight: tuple[int, int] = (18, 50)
    overweight_sickness_chance: float = 0.05
    overweight_energy_multiplier: Fraction = Fraction(5, 4)
    weight_episode_grace: timedelta = 12 * HOUR

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
        for stage in _BANDED_STAGES:
            low, high = self.weight_band(stage)
            if not self.min_weight <= low <= high:
                raise InvalidArgumentError(
                    f"{stage.value} weight band must be min_weight <= low <= high, got {low}-{high}"
                )

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

    def weight_band(self, stage: LifeStage) -> tuple[int, int]:
        """Return the healthy weight range (lowest, highest grams) at ``stage``."""
        match stage:
            case LifeStage.BABY:
                return self.baby_weight
            case LifeStage.CHILD:
                return self.child_weight
            case LifeStage.TEEN:
                return self.teen_weight
            case LifeStage.ADULT:
                return self.adult_weight
            case LifeStage.ELDER:
                return self.elder_weight
            case _:  # eggs and dead pets
                raise InvalidArgumentError(f"a pet has no healthy weight as {stage.value}")

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
