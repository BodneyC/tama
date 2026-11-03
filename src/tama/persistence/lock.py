"""One window per pet: a ``<save>.lock`` file holding the process id (ADR 0007).

A lock whose process has gone (a crash, a killed terminal) is stale and is taken over. Read-only
views never lock.
"""

import contextlib
import logging
import os
import sys
from collections.abc import Callable
from pathlib import Path
from types import TracebackType
from typing import Self

from tama.errors import PetLockedError

logger = logging.getLogger(__name__)


def process_alive(pid: int) -> bool:
    """Whether a process with id ``pid`` is running."""
    if pid <= 0:
        return False
    if sys.platform == "win32":  # os.kill(pid, 0) would send Ctrl-C on Windows
        return _windows_process_alive(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:  # it exists, it just isn't ours
        return True
    except OSError:
        return False
    return True


if sys.platform == "win32":  # pragma: no cover - exercised on Windows CI

    def _windows_process_alive(pid: int) -> bool:
        import ctypes  # noqa: PLC0415 - Windows only

        query_limited_information, still_active = 0x1000, 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(query_limited_information, False, pid)  # noqa: FBT003
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            return code.value == still_active
        finally:
            kernel32.CloseHandle(handle)


class PetLock:
    """The lock on one pet's save file."""

    def __init__(
        self,
        save_path: Path,
        *,
        pid: int | None = None,
        alive: Callable[[int], bool] = process_alive,
    ) -> None:
        """Lock ``save_path`` for process ``pid`` (this one by default)."""
        self.path = save_path.with_name(save_path.name + ".lock")
        self.pid = os.getpid() if pid is None else pid
        self._alive = alive

    def acquire(self) -> None:
        """Take the lock, taking over a stale one.

        Raises:
            PetLockedError: If another running process holds it.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            owner = self._owner()
            if owner == self.pid:
                return
            if owner is not None and self._alive(owner):
                raise PetLockedError(
                    f"{self.path.stem} is already open in another tama (process {owner})",
                    pid=owner,
                ) from None
            logger.warning("Taking over a stale lock %s (process %s)", self.path, owner)
            self.path.write_text(str(self.pid), encoding="utf-8")
            return
        with os.fdopen(fd, "w", encoding="utf-8") as lock_file:
            lock_file.write(str(self.pid))

    def release(self) -> None:
        """Give the lock up, if this process holds it."""
        if self._owner() == self.pid:
            with contextlib.suppress(FileNotFoundError):
                self.path.unlink()

    def _owner(self) -> int | None:
        try:
            owner = int(self.path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return None
        return owner if owner > 0 else None

    def __enter__(self) -> Self:
        """Take the lock for a ``with`` block."""
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Release the lock at the end of a ``with`` block."""
        self.release()
