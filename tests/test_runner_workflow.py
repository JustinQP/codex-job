from __future__ import annotations

from pathlib import Path
from urllib.error import URLError

import runner.runner as runner_module
from backend.models import TaskStatus, TaskType


def test_write_task_report_and_test_output(tmp_path: Path) -> None:
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    task = runner_module.ClaimedTask(
        task_id=1,
        project_id=2,
        project_path=tmp_path,
        prompt="do work",
        timeout_seconds=120,
        task_type=TaskType.IMPLEMENT,
        require_clean_worktree=True,
        test_command="pytest -q",
        smoke_check_command="python -m compileall backend",
        default_branch="main",
    )

    assert runner_module.write_test_output(task, job_dir) is None
    assert (
        runner_module.write_task_report(
            task,
            job_dir,
            status=TaskStatus.SUCCESS,
            exit_code=0,
            error_message=None,
        )
        is None
    )
    assert "pytest -q" in (job_dir / "test-output.txt").read_text(encoding="utf-8")
    assert "Task" in (job_dir / "task-report.md").read_text(encoding="utf-8")


def test_validate_project_rechecks_project_path_whitelist(
    tmp_path: Path,
    monkeypatch,
) -> None:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    monkeypatch.setenv("PROJECT_PATH_WHITELIST", str(allowed))

    error = runner_module.validate_project(outside, True)

    assert error == "project path is outside PROJECT_PATH_WHITELIST"


def test_open_runner_request_retries_network_errors(monkeypatch) -> None:
    attempts = {"count": 0}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return b'{"ok": true}'

    def fake_urlopen(request, timeout):
        del request, timeout
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise URLError("temporary network error")
        return FakeResponse()

    monkeypatch.setattr(runner_module, "urlopen", fake_urlopen)
    monkeypatch.setattr(runner_module.time, "sleep", lambda seconds: None)

    response = runner_module._open_runner_request_with_retry(
        "POST",
        "http://backend/runner/tasks/claim",
        b"{}",
        {"Accept": "application/json"},
        retry_delay_seconds=0,
    )

    assert response == '{"ok": true}'
    assert attempts["count"] == 2


def test_upload_artifacts_writes_pending_marker_on_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    log_file = job_dir / "run.log"
    result_file = job_dir / "result.md"
    diff_file = job_dir / "diff.patch"
    log_file.write_text("log", encoding="utf-8")
    result_file.write_text("result", encoding="utf-8")
    diff_file.write_text("diff", encoding="utf-8")

    def failing_request(method, path, payload=None):
        del method, path, payload
        raise RuntimeError("backend offline")

    monkeypatch.setattr(runner_module, "_runner_request", failing_request)

    try:
        runner_module.upload_artifacts(1, log_file, result_file, diff_file)
    except RuntimeError:
        pass

    pending = job_dir / "upload-pending.json"
    assert pending.exists()
    assert "backend offline" in pending.read_text(encoding="utf-8")


def test_log_upload_tracker_uploads_on_interval(
    monkeypatch,
    tmp_path: Path,
) -> None:
    uploaded: list[str] = []
    log_file = tmp_path / "run.log"
    log_file.write_text("first", encoding="utf-8")
    tracker = runner_module.LogUploadTracker(1, log_file, interval_seconds=10)
    times = iter([0.0, 11.0, 11.0, 12.0])

    monkeypatch.setattr(runner_module.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(
        runner_module,
        "_upload_log_content",
        lambda task_id, content: uploaded.append(content),
    )

    tracker.maybe_upload()
    tracker.maybe_upload()

    assert uploaded == ["first"]
