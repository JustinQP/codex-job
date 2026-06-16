from __future__ import annotations

from pathlib import Path

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
