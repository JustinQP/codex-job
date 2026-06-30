from __future__ import annotations

import json
import os
from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine, select
from sqlmodel.pool import StaticPool

from backend.db import get_session
from backend.main import app
from backend.models import AgentCommand, Device, DeviceStatus, Project, Run, RunStatus, Workspace, WorkspaceExecutionLock, utc_now
import pytest

from backend.services import agent_command_service, run_service
from backend.schemas import RunCreate


def make_client(*, include_api_token: bool = True) -> Generator[tuple[TestClient, Session], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    session = Session(engine)

    def override_get_session() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            if include_api_token:
                client.headers.update({"X-API-Token": os.environ["API_TOKEN"]})
            yield client, session
    finally:
        app.dependency_overrides.clear()
        session.close()


def add_project(session: Session) -> Project:
    project = Project(name="demo", path="E:\\demo", enabled=True, created_at=utc_now(), updated_at=utc_now())
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def add_device(session: Session, device_id: str, *, status: DeviceStatus = DeviceStatus.ONLINE) -> Device:
    now = utc_now()
    device = Device(
        device_id=device_id,
        display_name=device_id,
        hostname=device_id,
        os_name="Windows",
        agent_version="0.1.0",
        status=status,
        last_heartbeat_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(device)
    session.commit()
    session.refresh(device)
    return device


def add_workspace(session: Session, device_id: str, *, enabled: bool = True) -> Workspace:
    workspace = Workspace(
        device_id=device_id,
        workspace_key=f"repo-{device_id}",
        name="Repo",
        path_label="codex-job",
        enabled=enabled,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(workspace)
    session.commit()
    session.refresh(workspace)
    return workspace


def test_create_run_generates_device_scoped_agent_command() -> None:
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        add_device(session, "device-b")
        workspace = add_workspace(session, "device-a")

        response = client.post(
            "/runs",
            json={
                "project_id": project.id,
                "workspace_id": workspace.id,
                "device_id": "device-b",
                "prompt": "execute through agent",
                "client_request_id": "run-client-1",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["workspace_id"] == workspace.id
        assert body["device_id"] == "device-a"
        assert body["run_type"] == "IMPLEMENT"
        assert body["log_url"] == f"/runs/{body['id']}/log"
        command = session.get(AgentCommand, body["command_id"])
        assert command is not None
        assert command.command_type == "RUN_EXECUTE"
        assert command.aggregate_type == "run"
        assert command.aggregate_id == str(body["id"])
        payload = json.loads(command.payload_json)
        assert payload["run_id"] == body["id"]
        assert payload["workspace_key"] == workspace.workspace_key
        assert "cwd" not in payload
        assert "project_path" not in payload


def test_run_rejects_workspace_not_bound_to_project() -> None:
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        add_device(session, "device-b")
        workspace_a = add_workspace(session, "device-a")
        workspace_b = add_workspace(session, "device-b")
        first = client.post(
            "/runs",
            json={"project_id": project.id, "workspace_id": workspace_a.id, "prompt": "bind"},
        )
        second = client.post(
            "/runs",
            json={"project_id": project.id, "workspace_id": workspace_b.id, "prompt": "wrong"},
        )

        assert first.status_code == 200
        assert second.status_code == 409
        assert second.json()["detail"]["code"] == "project_workspace_mismatch"


def test_create_run_rolls_back_when_command_creation_fails(monkeypatch) -> None:
    for _client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")

        def fail_create_command(*args, **kwargs):
            raise agent_command_service.AgentCommandServiceError("boom", "boom")

        monkeypatch.setattr(agent_command_service, "create_command", fail_create_command)

        with pytest.raises(agent_command_service.AgentCommandServiceError):
            run_service.create_run(
                session,
                RunCreate(project_id=project.id, workspace_id=workspace.id, prompt="should rollback"),
            )

        assert len(session.exec(select(Run)).all()) == 0
        assert len(session.exec(select(WorkspaceExecutionLock)).all()) == 0


def test_create_run_rejects_disabled_workspace_and_offline_device() -> None:
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        add_device(session, "device-b", status=DeviceStatus.OFFLINE)
        disabled_workspace = add_workspace(session, "device-a", enabled=False)
        offline_workspace = add_workspace(session, "device-b")

        disabled_response = client.post(
            "/runs",
            json={"project_id": project.id, "workspace_id": disabled_workspace.id, "prompt": "disabled workspace"},
        )
        offline_response = client.post(
            "/runs",
            json={"project_id": project.id, "workspace_id": offline_workspace.id, "prompt": "offline device"},
        )

        assert disabled_response.status_code == 400
        assert disabled_response.json()["detail"] == "workspace is disabled"
        assert offline_response.status_code == 409
        assert offline_response.json()["detail"] == "device is offline"


def test_list_runs_can_filter_by_workspace() -> None:
    for client, session in make_client():
        project_a = add_project(session)
        project_b = add_project(session)
        add_device(session, "device-a")
        add_device(session, "device-b")
        workspace_a = add_workspace(session, "device-a")
        workspace_b = add_workspace(session, "device-b")
        run_a = client.post(
            "/runs",
            json={"project_id": project_a.id, "workspace_id": workspace_a.id, "prompt": "run a", "client_request_id": "filter-a"},
        ).json()
        run_b = client.post(
            "/runs",
            json={"project_id": project_b.id, "workspace_id": workspace_b.id, "prompt": "run b", "client_request_id": "filter-b"},
        ).json()

        filtered = client.get(f"/runs?workspace_id={workspace_a.id}&limit=20")
        all_runs = client.get("/runs?limit=20")

        assert filtered.status_code == 200
        assert [item["id"] for item in filtered.json()] == [run_a["id"]]
        assert {item["id"] for item in all_runs.json()} >= {run_a["id"], run_b["id"]}


def test_cancel_run_requests_cancel_and_keeps_workspace_lock_until_agent_completes(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")
        created = client.post(
            "/runs",
            json={"project_id": project.id, "workspace_id": workspace.id, "prompt": "cancel me"},
        ).json()
        command = session.get(AgentCommand, created["command_id"])
        claimed = client.post(
            "/agent/commands/claim",
            headers={"X-Agent-Token": "agent-secret"},
            json={"device_id": "device-a", "claim_request_id": "claim-run"},
        ).json()
        lease = {"device_id": "device-a", "lease_token": claimed["lease_token"]}
        ack = client.post(f"/agent/commands/{command.id}/ack", headers={"X-Agent-Token": "agent-secret"}, json=lease)
        assert ack.status_code == 200

        response = client.post(f"/runs/{created['id']}/cancel")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == RunStatus.RUNNING.value
        assert body["cancel_requested"] is True
        assert session.get(WorkspaceExecutionLock, 1) is not None
        command = session.get(AgentCommand, body["command_id"])
        assert command is not None
        assert command.cancel_requested is True
        assert command.lease_token == claimed["lease_token"]

        complete = client.post(
            f"/agent/commands/{command.id}/complete",
            headers={"X-Agent-Token": "agent-secret"},
            json={**lease, "status": "CANCELLED", "error_message": "run cancelled"},
        )
        assert complete.status_code == 200
        final = client.get(f"/runs/{created['id']}").json()
        assert final["status"] == RunStatus.CANCELLED.value
        assert session.get(WorkspaceExecutionLock, 1) is None


def test_run_ack_marks_run_running(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")
        created = client.post(
            "/runs",
            json={"project_id": project.id, "workspace_id": workspace.id, "prompt": "run me"},
        ).json()
        claim = client.post(
            "/agent/commands/claim",
            headers={"X-Agent-Token": "agent-secret"},
            json={"device_id": "device-a", "claim_request_id": "claim-run"},
        ).json()
        ack = client.post(
            f"/agent/commands/{created['command_id']}/ack",
            headers={"X-Agent-Token": "agent-secret"},
            json={"device_id": "device-a", "lease_token": claim["lease_token"]},
        )

        assert ack.status_code == 200
        running = client.get(f"/runs/{created['id']}").json()
        assert running["status"] == RunStatus.RUNNING.value
        assert running["started_at"] is not None


def test_rerun_creates_new_run_and_agent_command() -> None:
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")
        original = client.post(
            "/runs",
            json={"project_id": project.id, "workspace_id": workspace.id, "prompt": "rerun me"},
        ).json()
        db_run = session.get(Run, original["id"])
        db_run.status = RunStatus.SUCCESS
        session.add(db_run)
        session.commit()
        lock = session.get(WorkspaceExecutionLock, 1)
        session.delete(lock)
        session.commit()

        response = client.post(f"/runs/{original['id']}/rerun")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] != original["id"]
        assert body["prompt"] == "rerun me"
        assert body["command_id"]


def test_run_templates_are_exposed_with_run_type() -> None:
    for client, _session in make_client():
        response = client.get("/run-templates")

        assert response.status_code == 200
        run_types = {item["run_type"] for item in response.json()}
        assert {"PLAN", "IMPLEMENT"} <= run_types
