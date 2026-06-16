from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, status
from sqlmodel import Session, select

from backend.db import JOBS_DIR
from backend.models import Project, Task, TaskStatus, utc_now
from backend.schemas import TaskCreate


def _artifact_paths(task_id: int) -> tuple[Path, Path, Path]:
    job_dir = JOBS_DIR / str(task_id)
    return job_dir / "run.log", job_dir / "result.md", job_dir / "diff.patch"


def _assign_artifact_paths(task: Task) -> None:
    if task.id is None:
        raise ValueError("task id is required before assigning artifact paths")

    log_file, result_file, diff_file = _artifact_paths(task.id)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    task.log_file = str(log_file)
    task.result_file = str(result_file)
    task.diff_file = str(diff_file)
    task.updated_at = utc_now()


def create_task(session: Session, payload: TaskCreate) -> Task:
    project = session.get(Project, payload.project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="project not found",
        )
    if not project.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project is disabled",
        )

    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="prompt cannot be empty",
        )

    now = utc_now()
    task = Task(
        project_id=payload.project_id,
        prompt=prompt,
        timeout_seconds=payload.timeout_seconds,
        status=TaskStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    session.add(task)
    session.commit()
    session.refresh(task)

    _assign_artifact_paths(task)
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def list_tasks(
    session: Session,
    *,
    project_id: int | None = None,
    task_status: TaskStatus | None = None,
    limit: int = 50,
) -> list[Task]:
    statement = select(Task)
    if project_id is not None:
        statement = statement.where(Task.project_id == project_id)
    if task_status is not None:
        statement = statement.where(Task.status == task_status)
    statement = statement.order_by(Task.id.desc()).limit(limit)
    return list(session.exec(statement).all())


def get_task_or_404(session: Session, task_id: int) -> Task:
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="task not found",
        )
    return task


def rerun_task(session: Session, task_id: int) -> Task:
    original = get_task_or_404(session, task_id)
    payload = TaskCreate(
        project_id=original.project_id,
        prompt=original.prompt,
        timeout_seconds=original.timeout_seconds,
    )
    return create_task(session, payload)


def to_task_read(task: Task):
    from backend.schemas import TaskRead

    if task.id is None:
        raise ValueError("task id is required")
    return TaskRead(
        id=task.id,
        project_id=task.project_id,
        prompt=task.prompt,
        status=task.status,
        timeout_seconds=task.timeout_seconds,
        exit_code=task.exit_code,
        error_message=task.error_message,
        log_url=f"/tasks/{task.id}/log",
        result_url=f"/tasks/{task.id}/result",
        diff_url=f"/tasks/{task.id}/diff",
        created_at=task.created_at,
        updated_at=task.updated_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
    )
