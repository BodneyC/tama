from datetime import time, timedelta
from pathlib import Path

import pytest

from tama.errors import ConfigError
from tama.infra.config import Config, load_config


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_missing_file_gives_defaults(tmp_path: Path) -> None:
    config = load_config(tmp_path / "nope.toml")

    assert config == Config()
    assert config.bell is False
    assert config.reduced_motion is False
    assert config.night_start == time(22)
    assert config.night_end == time(7)
    assert config.offline_cap == timedelta(hours=72)
    assert config.theme is None


def test_full_file_is_parsed(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        """
        bell = true
        reduced_motion = true
        night_start = 23:30:00
        night_end = "06:15"
        offline_cap_hours = 24
        theme = "nord"
        """,
    )

    assert load_config(path) == Config(
        bell=True,
        reduced_motion=True,
        night_start=time(23, 30),
        night_end=time(6, 15),
        offline_cap=timedelta(hours=24),
        theme="nord",
    )


def test_partial_file_keeps_other_defaults(tmp_path: Path) -> None:
    assert load_config(write(tmp_path, "bell = true\n")) == Config(bell=True)


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ("bell = true\nvolume = 11\n", "volume"),
        ('bell = "yes"\n', "bell"),
        ("offline_cap_hours = -1\n", "offline_cap_hours"),
        ('night_start = "late"\n', "night_start"),
        ("bell = \n", "TOML"),
    ],
    ids=["unknown-key", "wrong-type", "negative-cap", "bad-time", "invalid-toml"],
)
def test_invalid_config_raises_config_error(tmp_path: Path, text: str, match: str) -> None:
    with pytest.raises(ConfigError, match=match):
        load_config(write(tmp_path, text))


def test_unreadable_config_raises_config_error(tmp_path: Path) -> None:
    unreadable = tmp_path / "config.toml"
    unreadable.mkdir()

    with pytest.raises(ConfigError, match=r"config\.toml"):
        load_config(unreadable)


def test_cli_overrides_take_precedence() -> None:
    config = Config(bell=True, reduced_motion=False)

    assert config.with_overrides(bell=False, reduced_motion=True) == Config(
        bell=False, reduced_motion=True
    )


def test_unset_cli_overrides_keep_config_values() -> None:
    config = Config(bell=True, reduced_motion=True)

    assert config.with_overrides() == config
