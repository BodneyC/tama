"""Where tama keeps its files.

tama keeps its pets in ``<data dir>/pets/`` (ADR 0007); the data directory is the platform's
user data directory unless ``TAMA_DATA_DIR`` says otherwise. ``--save-path`` (or
``TAMA_SAVE_PATH``) instead plays exactly one save file, outside the pet list. The config path
can be overridden with ``TAMA_CONFIG_PATH``.
"""

import os
from collections.abc import Mapping
from pathlib import Path

import platformdirs

APP_NAME = "tama"
SAVE_PATH_ENV = "TAMA_SAVE_PATH"
DATA_DIR_ENV = "TAMA_DATA_DIR"
LEGACY_SAVE = "save.json"
"""The single save file of tama before several pets; moved into ``pets/`` on first run."""
CONFIG_PATH_ENV = "TAMA_CONFIG_PATH"


def single_save_path(
    cli_path: Path | None = None, env: Mapping[str, str] = os.environ
) -> Path | None:
    """The one save file to play (``--save-path``, then ``TAMA_SAVE_PATH``), if asked for."""
    if cli_path is not None:
        return cli_path.expanduser()
    if from_env := env.get(SAVE_PATH_ENV):
        return Path(from_env).expanduser()
    return None


def resolve_data_dir(env: Mapping[str, str] = os.environ) -> Path:
    """Where tama keeps its pets (``TAMA_DATA_DIR``, else the user data directory)."""
    if from_env := env.get(DATA_DIR_ENV):
        return Path(from_env).expanduser()
    return platformdirs.user_data_path(APP_NAME)


def resolve_config_path(env: Mapping[str, str] = os.environ) -> Path:
    """Return the config file path, honouring the environment override."""
    if from_env := env.get(CONFIG_PATH_ENV):
        return Path(from_env).expanduser()
    return platformdirs.user_config_path(APP_NAME) / "config.toml"


def log_dir() -> Path:
    """Return the directory for log files."""
    return platformdirs.user_log_path(APP_NAME)
