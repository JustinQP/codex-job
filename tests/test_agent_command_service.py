from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from backend.models import AgentCommand, AgentCommandStatus, Device, DeviceStatus, utc_now
from backend.services import agent_command_service


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def add_device(session: Session, device_id: str = "device-a") -> Device:
    now = utc_now()
    device = Device(
        device_id=device_id,
        display_name="Desk A",
        hostname="host-a",
        os_name="Windows",
        agent_version="0.1.0",
        status=DeviceStatus.ONLINE,
        last_heartbeat_at=now,
        lease_expires_at=now + timedelta(minutes=1),
        created_at=now,
        updated_at=now,
    )
    session.add(device)
    session.commit()
    return device


def add_command(session: Session, idempotency_key: str = "cmd-a") -> AgentCommand:
    add_device(session)
    command = AgentCommand(
        device_id="device-a",
        command_type="codex.exec",
        aggregate_type="task",
        aggregate_id="1",
        idempotency_key=idempotency_key,
        payload_json='{"prompt":"hello"}',
    )
    session.add(command)
    session.commit()
    session.refresh(command)
    return command


def test_agent_command_claim_run_success_transition_sets_fields() -> None:
    session = make_session()
    try:
        command = add_command(session)
        lease_expires_at = utc_now() + timedelta(seconds=30)

        claimed = agent_command_service.transition_command(
            session,
            command,
            AgentCommandStatus.CLAIMED,
            lease_token="lease-a",
            lease_expires_at=lease_expires_at,
        )
        running = agent_command_service.transition_command(
            session,
            claimed,
            AgentCommandStatus.RUNNING,
        )
        completed = agent_command_service.transition_command(
            session,
            running,
            AgentCommandStatus.SUCCESS,
        )

        assert completed.status == AgentCommandStatus.SUCCESS
        assert completed.attempt_count == 1
        assert completed.claimed_at is not None
        assert completed.completed_at is not None
        assert completed.lease_token is None
        assert completed.lease_expires_at is None
    finally:
        session.close()


def test_agent_command_rejects_invalid_transition_from_terminal_status() -> None:
    session = make_session()
    try:
        command = add_command(session)
        completed = agent_command_service.transition_command(
            session,
            command,
            AgentCommandStatus.CANCELLED,
        )

        with pytest.raises(agent_command_service.AgentCommandStateError):
            agent_command_service.transition_command(
                session,
                completed,
                AgentCommandStatus.RUNNING,
            )
    finally:
        session.close()


def test_agent_command_repeated_terminal_completion_is_idempotent() -> None:
    session = make_session()
    try:
        command = add_command(session)
        claimed = agent_command_service.transition_command(
            session,
            command,
            AgentCommandStatus.CLAIMED,
            lease_token="lease-a",
        )
        completed = agent_command_service.transition_command(
            session,
            claimed,
            AgentCommandStatus.SUCCESS,
        )
        repeated = agent_command_service.transition_command(
            session,
            completed,
            AgentCommandStatus.SUCCESS,
        )

        assert repeated.id == completed.id
        assert repeated.status == AgentCommandStatus.SUCCESS
        assert repeated.completed_at == completed.completed_at
    finally:
        session.close()


def test_agent_command_rejects_pending_to_success_without_claim() -> None:
    session = make_session()
    try:
        command = add_command(session)

        with pytest.raises(agent_command_service.AgentCommandStateError):
            agent_command_service.transition_command(
                session,
                command,
                AgentCommandStatus.SUCCESS,
            )
    finally:
        session.close()


def test_agent_command_idempotency_key_is_unique() -> None:
    session = make_session()
    try:
        add_command(session, "same-key")
        duplicate = AgentCommand(
            device_id="device-a",
            command_type="codex.exec",
            idempotency_key="same-key",
        )
        session.add(duplicate)

        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.close()


def test_list_commands_for_device_filters_by_status() -> None:
    session = make_session()
    try:
        command = add_command(session)
        agent_command_service.transition_command(
            session,
            command,
            AgentCommandStatus.CANCELLED,
        )
        pending = AgentCommand(
            device_id="device-a",
            command_type="codex.exec",
            idempotency_key="pending-key",
        )
        session.add(pending)
        session.commit()

        commands = agent_command_service.list_commands_for_device(
            session,
            "device-a",
            status=AgentCommandStatus.PENDING,
        )

        assert [item.idempotency_key for item in commands] == ["pending-key"]
    finally:
        session.close()
