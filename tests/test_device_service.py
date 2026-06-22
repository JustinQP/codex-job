from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from backend.models import Device, DeviceStatus, utc_now
from backend.schemas import DeviceHeartbeat, DeviceRegister
from backend.services import device_service


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def register_payload(device_id: str = "device-a") -> DeviceRegister:
    return DeviceRegister(
        device_id=device_id,
        display_name="Desk A",
        hostname="host-a",
        os_name="Windows",
        agent_version="0.1.0",
        capabilities_json='{"codex":true}',
    )


def test_register_device_creates_and_repeated_register_updates() -> None:
    session = make_session()
    try:
        created = device_service.register_device(session, register_payload())
        updated = device_service.register_device(
            session,
            DeviceRegister(
                device_id="device-a",
                display_name="Desk A2",
                hostname="host-a2",
                os_name="Windows",
                agent_version="0.2.0",
                capabilities_json='{"codex":true,"app_server":true}',
            ),
        )

        assert created.device_id == "device-a"
        assert updated.device_id == "device-a"
        assert updated.display_name == "Desk A2"
        assert updated.hostname == "host-a2"
        assert updated.agent_version == "0.2.0"
        assert updated.status == DeviceStatus.ONLINE
        assert updated.lease_expires_at is not None
        assert len(device_service.list_devices(session)) == 1
    finally:
        session.close()


def test_heartbeat_updates_online_lease() -> None:
    session = make_session()
    try:
        device = device_service.register_device(session, register_payload())
        first_lease = device.lease_expires_at

        heartbeat = device_service.heartbeat_device(
            session,
            DeviceHeartbeat(
                device_id="device-a",
                display_name="Desk A heartbeat",
                capabilities_json='{"codex":false}',
            ),
        )

        assert heartbeat.status == DeviceStatus.ONLINE
        assert heartbeat.display_name == "Desk A heartbeat"
        assert heartbeat.capabilities_json == '{"codex":false}'
        assert heartbeat.lease_expires_at is not None
        assert first_lease is None or heartbeat.lease_expires_at >= first_lease
    finally:
        session.close()


def test_mark_offline_devices_updates_expired_online_only() -> None:
    session = make_session()
    try:
        now = utc_now()
        expired = Device(
            device_id="expired",
            display_name="Expired",
            hostname="host",
            os_name="Windows",
            agent_version="0.1.0",
            status=DeviceStatus.ONLINE,
            last_heartbeat_at=now - timedelta(minutes=5),
            lease_expires_at=now - timedelta(seconds=1),
            created_at=now,
            updated_at=now,
        )
        fresh = Device(
            device_id="fresh",
            display_name="Fresh",
            hostname="host",
            os_name="Windows",
            agent_version="0.1.0",
            status=DeviceStatus.ONLINE,
            last_heartbeat_at=now,
            lease_expires_at=now + timedelta(minutes=1),
            created_at=now,
            updated_at=now,
        )
        disabled = Device(
            device_id="disabled",
            display_name="Disabled",
            hostname="host",
            os_name="Windows",
            agent_version="0.1.0",
            status=DeviceStatus.DISABLED,
            last_heartbeat_at=now - timedelta(minutes=5),
            lease_expires_at=now - timedelta(seconds=1),
            created_at=now,
            updated_at=now,
        )
        session.add(expired)
        session.add(fresh)
        session.add(disabled)
        session.commit()

        count = device_service.mark_offline_devices(session)

        assert count == 1
        assert session.get(Device, "expired").status == DeviceStatus.OFFLINE
        assert session.get(Device, "fresh").status == DeviceStatus.ONLINE
        assert session.get(Device, "disabled").status == DeviceStatus.DISABLED
    finally:
        session.close()


def test_disabled_device_cannot_heartbeat_or_auto_recover() -> None:
    session = make_session()
    try:
        device = device_service.register_device(session, register_payload())
        device.status = DeviceStatus.DISABLED
        session.add(device)
        session.commit()

        with pytest.raises(HTTPException) as exc:
            device_service.heartbeat_device(
                session,
                DeviceHeartbeat(device_id="device-a"),
            )
        repeated = device_service.register_device(session, register_payload())

        assert exc.value.status_code == 403
        assert repeated.status == DeviceStatus.DISABLED
    finally:
        session.close()


def test_unknown_device_heartbeat_returns_404() -> None:
    session = make_session()
    try:
        with pytest.raises(HTTPException) as exc:
            device_service.heartbeat_device(session, DeviceHeartbeat(device_id="missing"))

        assert exc.value.status_code == 404
    finally:
        session.close()
