from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlmodel import Session

from backend import db
from backend.db import get_session
from backend.dependencies import require_api_token
from backend.models import RunStatus
from backend.schemas import RunArtifactsRead, RunCreate, RunRead, RunTemplateRead
from backend.services import run_service


router = APIRouter()


@router.post("/runs", response_model=RunRead)
def create_run(
    payload: RunCreate,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    run = run_service.create_run(session, payload)
    return run_service.to_run_read(run, session)


@router.get("/runs", response_model=list[RunRead])
def list_runs(
    project_id: int | None = None,
    workspace_id: int | None = None,
    status: RunStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    runs = run_service.list_runs(
        session,
        project_id=project_id,
        workspace_id=workspace_id,
        run_status=status,
        limit=limit,
    )
    return [run_service.to_run_read(run, session) for run in runs]


@router.get("/runs/{run_id}", response_model=RunRead)
def get_run(
    run_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    run = run_service.get_run_or_404(session, run_id)
    return run_service.to_run_read(run, session)


@router.post("/runs/{run_id}/rerun", response_model=RunRead)
def rerun_run(
    run_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    run = run_service.rerun_run(session, run_id)
    return run_service.to_run_read(run, session)


@router.post("/runs/{run_id}/cancel", response_model=RunRead)
def cancel_run(
    run_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    run = run_service.request_cancel(session, run_id)
    return run_service.to_run_read(run, session)


@router.get("/runs/{run_id}/artifacts", response_model=RunArtifactsRead)
def get_run_artifacts(
    run_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    run = run_service.get_run_or_404(session, run_id)
    return run_service.to_artifacts_read(run)


@router.get("/run-templates", response_model=list[RunTemplateRead])
def list_run_templates(_: None = Depends(require_api_token)):
    return run_service.list_run_templates()


@router.get("/runs/{run_id}/log", response_class=PlainTextResponse)
def get_run_log(
    run_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return _read_run_artifact(run_id, "log_file", session)


@router.get("/runs/{run_id}/result", response_class=PlainTextResponse)
def get_run_result(
    run_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return _read_run_artifact(run_id, "result_file", session)


@router.get("/runs/{run_id}/diff", response_class=PlainTextResponse)
def get_run_diff(
    run_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return _read_run_artifact(run_id, "diff_file", session)


@router.get("/runs/{run_id}/artifacts/git-status", response_class=PlainTextResponse)
def get_run_git_status(
    run_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    run = run_service.get_run_or_404(session, run_id)
    if not run.diff_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact path is not available")
    git_status_path = Path(run.diff_file).resolve().parent / "git-status.txt"
    return _read_artifact_path(git_status_path)


@router.get("/runs/{run_id}/artifacts/report", response_class=PlainTextResponse)
def get_run_report(
    run_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    run = run_service.get_run_or_404(session, run_id)
    if not run.diff_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact path is not available")
    report_path = Path(run.diff_file).resolve().parent / "run-report.md"
    return _read_artifact_path(report_path)


def _read_run_artifact(run_id: int, attr_name: str, session: Session) -> str:
    run = run_service.get_run_or_404(session, run_id)
    raw_path = getattr(run, attr_name)
    if not raw_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact path is not available")

    path = Path(raw_path).resolve()
    return _read_artifact_path(path)


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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact file not found")
    return path.read_text(encoding="utf-8", errors="replace")
