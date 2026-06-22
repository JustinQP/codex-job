from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from backend.db import get_session
from backend.dependencies import require_agent_token
from backend.schemas import (
    DeviceHeartbeat,
    DeviceRead,
    DeviceRegister,
    WorkspaceSyncRead,
    WorkspaceSyncRequest,
)
from backend.services import device_service, workspace_service


router = APIRouter()


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
