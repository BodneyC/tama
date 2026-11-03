"""Log to a file, never the terminal (output there would corrupt the TUI)."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FILE_NAME = "tama.log"
_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def configure_logging(directory: Path, level: int = logging.INFO) -> Path:
    """Send all logging (and Python warnings) to a rotating file in ``directory``.

    Safe to call more than once: an existing tama file handler is replaced, not duplicated.

    Returns:
        The log file path.
    """
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / LOG_FILE_NAME
    root = logging.getLogger()
    for handler in [h for h in root.handlers if getattr(h, "_tama", False)]:
        root.removeHandler(handler)
        handler.close()
    handler = RotatingFileHandler(path, maxBytes=512_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter(_FORMAT))
    handler._tama = True  # type: ignore[attr-defined]  # marker so reconfiguring replaces it
    root.addHandler(handler)
    root.setLevel(level)
    logging.captureWarnings(capture=True)
    return path
