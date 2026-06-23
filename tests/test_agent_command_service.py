from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from backend.models import AgentCommand, AgentCommandStatus, Device, DeviceStatus, Workspace, utc_now
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


def add_workspace(
    session: Session,
    *,
    enabled: bool = True,
    device_id: str = "device-a",
    workspace_key: str = "repo",
) -> Workspace:
    workspace = Workspace(
        device_id=device_id,
        workspace_key=workspace_key,
        name=f"Repo {workspace_key}",
        path_label="codex-job",
        enabled=enabled,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(workspace)
    session.commit()
    session.refresh(workspace)
    return workspace


def add_command(session: Session, idempotency_key: str = "cmd-a") -> AgentCommand:
    add_device(session)
    command = AgentCommand(
        device_id="device-a",
        command_type="codex.exec",
        aggregate_type="run",
        aggregate_id="1",
        idempotency_key=idempotency_key,
        payload_json='{"prompt":"hello"}',
    )
    session.add(command)
    session.commit()
    session.refresh(command)
    return command


def test_create_command_reuses_same_idempotency_key_for_same_payload() -> None:
    session = make_session()
    try:
        add_device(session)
        workspace = add_workspace(session)

        first = agent_command_service.create_command(
            session,
            device_id="device-a",
            command_type="codex.exec",
            aggregate_type="run",
            aggregate_id="1",
            idempotency_key="retry-key",
            workspace_id=workspace.id,
            payload={"run_id": 1, "workspace_id": workspace.id, "options": {"model": "gpt-5"}},
        )
        second = agent_command_service.create_command(
            session,
            device_id="device-a",
            command_type="codex.exec",
            aggregate_type="run",
            aggregate_id="1",
            idempotency_key="retry-key",
            workspace_id=workspace.id,
            payload={"options": {"model": "gpt-5"}, "workspace_id": workspace.id, "run_id": 1},
        )

        assert second.id == first.id
        assert len(agent_command_service.list_commands_for_device(session, "device-a")) == 1
    finally:
        session.close()


def test_create_command_conflicting_payload_has_stable_error_code() -> None:
    session = make_session()
    try:
        add_device(session)
        agent_command_service.create_command(
            session,
            device_id="device-a",
            command_type="codex.exec",
            idempotency_key="same-key",
            payload={"run_id": 1},
        )

        with pytest.raises(agent_command_service.AgentCommandServiceError) as exc:
            agent_command_service.create_command(
                session,
                device_id="device-a",
                command_type="codex.exec",
                idempotency_key="same-key",
                payload={"run_id": 2},
            )

        assert exc.value.code == "agent_command_idempotency_conflict"
    finally:
        session.close()


def test_create_command_rejects_disabled_device() -> None:
    session = make_session()
    try:
        device = add_device(session)
        device.status = DeviceStatus.DISABLED
        session.add(device)
        session.commit()

        with pytest.raises(agent_command_service.AgentCommandServiceError) as exc:
            agent_command_service.create_command(
                session,
                device_id="device-a",
                command_type="codex.exec",
                idempotency_key="device-disabled",
                payload={"run_id": 1},
            )

        assert exc.value.code == "device_disabled"
    finally:
        session.close()


def test_create_command_rejects_disabled_or_foreign_workspace() -> None:
    session = make_session()
    try:
        add_device(session, "device-a")
        add_device(session, "device-b")
        disabled = add_workspace(session, enabled=False, device_id="device-a", workspace_key="disabled")
        foreign = add_workspace(session, enabled=True, device_id="device-b", workspace_key="foreign")

        for workspace in (disabled, foreign):
            with pytest.raises(agent_command_service.AgentCommandServiceError) as exc:
                agent_command_service.create_command(
                    session,
                    device_id="device-a",
                    command_type="codex.exec",
                    idempotency_key=f"bad-workspace-{workspace.id}",
                    workspace_id=workspace.id,
                    payload={"workspace_id": workspace.id},
                )
            assert exc.value.code == "workspace_unavailable"
    finally:
        session.close()


def test_create_command_rejects_payload_with_absolute_path() -> None:
    session = make_session()
    try:
        add_device(session)

        with pytest.raises(agent_command_service.AgentCommandServiceError) as exc:
            agent_command_service.create_command(
                session,
                device_id="device-a",
                command_type="codex.exec",
                idempotency_key="path-key",
                payload={"cwd": "C:\\repo"},
            )

        assert exc.value.code == "invalid_command_payload"
    finally:
        session.close()


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


def test_cancelled_command_is_not_overwritten_by_late_success_completion() -> None:
    session = make_session()
    try:
        command = add_command(session)
        claimed = agent_command_service.transition_command(
            session,
            command,
            AgentCommandStatus.CLAIMED,
            lease_token="lease-a",
            lease_expires_at=utc_now() + timedelta(seconds=30),
        )
        cancelled = agent_command_service.request_cancel_command(
            session,
            command_id=claimed.id,
        )
        completed = agent_command_service.complete_command(
            session,
            command_id=cancelled.id,
            device_id="device-a",
            lease_token="lease-a",
            status=AgentCommandStatus.SUCCESS,
        )

        assert completed.status == AgentCommandStatus.CANCELLED
        assert completed.last_error == "cancelled by user"
    finally:
        session.close()


def test_cancel_command_is_idempotent_for_terminal_command() -> None:
    session = make_session()
    try:
        command = add_command(session)
        cancelled = agent_command_service.request_cancel_command(
            session,
            command_id=command.id,
        )
        repeated = agent_command_service.request_cancel_command(
            session,
            command_id=command.id,
        )

        assert repeated.id == cancelled.id
        assert repeated.status == AgentCommandStatus.PENDING
        assert repeated.cancel_requested is True
        assert repeated.cancel_requested_at == cancelled.cancel_requested_at
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
