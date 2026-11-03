import os
from pathlib import Path

import platformdirs

from tama.infra.paths import (
    APP_NAME,
    CONFIG_PATH_ENV,
    SAVE_PATH_ENV,
    log_dir,
    resolve_config_path,
    resolve_save_path,
)


def test_default_save_path_is_in_user_data_dir() -> None:
    expected = platformdirs.user_data_path(APP_NAME) / "save.json"

    assert resolve_save_path(None, env={}) == expected


def test_env_overrides_default_save_path(tmp_path: Path) -> None:
    env = {SAVE_PATH_ENV: str(tmp_path / "env.json")}

    assert resolve_save_path(None, env=env) == tmp_path / "env.json"


def test_cli_overrides_env_save_path(tmp_path: Path) -> None:
    env = {SAVE_PATH_ENV: str(tmp_path / "env.json")}

    assert resolve_save_path(tmp_path / "cli.json", env=env) == tmp_path / "cli.json"


def test_empty_env_var_is_ignored() -> None:
    assert resolve_save_path(None, env={SAVE_PATH_ENV: ""}) == resolve_save_path(None, env={})


def test_paths_expand_user() -> None:
    home = Path.home()

    assert resolve_save_path(Path("~/pet.json"), env={}) == home / "pet.json"
    assert resolve_save_path(None, env={SAVE_PATH_ENV: "~/env.json"}) == home / "env.json"


def test_default_config_path_is_in_user_config_dir() -> None:
    expected = platformdirs.user_config_path(APP_NAME) / "config.toml"

    assert resolve_config_path(env={}) == expected


def test_env_overrides_config_path(tmp_path: Path) -> None:
    env = {CONFIG_PATH_ENV: str(tmp_path / "c.toml")}

    assert resolve_config_path(env=env) == tmp_path / "c.toml"


def test_defaults_read_the_real_environment() -> None:
    # conftest points TAMA_SAVE_PATH at a temp dir; the default env argument must see it.
    assert resolve_save_path() == Path(os.environ[SAVE_PATH_ENV])


def test_log_dir_is_in_user_log_dir() -> None:
    assert log_dir() == platformdirs.user_log_path(APP_NAME)
