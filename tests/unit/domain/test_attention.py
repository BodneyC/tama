from datetime import UTC, datetime
from typing import Any

import pytest

from tama.domain.attention import AttentionReason, attention_reasons, new_attention_calls
from tama.domain.balance import DEFAULT_BALANCE
from tama.domain.stage import DeathCause, LifeStage
from tama.domain.stats import Stats
from tests.factories import make_pet


def reasons(**overrides: Any) -> frozenset[AttentionReason]:
    return attention_reasons(make_pet(**overrides), DEFAULT_BALANCE)


def test_content_pet_needs_nothing() -> None:
    assert reasons() == frozenset()


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"stats": Stats(hunger=24)}, AttentionReason.HUNGRY),
        ({"stats": Stats(happiness=24)}, AttentionReason.UNHAPPY),
        ({"stats": Stats(hygiene=24)}, AttentionReason.DIRTY),
        ({"sickness_doses": 1}, AttentionReason.SICK),
        ({"poop_count": 1}, AttentionReason.POOP),
        ({"misbehaving": True}, AttentionReason.MISBEHAVING),
        (
            {"is_asleep": True, "updated_at": datetime(2026, 1, 1, 23, tzinfo=UTC)},
            AttentionReason.LIGHTS,
        ),
    ],
)
def test_each_reason(overrides: dict[str, Any], reason: AttentionReason) -> None:
    assert reasons(**overrides) == {reason}


def test_threshold_is_exclusive() -> None:
    assert reasons(stats=Stats(hunger=25)) == frozenset()


def test_multiple_reasons_combine() -> None:
    assert reasons(sickness_doses=1, poop_count=2) == {AttentionReason.SICK, AttentionReason.POOP}


@pytest.mark.parametrize("stage", [LifeStage.EGG, LifeStage.DEAD])
def test_eggs_and_dead_pets_never_call(stage: LifeStage) -> None:
    assert reasons(stage=stage, poop_count=3, cause_of_death=DeathCause.OLD_AGE) == frozenset()


H, P, S = AttentionReason.HUNGRY, AttentionReason.POOP, AttentionReason.SICK


@pytest.mark.parametrize(
    ("before", "after", "new"),
    [
        (set(), {H}, {H}),
        ({H}, {H}, set()),
        ({H}, {H, P}, {P}),
        ({H, P}, {P}, set()),
        ({H}, set(), set()),
        ({S}, {H}, {H}),
    ],
)
def test_new_attention_calls_are_those_just_raised(
    before: set[AttentionReason], after: set[AttentionReason], new: set[AttentionReason]
) -> None:
    assert new_attention_calls(frozenset(before), frozenset(after)) == new
