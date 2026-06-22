from __future__ import annotations

from datetime import timedelta

from fastapi import HTTPException, status
from sqlmodel import Session, select

from backend.models import Device, DeviceStatus, utc_now
from backend.schemas import DeviceHeartbeat, DeviceRegister


DEVICE_LEASE_SECONDS = 60


def register_device(session: Session, payload: DeviceRegister) -> Device:
    now = utc_now()
    lease_expires_at = now + timedelta(seconds=DEVICE_LEASE_SECONDS)
    device = session.get(Device, payload.device_id)
    if device is None:
        device = Device(
            device_id=payload.device_id,
            display_name=payload.display_name,
            hostname=payload.hostname,
            os_name=payload.os_name,
            agent_version=payload.agent_version,
            capabilities_json=payload.capabilities_json,
            status=DeviceStatus.ONLINE,
            last_heartbeat_at=now,
            lease_expires_at=lease_expires_at,
            created_at=now,
            updated_at=now,
        )
    else:
        device.display_name = payload.display_name
        device.hostname = payload.hostname
        device.os_name = payload.os_name
        device.agent_version = payload.agent_version
        device.capabilities_json = payload.capabilities_json
        if device.status != DeviceStatus.DISABLED:
            device.status = DeviceStatus.ONLINE
            device.last_heartbeat_at = now
            device.lease_expires_at = lease_expires_at
        device.updated_at = now
    session.add(device)
    session.commit()
    session.refresh(device)
    return device


def heartbeat_device(session: Session, payload: DeviceHeartbeat) -> Device:
    device = session.get(Device, payload.device_id)
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="device not found",
        )
    if device.status == DeviceStatus.DISABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="device is disabled",
        )

    now = utc_now()
    if payload.display_name is not None:
        device.display_name = payload.display_name
    if payload.hostname is not None:
        device.hostname = payload.hostname
    if payload.os_name is not None:
        device.os_name = payload.os_name
    if payload.agent_version is not None:
        device.agent_version = payload.agent_version
    if payload.capabilities_json is not None:
        device.capabilities_json = payload.capabilities_json
    device.status = DeviceStatus.ONLINE
    device.last_heartbeat_at = now
    device.lease_expires_at = now + timedelta(seconds=DEVICE_LEASE_SECONDS)
    device.updated_at = now
    session.add(device)
    session.commit()
    session.refresh(device)
    return device


def mark_offline_devices(session: Session) -> int:
    now = utc_now()
    devices = session.exec(
        select(Device).where(
            Device.status == DeviceStatus.ONLINE,
            Device.lease_expires_at.is_not(None),
            Device.lease_expires_at < now,
        )
    ).all()
    for device in devices:
        device.status = DeviceStatus.OFFLINE
        device.updated_at = now
        session.add(device)
    if devices:
        session.commit()
    return len(devices)


def list_devices(session: Session) -> list[Device]:
    mark_offline_devices(session)
    return list(session.exec(select(Device).order_by(Device.display_name)).all())


def get_device_or_404(session: Session, device_id: str) -> Device:
    mark_offline_devices(session)
    device = session.get(Device, device_id)
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="device not found",
        )
    return device
