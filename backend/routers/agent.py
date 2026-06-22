from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from backend.db import get_session
from backend.dependencies import require_agent_token
from backend.schemas import (
    AgentCommandClaimRequest,
    AgentCommandCompleteRequest,
    AgentCommandLeaseRequest,
    AgentCommandRead,
    DeviceHeartbeat,
    DeviceRead,
    DeviceRegister,
    WorkspaceSyncRead,
    WorkspaceSyncRequest,
)
from backend.services import agent_command_service, device_service, workspace_service


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
        return agent_command_service.ack_command(
            session,
            command_id=command_id,
            device_id=payload.device_id,
            lease_token=payload.lease_token,
        )
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
        return agent_command_service.renew_command(
            session,
            command_id=command_id,
            device_id=payload.device_id,
            lease_token=payload.lease_token,
        )
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
        return agent_command_service.complete_command(
            session,
            command_id=command_id,
            device_id=payload.device_id,
            lease_token=payload.lease_token,
            status=payload.status,
            error_message=payload.error_message,
        )
    except agent_command_service.AgentCommandServiceError as exc:
        raise_agent_command_error(exc)
