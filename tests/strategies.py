"""Hypothesis strategies for domain objects."""

from dataclasses import replace
from datetime import timedelta
from fractions import Fraction
from random import Random
from typing import Any

from hypothesis import strategies as st

from tama.domain.events import Action
from tama.domain.journal import Entry, EntryKind, GameTally, Journal, Tallies, Topic
from tama.domain.minigames import GameKind
from tama.domain.pet import AncestorRecord, Drift, Pet, Timers
from tama.domain.stage import DeathCause, LifeStage, Variant
from tama.domain.stats import Stats
from tests.factories import FIXED_NOW, make_pet

STAT = st.integers(min_value=0, max_value=100)
PENDING = st.fractions(min_value=Fraction(-59, 60), max_value=Fraction(59, 60), max_denominator=60)


def minutes(max_minutes: int) -> st.SearchStrategy[timedelta]:
    """Whole-minute durations (the default simulation step) up to ``max_minutes``."""
    return st.integers(min_value=0, max_value=max_minutes).map(lambda m: timedelta(minutes=m))


def durations(max_value: timedelta) -> st.SearchStrategy[timedelta]:
    """Arbitrary non-negative durations, including sub-step ones."""
    return st.timedeltas(min_value=timedelta(0), max_value=max_value)


stats_strategy = st.builds(
    Stats, hunger=STAT, happiness=STAT, energy=STAT, hygiene=STAT, health=STAT, discipline=STAT
)
drift_strategy = st.builds(
    Drift, hunger=PENDING, happiness=PENDING, energy=PENDING, hygiene=PENDING, health=PENDING
)
timers_strategy = st.builds(
    Timers,
    hunger=minutes(60),
    happiness=minutes(60),
    hygiene=minutes(60),
    lights_on_asleep=minutes(60),
    misbehaving=minutes(10),
    weight=minutes(24 * 60),
)


@st.composite
def pets(draw: st.DrawFn, *, alive: bool | None = None) -> Pet:
    """Arbitrary valid pets in any stage, awake or asleep, at any time of day."""
    dead = draw(st.booleans()) if alive is None else not alive
    stage = LifeStage.DEAD if dead else draw(st.sampled_from(list(LifeStage)[:-1]))
    age = draw(minutes(20 * 24 * 60))
    ancestors = tuple(
        draw(
            st.lists(
                st.builds(
                    AncestorRecord,
                    name=st.sampled_from(["Mochi", "Mochi II", "Bao"]),
                    born_at=minutes(60 * 24 * 30).map(lambda m: FIXED_NOW - m),
                    generation=st.integers(min_value=1, max_value=50),
                    variant=st.sampled_from(list(Variant)),
                    lifespan=minutes(20 * 24 * 60),
                ),
                max_size=3,
            )
        )
    )
    return replace(
        make_pet(stage=stage),
        age=age,
        lifespan=timedelta(days=draw(st.integers(min_value=14, max_value=18))),
        species=draw(st.sampled_from(["tama", "owl", "polar-bear"])),
        updated_at=FIXED_NOW + draw(minutes(24 * 60)),
        carry=timedelta(seconds=draw(st.integers(min_value=0, max_value=59))),
        stats=draw(stats_strategy),
        drift=draw(drift_strategy),
        timers=draw(timers_strategy),
        weight=draw(st.integers(min_value=1, max_value=200)),
        poop_count=draw(st.integers(min_value=0, max_value=4)),
        poop_progress=draw(
            st.fractions(min_value=0, max_value=Fraction(119, 120), max_denominator=120)
        ),
        weight_progress=draw(
            st.fractions(min_value=0, max_value=Fraction(63, 64), max_denominator=64 * 60)
        ),
        sickness_doses=draw(st.integers(min_value=0, max_value=2)),
        is_asleep=draw(st.booleans()),
        lights_on=draw(st.booleans()),
        misbehaving=draw(st.booleans()),
        woken_tantrum=draw(st.booleans()),
        stay_awake=draw(minutes(30)),
        care_mistakes=draw(st.integers(min_value=0, max_value=10)),
        recent_snacks=tuple(draw(st.lists(minutes(age // timedelta(minutes=1)), max_size=4))),
        cause_of_death=draw(st.sampled_from(list(DeathCause))) if dead else None,
        paused_since=draw(st.none() | st.just(FIXED_NOW)),
        generation=len(ancestors) + 1,
        ancestors=ancestors,
        heir_hatched=dead and draw(st.booleans()),
    )


actions = st.sampled_from(list(Action))


@st.composite
def rng_states(draw: st.DrawFn) -> tuple[Any, ...]:
    """States of a ``random.Random`` part-way through a sequence, sometimes mid-``gauss``."""
    rng = Random(draw(st.integers()))
    for _ in range(draw(st.integers(min_value=0, max_value=5))):
        rng.random()
    if draw(st.booleans()):
        rng.gauss()  # leaves a cached value in the state's gauss_next slot
    return rng.getstate()


COUNT = st.integers(min_value=0, max_value=10_000)


@st.composite
def journals(draw: st.DrawFn) -> Journal:
    """Arbitrary journals: any entries (in order) and any tallies."""
    entries = draw(
        st.lists(
            st.builds(
                Entry,
                kind=st.sampled_from(list(EntryKind)),
                topic=st.sampled_from(list(Topic)),
                at=st.just(FIXED_NOW) | minutes(60 * 24).map(lambda m: FIXED_NOW + m),
                age=minutes(20 * 24 * 60),
                detail=st.text(max_size=20),
            ),
            max_size=6,
        )
    )
    games = draw(st.lists(st.sampled_from(list(GameKind)), unique=True))
    tallies = Tallies(
        **{name: draw(COUNT) for name in Tallies.__slots__ if name != "games"},
        games=tuple(
            (kind, GameTally(draw(COUNT), draw(COUNT), draw(COUNT)))
            for kind in GameKind
            if kind in games
        ),
    )
    return Journal(tuple(entries), tallies)
