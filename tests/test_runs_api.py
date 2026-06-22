from __future__ import annotations

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from backend.db import get_session
from backend.main import app
from backend.models import Device, DeviceStatus, Project, Task, TaskStatus, Workspace, utc_now


def make_client() -> Generator[tuple[TestClient, Session], None, None]:
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


def test_create_run_binds_device_from_workspace_and_ignores_client_device_id() -> None:
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
                "prompt": "run on workspace device",
                "client_request_id": "client-1",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["workspace_id"] == workspace.id
        assert body["device_id"] == "device-a"
        assert body["device_display_name"] == "device-a"
        assert body["device_status"] == "ONLINE"
        assert body["workspace_name"] == "Repo"
        assert body["workspace_path_label"] == "codex-job"
        assert body["client_request_id"] == "client-1"


def test_create_run_rejects_disabled_workspace_and_offline_device() -> None:
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        add_device(session, "device-b", status=DeviceStatus.OFFLINE)
        disabled_workspace = add_workspace(session, "device-a", enabled=False)
        offline_workspace = add_workspace(session, "device-b")

        disabled_response = client.post(
            "/runs",
            json={
                "project_id": project.id,
                "workspace_id": disabled_workspace.id,
                "prompt": "disabled workspace",
            },
        )
        offline_response = client.post(
            "/runs",
            json={
                "project_id": project.id,
                "workspace_id": offline_workspace.id,
                "prompt": "offline device",
            },
        )

        assert disabled_response.status_code == 400
        assert disabled_response.json()["detail"] == "workspace is disabled"
        assert offline_response.status_code == 409
        assert offline_response.json()["detail"] == "device is offline"


def test_legacy_task_history_without_binding_is_still_readable() -> None:
    for client, session in make_client():
        project = add_project(session)
        task = Task(
            project_id=project.id,
            prompt="legacy task",
            status=TaskStatus.SUCCESS,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(task)
        session.commit()
        session.refresh(task)

        response = client.get(f"/tasks/{task.id}")

        assert response.status_code == 200
        assert response.json()["device_id"] is None
        assert response.json()["workspace_id"] is None
        assert response.json()["command_id"] is None


def test_list_tasks_can_filter_runs_by_workspace() -> None:
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        add_device(session, "device-b")
        workspace_a = add_workspace(session, "device-a")
        workspace_b = add_workspace(session, "device-b")
        run_a = client.post(
            "/runs",
            json={
                "project_id": project.id,
                "workspace_id": workspace_a.id,
                "prompt": "run a",
                "client_request_id": "workspace-filter-a",
            },
        ).json()
        run_b = client.post(
            "/runs",
            json={
                "project_id": project.id,
                "workspace_id": workspace_b.id,
                "prompt": "run b",
                "client_request_id": "workspace-filter-b",
            },
        ).json()

        filtered = client.get(f"/tasks?workspace_id={workspace_a.id}&limit=20")
        all_runs = client.get("/tasks?limit=20")

        assert filtered.status_code == 200
        assert [item["id"] for item in filtered.json()] == [run_a["id"]]
        assert {item["id"] for item in all_runs.json()} >= {run_a["id"], run_b["id"]}
