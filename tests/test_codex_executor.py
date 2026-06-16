from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from runner.codex_executor import (
    check_clean_worktree,
    collect_git_artifacts,
    execute_codex,
    find_codex_bin,
)


def run(command: list[str], cwd: Path) -> None:
    import subprocess

    completed = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert completed.returncode == 0, completed.stderr


def test_find_codex_bin_prefers_explicit_env_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_codex = tmp_path / "codex.cmd"
    fake_codex.write_text("@echo off\n", encoding="utf-8")

    monkeypatch.setenv("CODEX_BIN", str(fake_codex))

    assert find_codex_bin() == str(fake_codex.resolve())


def test_find_codex_bin_fails_when_env_path_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("CODEX_BIN", str(tmp_path / "missing-codex.cmd"))

    with pytest.raises(FileNotFoundError):
        find_codex_bin()


def test_check_clean_worktree_rejects_non_git_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_run_git(project_path: Path, command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command,
            returncode=128,
            stdout="",
            stderr="fatal: not a git repository",
        )

    monkeypatch.setattr("runner.codex_executor._run_git", fake_run_git)

    error = check_clean_worktree(tmp_path)

    assert error is not None
    assert "not a git repository" in error


def test_collect_git_artifacts_captures_staged_unstaged_and_untracked(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test User"], repo)

    tracked = repo / "tracked.txt"
    tracked.write_text("base\n", encoding="utf-8")
    run(["git", "add", "tracked.txt"], repo)
    run(["git", "commit", "-m", "initial"], repo)

    tracked.write_text("base\nunstaged\n", encoding="utf-8")
    staged = repo / "staged.txt"
    staged.write_text("staged\n", encoding="utf-8")
    run(["git", "add", "staged.txt"], repo)
    untracked = repo / "untracked.txt"
    untracked.write_text("untracked\n", encoding="utf-8")

    result = collect_git_artifacts(repo, tmp_path / "job")

    assert result.error_message is None
    assert "tracked.txt" in result.status_file.read_text(encoding="utf-8")
    assert "unstaged" in result.diff_unstaged_file.read_text(encoding="utf-8")
    assert "staged.txt" in result.diff_staged_file.read_text(encoding="utf-8")
    assert "untracked.txt" in result.untracked_files_file.read_text(encoding="utf-8")
    combined = result.combined_diff_file.read_text(encoding="utf-8")
    assert "--- git diff --cached ---" in combined
    assert "untracked.txt" in combined


def test_execute_codex_stops_process_when_on_tick_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_codex = tmp_path / "codex.cmd"
    fake_codex.write_text("@echo off\n", encoding="utf-8")
    monkeypatch.setenv("CODEX_BIN", str(fake_codex))

    class FakeStdout:
        def __iter__(self):
            return iter(())

    class FakeProcess:
        pid = 123
        stdout = FakeStdout()

        def __init__(self):
            self.terminated = False
            self.killed = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True

        def wait(self, timeout=None):
            del timeout
            return -1

    process = FakeProcess()
    monkeypatch.setattr(
        "runner.codex_executor.subprocess.Popen",
        lambda *args, **kwargs: process,
    )

    result = execute_codex(
        project_path=tmp_path,
        prompt="work",
        log_file=tmp_path / "run.log",
        result_file=tmp_path / "result.md",
        timeout_seconds=60,
        on_tick=lambda: (_ for _ in ()).throw(RuntimeError("network down")),
    )

    assert result.exit_code == -1
    assert result.error_message == "on_tick failed: network down"
    assert process.terminated is True


def test_execute_codex_stops_process_when_should_cancel_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_codex = tmp_path / "codex.cmd"
    fake_codex.write_text("@echo off\n", encoding="utf-8")
    monkeypatch.setenv("CODEX_BIN", str(fake_codex))

    class FakeStdout:
        def __iter__(self):
            return iter(())

    class FakeProcess:
        pid = 124
        stdout = FakeStdout()

        def __init__(self):
            self.terminated = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

        def kill(self):
            pass

        def wait(self, timeout=None):
            del timeout
            return -1

    process = FakeProcess()
    monkeypatch.setattr(
        "runner.codex_executor.subprocess.Popen",
        lambda *args, **kwargs: process,
    )

    result = execute_codex(
        project_path=tmp_path,
        prompt="work",
        log_file=tmp_path / "run.log",
        result_file=tmp_path / "result.md",
        timeout_seconds=60,
        should_cancel=lambda: (_ for _ in ()).throw(RuntimeError("api down")),
    )

    assert result.exit_code == -1
    assert result.error_message == "should_cancel failed: api down"
    assert process.terminated is True
