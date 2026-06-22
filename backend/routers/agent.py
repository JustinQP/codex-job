from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from backend.db import get_session
from backend.dependencies import require_agent_token
from backend.schemas import DeviceHeartbeat, DeviceRead, DeviceRegister
from backend.services import device_service


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
