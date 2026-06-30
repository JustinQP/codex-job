from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from backend.db import get_session
from backend.dependencies import require_api_token
from backend.schemas import DeviceRead, DeviceUpdate
from backend.services import device_service


router = APIRouter()


@router.get("/devices", response_model=list[DeviceRead])
def list_devices(
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return device_service.list_devices(session)


@router.get("/devices/{device_id}", response_model=DeviceRead)
def get_device(
    device_id: str,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return device_service.get_device_or_404(session, device_id)


@router.patch("/devices/{device_id}", response_model=DeviceRead)
def update_device(
    device_id: str,
    payload: DeviceUpdate,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return device_service.update_device(
        session,
        device_id,
        display_name=payload.display_name,
    )


@router.post("/devices/{device_id}/disable", response_model=DeviceRead)
def disable_device(
    device_id: str,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return device_service.disable_device(session, device_id)


@router.delete("/devices/{device_id}", response_model=DeviceRead)
def delete_device(
    device_id: str,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return device_service.delete_device(session, device_id)
