from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from backend.db import get_session
from backend.dependencies import require_agent_token
from backend.schemas import (
    AgentCommandClaimRequest,
    AgentCommandCompleteRequest,
    AgentCommandEventsUploadRead,
    AgentCommandEventsUploadRequest,
    AgentCommandLeaseRequest,
    AgentReconcileRead,
    AgentReconcileRequest,
    AgentCommandRead,
    DeviceHeartbeat,
    DeviceRead,
    DeviceRegister,
    RunArtifactUpload,
    RunArtifactUploadRead,
    RunLogChunkUpload,
    RunLogChunkUploadRead,
    WorkspaceSyncRead,
    WorkspaceSyncRequest,
)
from backend.services import (
    agent_command_maintenance_service,
    agent_command_event_service,
    agent_command_service,
    agent_reconciliation_service,
    app_thread_service,
    device_service,
    run_artifact_service,
    run_service,
    run_log_service,
    workspace_service,
    workspace_lock_service,
)


router = APIRouter()


ERROR_STATUS = {
    "agent_command_not_found": status.HTTP_404_NOT_FOUND,
    "device_not_found": status.HTTP_404_NOT_FOUND,
    "device_disabled": status.HTTP_403_FORBIDDEN,
    "agent_command_device_mismatch": status.HTTP_403_FORBIDDEN,
    "invalid_lease_token": status.HTTP_409_CONFLICT,
    "lease_expired": status.HTTP_409_CONFLICT,
    "invalid_agent_command_state": status.HTTP_409_CONFLICT,
    "invalid_completion_status": status.HTTP_400_BAD_REQUEST,
    "missing_claim_request_id": status.HTTP_400_BAD_REQUEST,
    "too_many_command_events": status.HTTP_413_CONTENT_TOO_LARGE,
    "command_event_too_large": status.HTTP_413_CONTENT_TOO_LARGE,
    "duplicate_event_sequence_in_batch": status.HTTP_409_CONFLICT,
    "out_of_order_command_events": status.HTTP_409_CONFLICT,
    "command_event_sequence_conflict": status.HTTP_409_CONFLICT,
    "app_turn_not_found": status.HTTP_404_NOT_FOUND,
    "turn_event_sequence_conflict": status.HTTP_409_CONFLICT,
}


def raise_agent_command_error(exc: agent_command_service.AgentCommandServiceError) -> None:
    raise HTTPException(
        status_code=ERROR_STATUS.get(exc.code, status.HTTP_400_BAD_REQUEST),
        detail={"code": exc.code, "message": exc.message},
    )


@router.post("/agent/register", response_model=DeviceRead)
def register_agent(
    payload: DeviceRegister,
    session: Session = Depends(get_session),
    _: None = Depends(require_agent_token),
):
    return device_service.register_device(session, payload)


@router.post("/agent/heartbeat", response_model=DeviceRead)
def heartbeat_agent(
    payload: DeviceHeartbeat,
    session: Session = Depends(get_session),
    _: None = Depends(require_agent_token),
):
    return device_service.heartbeat_device(session, payload)


@router.post("/agent/workspaces/sync", response_model=WorkspaceSyncRead)
def sync_agent_workspaces(
    payload: WorkspaceSyncRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_agent_token),
):
    device_service.get_device_or_404(session, payload.device_id)
    return workspace_service.sync_device_workspaces(session, payload)


@router.post("/agent/commands/claim", response_model=AgentCommandRead | None)
def claim_agent_command(
    payload: AgentCommandClaimRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_agent_token),
):
    try:
        agent_command_maintenance_service.expire_stale_agent_commands(
            session,
            device_id=payload.device_id,
        )
        return agent_command_service.claim_command(
            session,
            device_id=payload.device_id,
            claim_request_id=payload.claim_request_id,
        )
    except agent_command_service.AgentCommandServiceError as exc:
        raise_agent_command_error(exc)


@router.post("/agent/commands/{command_id}/ack", response_model=AgentCommandRead)
def ack_agent_command(
    command_id: str,
    payload: AgentCommandLeaseRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_agent_token),
):
    try:
        command = agent_command_service.ack_command(
            session,
            command_id=command_id,
            device_id=payload.device_id,
            lease_token=payload.lease_token,
        )
        if command.command_type == "TURN_START":
            app_thread_service.mark_agent_turn_running(session, command_id=command.id)
            session.refresh(command)
        elif command.command_type == "RUN_EXECUTE":
            run_service.mark_run_running(session, command_id=command.id)
            session.refresh(command)
        return command
    except agent_command_service.AgentCommandServiceError as exc:
        raise_agent_command_error(exc)


@router.post("/agent/commands/{command_id}/renew", response_model=AgentCommandRead)
def renew_agent_command(
    command_id: str,
    payload: AgentCommandLeaseRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_agent_token),
):
    try:
        command = agent_command_service.renew_command(
            session,
            command_id=command_id,
            device_id=payload.device_id,
            lease_token=payload.lease_token,
        )
        if command.command_type == "RUN_EXECUTE":
            run_service.renew_run_lease_from_command(session, command_id=command.id)
            if command.aggregate_id:
                workspace_lock_service.renew_workspace_lock(
                    session,
                    owner_type="run",
                    owner_id=str(command.aggregate_id),
                )
            session.refresh(command)
        elif command.command_type in {"SESSION_OPEN", "SESSION_CLOSE", "TURN_START"}:
            owner_id = _workspace_lock_owner_id_for_session_command(session, command)
            if owner_id is not None:
                workspace_lock_service.renew_workspace_lock(
                    session,
                    owner_type="app_thread",
                    owner_id=owner_id,
                )
            session.refresh(command)
        return command
    except agent_command_service.AgentCommandServiceError as exc:
        raise_agent_command_error(exc)


@router.post("/agent/commands/{command_id}/complete", response_model=AgentCommandRead)
def complete_agent_command(
    command_id: str,
    payload: AgentCommandCompleteRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_agent_token),
):
    try:
        command = agent_command_service.complete_command(
            session,
            command_id=command_id,
            device_id=payload.device_id,
            lease_token=payload.lease_token,
            status=payload.status,
            error_message=payload.error_message,
            result_payload=payload.result_payload,
        )
        if command.command_type == "SESSION_OPEN":
            app_thread_service.complete_agent_session_open(
                session,
                command_id=command.id,
                result_payload=payload.result_payload,
            )
        elif command.command_type in {"SESSION_CLOSE", "TURN_START", "RUN_EXECUTE"}:
            agent_command_maintenance_service.apply_terminal_command_effects(
                session,
                command,
                result_payload=payload.result_payload,
            )
        session.refresh(command)
        return command
    except agent_command_service.AgentCommandServiceError as exc:
        raise_agent_command_error(exc)


@router.post("/agent/commands/{command_id}/events", response_model=AgentCommandEventsUploadRead)
def upload_agent_command_events(
    command_id: str,
    payload: AgentCommandEventsUploadRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_agent_token),
):
    try:
        agent_command_service.renew_command(
            session,
            command_id=command_id,
            device_id=payload.device_id,
            lease_token=payload.lease_token,
        )
        return agent_command_event_service.upload_command_events(
            session,
            command_id=command_id,
            device_id=payload.device_id,
            payload=payload,
        )
    except agent_command_service.AgentCommandServiceError as exc:
        raise_agent_command_error(exc)


@router.post("/agent/reconcile", response_model=AgentReconcileRead)
def reconcile_agent(
    payload: AgentReconcileRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_agent_token),
):
    try:
        return agent_reconciliation_service.reconcile_agent(session, payload)
    except agent_command_service.AgentCommandServiceError as exc:
        raise_agent_command_error(exc)


@router.post("/agent/runs/{run_id}/log-chunks", response_model=RunLogChunkUploadRead)
def upload_run_log_chunk(
    run_id: int,
    payload: RunLogChunkUpload,
    session: Session = Depends(get_session),
    _: None = Depends(require_agent_token),
):
    return run_log_service.upload_run_log_chunk(session, run_id, payload)


@router.post("/agent/runs/{run_id}/artifacts", response_model=RunArtifactUploadRead)
def upload_run_artifact(
    run_id: int,
    payload: RunArtifactUpload,
    session: Session = Depends(get_session),
    _: None = Depends(require_agent_token),
):
    return run_artifact_service.upload_run_artifact(session, run_id, payload)


def _workspace_lock_owner_id_for_session_command(session: Session, command) -> str | None:
    if command.aggregate_type == "app_thread" and command.aggregate_id:
        return str(command.aggregate_id)
    if command.aggregate_type != "app_turn" or not command.aggregate_id:
        return None
    try:
        app_turn_id = int(command.aggregate_id)
    except ValueError:
        return None
    app_turn = app_thread_service.get_app_turn_or_404(session, app_turn_id)
    return str(app_turn.app_thread_id)
