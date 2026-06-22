from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from backend.db import get_session
from backend.dependencies import require_api_token
from backend.schemas import (
    RunnerHeartbeat,
    RunnerRead,
    RunnerRegister,
    RunnerTaskArtifactsUpload,
    RunnerTaskCancelState,
    RunnerTaskClaimRequest,
    RunnerTaskClaimResponse,
    RunnerTaskFinishRequest,
    RunnerTaskLogUpload,
    TaskRead,
)
from backend.services import runner_service, task_service


router = APIRouter()


@router.post("/runners/register", response_model=RunnerRead)
def register_runner(
    payload: RunnerRegister,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return runner_service.register_runner(session, payload)


@router.post("/runner/register", response_model=RunnerRead, deprecated=True)
def runner_register(
    payload: RunnerRegister,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return runner_service.register_runner(session, payload)


@router.post("/runners/heartbeat", response_model=RunnerRead)
def runner_heartbeat(
    payload: RunnerHeartbeat,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return runner_service.heartbeat(session, payload)


@router.post("/runner/heartbeat", response_model=RunnerRead, deprecated=True)
def runner_http_heartbeat(
    payload: RunnerHeartbeat,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return runner_service.heartbeat(session, payload)


@router.get("/runners", response_model=list[RunnerRead])
def list_runners(
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return runner_service.list_runners(session)


@router.post(
    "/runner/tasks/claim",
    response_model=RunnerTaskClaimResponse | None,
    deprecated=True,
)
def runner_claim_task(
    payload: RunnerTaskClaimRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return runner_service.claim_task(session, payload.runner_id)


@router.post("/runner/tasks/{task_id}/log", deprecated=True)
def runner_upload_task_log(
    task_id: int,
    payload: RunnerTaskLogUpload,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return runner_service.upload_task_log(session, task_id, payload)


@router.post("/runner/tasks/{task_id}/artifacts", deprecated=True)
def runner_upload_task_artifacts(
    task_id: int,
    payload: RunnerTaskArtifactsUpload,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return runner_service.upload_task_artifacts(session, task_id, payload)


@router.post(
    "/runner/tasks/{task_id}/finish",
    response_model=TaskRead,
    deprecated=True,
)
def runner_finish_task(
    task_id: int,
    payload: RunnerTaskFinishRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    task = runner_service.finish_task(session, task_id, payload)
    return task_service.to_task_read(task, session)


@router.get(
    "/runner/tasks/{task_id}/cancel-state",
    response_model=RunnerTaskCancelState,
    deprecated=True,
)
def runner_get_cancel_state(
    task_id: int,
    runner_id: str,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    task = runner_service.get_cancel_state(session, task_id, runner_id)
    return RunnerTaskCancelState(
        task_id=task.id,
        cancel_requested=task.cancel_requested,
        status=task.status,
    )
