from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from backend.models import Device, Workspace, utc_now
from backend.schemas import WorkspaceUpsert
from backend.services import workspace_service


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def add_device(session: Session, device_id: str) -> Device:
    device = Device(
        device_id=device_id,
        display_name=f"Device {device_id}",
        hostname="host",
        os_name="Windows",
        agent_version="0.1.0",
        created_at=utc_now(),
        updated_at=utc_now(),
        last_heartbeat_at=utc_now(),
    )
    session.add(device)
    session.commit()
    session.refresh(device)
    return device


def workspace_payload(
    *,
    device_id: str = "device-a",
    workspace_key: str = "repo",
    enabled: bool = True,
) -> WorkspaceUpsert:
    return WorkspaceUpsert(
        device_id=device_id,
        workspace_key=workspace_key,
        name="Repo",
        path_label="codex-job",
        enabled=enabled,
        default_model="gpt-5",
        default_reasoning_effort="high",
        default_sandbox="workspace-write",
        default_approval_policy="on-request",
        require_clean_worktree=True,
    )


def test_upsert_workspace_creates_and_updates_for_same_device_key() -> None:
    session = make_session()
    try:
        add_device(session, "device-a")

        created = workspace_service.upsert_workspace(session, workspace_payload())
        updated = workspace_service.upsert_workspace(
            session,
            WorkspaceUpsert(
                device_id="device-a",
                workspace_key="repo",
                name="Repo Updated",
                path_label="repo-label",
                enabled=False,
            ),
        )

        assert created.id == updated.id
        assert updated.name == "Repo Updated"
        assert updated.path_label == "repo-label"
        assert updated.enabled is False
        assert len(workspace_service.list_workspaces(session, device_id="device-a")) == 1
    finally:
        session.close()


def test_same_workspace_key_allowed_on_different_devices() -> None:
    session = make_session()
    try:
        add_device(session, "device-a")
        add_device(session, "device-b")

        a = workspace_service.upsert_workspace(
            session,
            workspace_payload(device_id="device-a", workspace_key="repo"),
        )
        b = workspace_service.upsert_workspace(
            session,
            workspace_payload(device_id="device-b", workspace_key="repo"),
        )

        assert a.id != b.id
        assert {workspace.device_id for workspace in workspace_service.list_workspaces(session)} == {
            "device-a",
            "device-b",
        }
    finally:
        session.close()


def test_workspace_must_bind_existing_device() -> None:
    session = make_session()
    try:
        with pytest.raises(HTTPException) as exc:
            workspace_service.upsert_workspace(session, workspace_payload(device_id="missing"))

        assert exc.value.status_code == 404
    finally:
        session.close()


def test_disabled_workspace_cannot_be_used_for_new_execution() -> None:
    session = make_session()
    try:
        add_device(session, "device-a")
        workspace = workspace_service.upsert_workspace(
            session,
            workspace_payload(enabled=False),
        )

        with pytest.raises(HTTPException) as exc:
            workspace_service.ensure_workspace_enabled(session, workspace.id)

        assert exc.value.status_code == 400
        assert exc.value.detail == "workspace is disabled"
    finally:
        session.close()


def test_database_enforces_unique_device_workspace_key() -> None:
    session = make_session()
    try:
        add_device(session, "device-a")
        now = utc_now()
        session.add(
            Workspace(
                device_id="device-a",
                workspace_key="repo",
                name="One",
                path_label="one",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            Workspace(
                device_id="device-a",
                workspace_key="repo",
                name="Two",
                path_label="two",
                created_at=now,
                updated_at=now,
            )
        )

        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.close()
