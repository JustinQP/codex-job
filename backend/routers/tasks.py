from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlmodel import Session

from backend import db
from backend.db import get_session
from backend.dependencies import require_api_token
from backend.models import TaskStatus
from backend.schemas import RunCreate, TaskArtifactsRead, TaskCreate, TaskRead, TaskTemplateRead
from backend.services import task_service


router = APIRouter()


@router.post("/tasks", response_model=TaskRead)
def create_task(
    payload: TaskCreate,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    task = task_service.create_task(session, payload)
    return task_service.to_task_read(task, session)


@router.post("/runs", response_model=TaskRead)
def create_run(
    payload: RunCreate,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    task = task_service.create_run(session, payload)
    return task_service.to_task_read(task, session)


@router.get("/tasks", response_model=list[TaskRead])
def list_tasks(
    project_id: int | None = None,
    workspace_id: int | None = None,
    status: TaskStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    tasks = task_service.list_tasks(
        session,
        project_id=project_id,
        workspace_id=workspace_id,
        task_status=status,
        limit=limit,
    )
    return [task_service.to_task_read(task, session) for task in tasks]


@router.get("/tasks/{task_id}", response_model=TaskRead)
def get_task(
    task_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    task = task_service.get_task_or_404(session, task_id)
    return task_service.to_task_read(task, session)


@router.post("/tasks/{task_id}/rerun", response_model=TaskRead)
def rerun_task(
    task_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    task = task_service.rerun_task(session, task_id)
    return task_service.to_task_read(task, session)


@router.post("/tasks/{task_id}/cancel", response_model=TaskRead)
def cancel_task(
    task_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    task = task_service.request_cancel(session, task_id)
    return task_service.to_task_read(task, session)


@router.get("/tasks/{task_id}/artifacts", response_model=TaskArtifactsRead)
def get_task_artifacts(
    task_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    task = task_service.get_task_or_404(session, task_id)
    return task_service.to_artifacts_read(task)


@router.get("/task-templates", response_model=list[TaskTemplateRead])
def list_task_templates(_: None = Depends(require_api_token)):
    return task_service.list_task_templates()


@router.get("/tasks/{task_id}/log", response_class=PlainTextResponse)
def get_task_log(
    task_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return _read_task_artifact(task_id, "log_file", session)


@router.get("/tasks/{task_id}/result", response_class=PlainTextResponse)
def get_task_result(
    task_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return _read_task_artifact(task_id, "result_file", session)


@router.get("/tasks/{task_id}/diff", response_class=PlainTextResponse)
def get_task_diff(
    task_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return _read_task_artifact(task_id, "diff_file", session)


@router.get("/tasks/{task_id}/artifacts/git-status", response_class=PlainTextResponse)
def get_task_git_status(
    task_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    task = task_service.get_task_or_404(session, task_id)
    if not task.diff_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="artifact path is not available",
        )
    git_status_path = Path(task.diff_file).resolve().parent / "git-status.txt"
    return _read_artifact_path(git_status_path)


@router.get("/tasks/{task_id}/artifacts/report", response_class=PlainTextResponse)
def get_task_report(
    task_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    task = task_service.get_task_or_404(session, task_id)
    if not task.diff_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="artifact path is not available",
        )
    report_path = Path(task.diff_file).resolve().parent / "task-report.md"
    return _read_artifact_path(report_path)


def _read_task_artifact(task_id: int, attr_name: str, session: Session) -> str:
    task = task_service.get_task_or_404(session, task_id)
    raw_path = getattr(task, attr_name)
    if not raw_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="artifact path is not available",
        )

    path = Path(raw_path).resolve()
    jobs_root = db.JOBS_DIR.resolve()
    try:
        path.relative_to(jobs_root)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="artifact path is outside jobs directory",
        ) from exc

    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="artifact file not found",
        )
    return path.read_text(encoding="utf-8", errors="replace")


def _read_artifact_path(path: Path) -> str:
    path = path.resolve()
    jobs_root = db.JOBS_DIR.resolve()
    try:
        path.relative_to(jobs_root)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="artifact path is outside jobs directory",
        ) from exc
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="artifact file not found",
        )
    return path.read_text(encoding="utf-8", errors="replace")
