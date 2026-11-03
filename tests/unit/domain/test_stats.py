import pytest

from tama.domain.stats import NEEDS, STAT_MAX, STAT_MIN, Stat, Stats, clamp
from tama.errors import InvalidArgumentError


@pytest.mark.parametrize(
    ("value", "expected"),
    [(-5, 0), (0, 0), (42, 42), (100, 100), (250, 100)],
)
def test_clamp_limits_to_stat_range(value: int, expected: int) -> None:
    assert clamp(value) == expected


def test_clamp_accepts_custom_bounds() -> None:
    assert clamp(0, low=1, high=10) == 1
    assert clamp(11, low=1, high=10) == 10


def test_default_stats_are_full_except_discipline() -> None:
    stats = Stats()

    assert all(stats[stat] == STAT_MAX for stat in Stat if stat is not Stat.DISCIPLINE)
    assert stats.discipline == STAT_MIN


@pytest.mark.parametrize("bad", [-1, 101])
def test_out_of_range_stats_are_rejected(bad: int) -> None:
    with pytest.raises(InvalidArgumentError, match="hunger"):
        Stats(hunger=bad)


def test_with_value_clamps() -> None:
    assert Stats().with_value(Stat.HEALTH, -20).health == 0
    assert Stats().with_value(Stat.HEALTH, 50).health == 50


def test_adjust_adds_delta_and_clamps() -> None:
    stats = Stats(hunger=90)

    assert stats.adjust(Stat.HUNGER, 30).hunger == 100
    assert stats.adjust(Stat.HUNGER, -30).hunger == 60


def test_stats_are_immutable() -> None:
    stats = Stats()

    stats.adjust(Stat.HUNGER, -10)

    assert stats.hunger == STAT_MAX


def test_needs_are_the_neglectable_stats() -> None:
    assert NEEDS == (Stat.HUNGER, Stat.HAPPINESS, Stat.HYGIENE)
