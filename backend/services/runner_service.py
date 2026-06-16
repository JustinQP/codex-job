from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, status
from sqlmodel import Session, select

from backend.db import JOBS_DIR
from backend.models import Project, RunnerRecord, Task, TaskStatus, utc_now
from backend.schemas import (
    RunnerHeartbeat,
    RunnerRegister,
    RunnerTaskArtifactsUpload,
    RunnerTaskClaimResponse,
    RunnerTaskFinishRequest,
    RunnerTaskLogUpload,
)


def register_runner(session: Session, payload: RunnerRegister) -> RunnerRecord:
    now = utc_now()
    runner = session.get(RunnerRecord, payload.runner_id)
    if runner is None:
        runner = RunnerRecord(
            runner_id=payload.runner_id,
            pid=payload.pid,
            hostname=payload.hostname,
            status="ONLINE",
            registered_at=now,
            last_heartbeat_at=now,
        )
    else:
        runner.pid = payload.pid
        runner.hostname = payload.hostname
        runner.status = "ONLINE"
        runner.last_heartbeat_at = now
    session.add(runner)
    session.commit()
    session.refresh(runner)
    return runner


def heartbeat(session: Session, payload: RunnerHeartbeat) -> RunnerRecord:
    register_payload = RunnerRegister(
        runner_id=payload.runner_id,
        pid=payload.pid,
        hostname=payload.hostname,
    )
    return register_runner(session, register_payload)


def list_runners(session: Session) -> list[RunnerRecord]:
    return list(session.exec(select(RunnerRecord).order_by(RunnerRecord.runner_id)).all())


def claim_task(session: Session, runner_id: str) -> RunnerTaskClaimResponse | None:
    now = utc_now()
    task = session.exec(
        select(Task)
        .where(Task.status == TaskStatus.PENDING)
        .order_by(Task.created_at)
    ).first()
    if task is None or task.id is None:
        return None

    project = session.get(Project, task.project_id)
    if project is None:
        task.status = TaskStatus.FAILED
        task.error_message = "project not found"
        task.finished_at = now
        task.updated_at = now
        session.add(task)
        session.commit()
        return None

    task.status = TaskStatus.RUNNING
    task.started_at = now
    task.updated_at = now
    task.runner_id = runner_id
    task.runner_pid = None
    session.add(task)
    session.commit()
    session.refresh(task)

    return RunnerTaskClaimResponse(
        task_id=task.id,
        project_id=task.project_id,
        project_path=project.path,
        prompt=task.prompt,
        timeout_seconds=task.timeout_seconds,
        task_type=task.task_type,
        require_clean_worktree=project.require_clean_worktree,
        test_command=project.test_command,
        smoke_check_command=project.smoke_check_command,
        default_branch=project.default_branch,
    )


def upload_task_log(
    session: Session,
    task_id: int,
    payload: RunnerTaskLogUpload,
) -> dict[str, str]:
    task = _get_runner_task(session, task_id, payload.runner_id)
    log_path = _task_job_dir(task) / "run.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if payload.append else "w"
    with log_path.open(mode, encoding="utf-8", errors="replace") as log_file:
        log_file.write(payload.content)
    task.log_file = str(log_path)
    task.updated_at = utc_now()
    session.add(task)
    session.commit()
    return {"status": "ok"}


def upload_task_artifacts(
    session: Session,
    task_id: int,
    payload: RunnerTaskArtifactsUpload,
) -> dict[str, str]:
    task = _get_runner_task(session, task_id, payload.runner_id)
    job_dir = _task_job_dir(task)
    job_dir.mkdir(parents=True, exist_ok=True)
    mapping = {
        "result.md": payload.result,
        "diff.patch": payload.diff,
        "git-status.txt": payload.git_status,
        "diff-unstaged.patch": payload.diff_unstaged,
        "diff-staged.patch": payload.diff_staged,
        "untracked-files.txt": payload.untracked_files,
        "test-output.txt": payload.test_output,
        "task-report.md": payload.task_report,
    }
    for filename, content in mapping.items():
        if content is None:
            continue
        (job_dir / filename).write_text(content, encoding="utf-8", errors="replace")
    task.result_file = str(job_dir / "result.md")
    task.diff_file = str(job_dir / "diff.patch")
    task.updated_at = utc_now()
    session.add(task)
    session.commit()
    return {"status": "ok"}


def finish_task(
    session: Session,
    task_id: int,
    payload: RunnerTaskFinishRequest,
) -> Task:
    task = _get_runner_task(session, task_id, payload.runner_id)
    if payload.status not in {
        TaskStatus.SUCCESS,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="finish status must be terminal",
        )
    now = utc_now()
    task.status = payload.status
    task.exit_code = payload.exit_code
    task.error_message = payload.error_message
    task.runner_id = None
    task.runner_pid = None
    task.finished_at = now
    task.updated_at = now
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def get_cancel_state(session: Session, task_id: int, runner_id: str) -> Task:
    return _get_runner_task(session, task_id, runner_id)


def _get_runner_task(session: Session, task_id: int, runner_id: str) -> Task:
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="task not found",
        )
    if task.runner_id != runner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"task is not assigned to runner {runner_id}",
        )
    if task.status == TaskStatus.RUNNING:
        return task
    if task.cancel_requested:
        return task
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"task is not assigned to runner {runner_id}",
    )


def _task_job_dir(task: Task) -> Path:
    if task.id is None:
        raise ValueError("task id is required")
    return JOBS_DIR / str(task.id)
