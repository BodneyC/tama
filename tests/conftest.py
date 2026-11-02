import os
from pathlib import Path

import pytest
from hypothesis import settings

settings.register_profile("default", deadline=None)
settings.register_profile("ci", deadline=None, max_examples=500)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))


@pytest.fixture(autouse=True)
def isolate_user_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point every save/config/log location at a temp dir so tests never touch real data."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("TAMA_SAVE_PATH", str(home / "save.json"))
    monkeypatch.setenv("HOME", str(home))
    for var in ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
        monkeypatch.setenv(var, str(home / var.lower()))
    return home
