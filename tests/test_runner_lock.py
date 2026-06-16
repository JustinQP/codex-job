from __future__ import annotations

from pathlib import Path

import pytest

from runner.runner import RunnerLock


def test_runner_lock_removes_stale_lock(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    lock_file = tmp_path / "runner.lock"
    lock_file.write_text("pid=999999\n", encoding="utf-8")
    monkeypatch.setattr("runner.runner.is_process_running", lambda pid: False)

    lock = RunnerLock(lock_file)
    lock.acquire()

    assert lock.acquired is True
    assert "pid=" in lock_file.read_text(encoding="utf-8")
    lock.release()
    assert not lock_file.exists()


def test_runner_lock_rejects_running_pid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    lock_file = tmp_path / "runner.lock"
    lock_file.write_text("pid=123\n", encoding="utf-8")
    monkeypatch.setattr("runner.runner.is_process_running", lambda pid: True)

    lock = RunnerLock(lock_file)

    with pytest.raises(RuntimeError):
        lock.acquire()

    assert lock_file.exists()
