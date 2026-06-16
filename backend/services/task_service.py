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


def list_tasks(session: Session) -> list[Task]:
    return list(session.exec(select(Task).order_by(Task.id.desc())).all())


def get_task_or_404(session: Session, task_id: int) -> Task:
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="task not found",
        )
    return task
