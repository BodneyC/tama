"""Where tama keeps its files.

Precedence for the save path is: ``--save-path`` CLI flag, then ``TAMA_SAVE_PATH``, then the
platform's user data directory. The config path can be overridden with ``TAMA_CONFIG_PATH``.
"""

import os
from collections.abc import Mapping
from pathlib import Path

import platformdirs

APP_NAME = "tama"
SAVE_PATH_ENV = "TAMA_SAVE_PATH"
CONFIG_PATH_ENV = "TAMA_CONFIG_PATH"


def resolve_save_path(cli_path: Path | None = None, env: Mapping[str, str] = os.environ) -> Path:
    """Return the save file path, honouring CLI and environment overrides."""
    if cli_path is not None:
        return cli_path.expanduser()
    if from_env := env.get(SAVE_PATH_ENV):
        return Path(from_env).expanduser()
    return platformdirs.user_data_path(APP_NAME) / "save.json"


def resolve_config_path(env: Mapping[str, str] = os.environ) -> Path:
    """Return the config file path, honouring the environment override."""
    if from_env := env.get(CONFIG_PATH_ENV):
        return Path(from_env).expanduser()
    return platformdirs.user_config_path(APP_NAME) / "config.toml"


def log_dir() -> Path:
    """Return the directory for log files."""
    return platformdirs.user_log_path(APP_NAME)
