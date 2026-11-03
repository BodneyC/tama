import os
from pathlib import Path

import pytest

from tama.errors import PetLockedError, TamaError
from tama.persistence.lock import PetLock, process_alive

ME, OTHER = 1000, 2000


def lock(tmp_path: Path, pid: int = ME, *, others_alive: bool = True) -> PetLock:
    return PetLock(tmp_path / "mochi.json", pid=pid, alive=lambda _pid: others_alive)


def test_taking_a_lock_records_the_process(tmp_path: Path) -> None:
    held = lock(tmp_path)

    held.acquire()

    assert (tmp_path / "mochi.json.lock").read_text(encoding="utf-8") == str(ME)


def test_a_pet_open_elsewhere_cannot_be_locked(tmp_path: Path) -> None:
    lock(tmp_path, OTHER).acquire()

    with pytest.raises(PetLockedError, match="already open") as caught:
        lock(tmp_path).acquire()
    assert caught.value.pid == OTHER
    assert issubclass(PetLockedError, TamaError)


def test_a_stale_lock_is_taken_over(tmp_path: Path) -> None:
    lock(tmp_path, OTHER).acquire()

    lock(tmp_path, others_alive=False).acquire()

    assert (tmp_path / "mochi.json.lock").read_text(encoding="utf-8") == str(ME)


@pytest.mark.parametrize("content", ["", "not a pid", "-5"])
def test_a_garbled_lock_is_taken_over(tmp_path: Path, content: str) -> None:
    (tmp_path / "mochi.json.lock").write_text(content, encoding="utf-8")

    lock(tmp_path).acquire()

    assert (tmp_path / "mochi.json.lock").read_text(encoding="utf-8") == str(ME)


def test_taking_our_own_lock_again_is_fine(tmp_path: Path) -> None:
    lock(tmp_path).acquire()
    lock(tmp_path).acquire()


def test_releasing_removes_only_our_own_lock(tmp_path: Path) -> None:
    mine = lock(tmp_path)
    mine.acquire()
    mine.release()
    assert not (tmp_path / "mochi.json.lock").exists()

    lock(tmp_path, OTHER).acquire()
    mine.release()
    assert (tmp_path / "mochi.json.lock").exists()


def test_releasing_a_lock_never_taken_does_nothing(tmp_path: Path) -> None:
    lock(tmp_path).release()


def test_a_lock_works_as_a_context_manager(tmp_path: Path) -> None:
    with lock(tmp_path) as held:
        assert held.path.exists()
    assert not held.path.exists()


def test_this_process_is_alive() -> None:
    assert process_alive(os.getpid())


def test_a_finished_process_is_not_alive() -> None:
    assert not process_alive(2**22 + 12345)  # above Linux's pid_max default; never in use
