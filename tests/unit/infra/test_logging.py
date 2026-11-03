import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from tama.infra.logging import LOG_FILE_NAME, configure_logging


@pytest.fixture(autouse=True)
def restore_root_logger() -> Iterator[None]:
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    yield
    for handler in root.handlers:
        if handler not in handlers:
            root.removeHandler(handler)
            handler.close()
    root.setLevel(level)
    logging.captureWarnings(capture=False)


def test_logs_go_to_a_file(tmp_path: Path) -> None:
    path = configure_logging(tmp_path / "logs")

    logging.getLogger("tama.test").warning("hello from the test")
    for handler in logging.getLogger().handlers:
        handler.flush()

    assert path == tmp_path / "logs" / LOG_FILE_NAME
    assert "hello from the test" in path.read_text(encoding="utf-8")


def test_reconfiguring_does_not_duplicate_handlers(tmp_path: Path) -> None:
    configure_logging(tmp_path)
    before = len(logging.getLogger().handlers)

    configure_logging(tmp_path)

    assert len(logging.getLogger().handlers) == before
