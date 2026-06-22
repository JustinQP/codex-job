from __future__ import annotations

from datetime import timedelta
import os
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import or_, update
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

RUNNER_LEASE_SECONDS = 60
RUNNING_TASK_LEASE_SECONDS = 120
RECOVER_MODE_FAILED = "failed"
RECOVER_MODE_REQUEUE = "requeue"


def register_runner(session: Session, payload: RunnerRegister) -> RunnerRecord:
    now = utc_now()
    lease_expires_at = now + timedelta(seconds=RUNNER_LEASE_SECONDS)
    runner = session.get(RunnerRecord, payload.runner_id)
    if runner is None:
        runner = RunnerRecord(
            runner_id=payload.runner_id,
            pid=payload.pid,
            hostname=payload.hostname,
            supported_models=payload.supported_models,
            status="ONLINE",
            registered_at=now,
            last_heartbeat_at=now,
            lease_expires_at=lease_expires_at,
        )
    else:
        runner.pid = payload.pid
        runner.hostname = payload.hostname
        runner.supported_models = payload.supported_models
        runner.status = "ONLINE"
        runner.last_heartbeat_at = now
        runner.lease_expires_at = lease_expires_at
    session.add(runner)
    session.commit()
    session.refresh(runner)
    return runner


def heartbeat(session: Session, payload: RunnerHeartbeat) -> RunnerRecord:
    register_payload = RunnerRegister(
        runner_id=payload.runner_id,
        pid=payload.pid,
        hostname=payload.hostname,
        supported_models=payload.supported_models,
    )
    return register_runner(session, register_payload)


def list_runners(session: Session) -> list[RunnerRecord]:
    mark_offline_runners(session)
    return list(session.exec(select(RunnerRecord).order_by(RunnerRecord.runner_id)).all())


def claim_task(session: Session, runner_id: str) -> RunnerTaskClaimResponse | None:
    mark_offline_runners(session)
    recover_expired_running_tasks(session)
    now = utc_now()
    task_lease_expires_at = now + timedelta(seconds=RUNNING_TASK_LEASE_SECONDS)
    task = session.exec(
        select(Task)
        .where(
            Task.status == TaskStatus.PENDING,
            Task.workspace_id.is_(None),
            Task.device_id.is_(None),
            Task.command_id.is_(None),
            or_(
                Task.assigned_runner_id.is_(None),
                Task.assigned_runner_id == runner_id,
            ),
        )
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
    if not project.enabled:
        task.status = TaskStatus.FAILED
        task.error_message = "project is disabled"
        task.finished_at = now
        task.updated_at = now
        session.add(task)
        session.commit()
        return None

    result = session.exec(
        update(Task)
        .where(
            Task.id == task.id,
            Task.status == TaskStatus.PENDING,
            Task.workspace_id.is_(None),
            Task.device_id.is_(None),
            Task.command_id.is_(None),
            or_(
                Task.assigned_runner_id.is_(None),
                Task.assigned_runner_id == runner_id,
            ),
        )
        .values(
            status=TaskStatus.RUNNING,
            started_at=now,
            updated_at=now,
            runner_id=runner_id,
            runner_pid=None,
            lease_expires_at=task_lease_expires_at,
        )
    )
    session.commit()
    if result.rowcount != 1:
        return None
    session.refresh(task)

    return RunnerTaskClaimResponse(
        task_id=task.id,
        project_id=task.project_id,
        project_path=project.path,
        prompt=task.prompt,
        timeout_seconds=task.timeout_seconds,
        task_type=task.task_type,
        model=task.model,
        reasoning_effort=task.reasoning_effort,
        sandbox=task.sandbox or "workspace-write",
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
    task.lease_expires_at = utc_now() + timedelta(seconds=RUNNING_TASK_LEASE_SECONDS)
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
    task.lease_expires_at = utc_now() + timedelta(seconds=RUNNING_TASK_LEASE_SECONDS)
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
    task.lease_expires_at = None
    task.finished_at = now
    task.updated_at = now
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def get_cancel_state(session: Session, task_id: int, runner_id: str) -> Task:
    task = _get_runner_task(session, task_id, runner_id)
    task.lease_expires_at = utc_now() + timedelta(seconds=RUNNING_TASK_LEASE_SECONDS)
    task.updated_at = utc_now()
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def mark_offline_runners(session: Session) -> int:
    now = utc_now()
    runners = session.exec(
        select(RunnerRecord).where(
            RunnerRecord.status == "ONLINE",
            RunnerRecord.lease_expires_at.is_not(None),
            RunnerRecord.lease_expires_at < now,
        )
    ).all()
    for runner in runners:
        runner.status = "OFFLINE"
        session.add(runner)
    if runners:
        session.commit()
    return len(runners)


def recover_expired_running_tasks(session: Session) -> int:
    recover_mode = os.environ.get(
        "RECOVER_EXPIRED_TASKS_MODE",
        RECOVER_MODE_FAILED,
    ).strip().lower()
    now = utc_now()
    tasks = session.exec(
        select(Task).where(
            Task.status == TaskStatus.RUNNING,
            Task.lease_expires_at.is_not(None),
            Task.lease_expires_at < now,
        )
    ).all()
    for task in tasks:
        if recover_mode == RECOVER_MODE_REQUEUE:
            task.status = TaskStatus.PENDING
            task.started_at = None
            task.finished_at = None
            task.error_message = "requeued from expired runner lease"
        else:
            task.status = TaskStatus.FAILED
            task.finished_at = now
            task.error_message = "failed from expired runner lease"
        task.runner_id = None
        task.runner_pid = None
        task.lease_expires_at = None
        task.updated_at = now
        session.add(task)
    if tasks:
        session.commit()
    return len(tasks)


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
