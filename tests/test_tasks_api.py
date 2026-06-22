from __future__ import annotations

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from backend.main import app
from backend.db import get_session
from backend.models import AgentCommandStatus, Project, RunnerRecord, Task, TaskStatus, TaskType, utc_now
from backend.services import agent_command_service
from tests.test_runs_api import add_device, add_workspace


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


def add_project(session: Session, *, enabled: bool = True) -> Project:
    project = Project(
        name="demo",
        path="E:\\demo",
        enabled=enabled,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def test_project_create_and_list_api_uses_path_label(tmp_path) -> None:
    for client, session in make_client():
        del session
        project_dir = tmp_path / "demo-project"
        project_dir.mkdir()

        created = client.post(
            "/projects",
            json={
                "name": " Demo Project ",
                "path": str(project_dir),
                "test_command": "pytest -q",
                "smoke_check_command": "python -m compileall backend",
                "default_branch": "main",
                "require_clean_worktree": True,
            },
        )
        listed = client.get("/projects")

        assert created.status_code == 200
        created_body = created.json()
        assert created_body["name"] == "Demo Project"
        assert created_body["path_label"] == "demo-project"
        assert created_body["test_command"] == "pytest -q"
        assert created_body["smoke_check_command"] == "python -m compileall backend"
        assert created_body["default_branch"] == "main"
        assert created_body["require_clean_worktree"] is True
        assert listed.status_code == 200
        assert [project["id"] for project in listed.json()] == [created_body["id"]]


def add_task(
    session: Session,
    *,
    project_id: int,
    prompt: str,
    task_status: TaskStatus,
    timeout_seconds: int = 7200,
) -> Task:
    task = Task(
        project_id=project_id,
        prompt=prompt,
        status=task_status,
        timeout_seconds=timeout_seconds,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def test_list_tasks_supports_filters_and_limit() -> None:
    for client, session in make_client():
        project_1 = add_project(session)
        project_2 = add_project(session)
        add_task(
            session,
            project_id=project_1.id,
            prompt="pending one",
            task_status=TaskStatus.PENDING,
        )
        add_task(
            session,
            project_id=project_1.id,
            prompt="success one",
            task_status=TaskStatus.SUCCESS,
        )
        add_task(
            session,
            project_id=project_2.id,
            prompt="pending two",
            task_status=TaskStatus.PENDING,
        )

        response = client.get(
            f"/tasks?project_id={project_1.id}&status=PENDING&limit=1"
        )

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["project_id"] == project_1.id
        assert body[0]["status"] == "PENDING"
        assert "log_file" not in body[0]
        assert body[0]["log_url"].startswith("/tasks/")


def test_rerun_creates_new_pending_task_with_new_artifact_urls() -> None:
    for client, session in make_client():
        project = add_project(session)
        original = add_task(
            session,
            project_id=project.id,
            prompt="repeat me",
            task_status=TaskStatus.FAILED,
            timeout_seconds=120,
        )

        response = client.post(f"/tasks/{original.id}/rerun")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] != original.id
        assert body["project_id"] == project.id
        assert body["prompt"] == "repeat me"
        assert body["timeout_seconds"] == 120
        assert body["status"] == "PENDING"
        assert body["log_url"] == f"/tasks/{body['id']}/log"


def test_rerun_preserves_execution_config() -> None:
    for client, session in make_client():
        project = add_project(session)
        runner = RunnerRecord(
            runner_id="runner-a",
            pid=1,
            hostname="host",
            status="ONLINE",
            registered_at=utc_now(),
            last_heartbeat_at=utc_now(),
        )
        session.add(runner)
        session.commit()
        original = Task(
            project_id=project.id,
            prompt="repeat configured task",
            status=TaskStatus.FAILED,
            timeout_seconds=120,
            assigned_runner_id="runner-a",
            model="gpt-5-codex",
            reasoning_effort="high",
            sandbox="read-only",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(original)
        session.commit()
        session.refresh(original)

        response = client.post(f"/tasks/{original.id}/rerun")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] != original.id
        assert body["assigned_runner_id"] == "runner-a"
        assert body["model"] == "gpt-5-codex"
        assert body["reasoning_effort"] == "high"
        assert body["sandbox"] == "read-only"


def test_create_task_rejects_timeout_outside_bounds() -> None:
    for client, session in make_client():
        project = add_project(session)

        too_short = client.post(
            "/tasks",
            json={
                "project_id": project.id,
                "prompt": "short",
                "timeout_seconds": 29,
            },
        )
        too_long = client.post(
            "/tasks",
            json={
                "project_id": project.id,
                "prompt": "long",
                "timeout_seconds": 21601,
            },
        )
        valid = client.post(
            "/tasks",
            json={
                "project_id": project.id,
                "prompt": "valid",
                "timeout_seconds": 30,
            },
        )

        assert too_short.status_code == 422
        assert too_long.status_code == 422
        assert valid.status_code == 200
        assert valid.json()["timeout_seconds"] == 30


def test_create_task_supports_assigned_runner_id() -> None:
    for client, session in make_client():
        project = add_project(session)
        runner = RunnerRecord(
            runner_id="runner-a",
            pid=1,
            hostname="host",
            status="ONLINE",
            registered_at=utc_now(),
            last_heartbeat_at=utc_now(),
        )
        session.add(runner)
        session.commit()

        response = client.post(
            "/tasks",
            json={
                "project_id": project.id,
                "prompt": "assigned",
                "assigned_runner_id": "runner-a",
            },
        )

        assert response.status_code == 200
        assert response.json()["assigned_runner_id"] == "runner-a"


def test_create_task_rejects_unknown_assigned_runner_id() -> None:
    for client, session in make_client():
        project = add_project(session)

        response = client.post(
            "/tasks",
            json={
                "project_id": project.id,
                "prompt": "assigned",
                "assigned_runner_id": "missing-runner",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "assigned runner not found: missing-runner"


def test_create_task_inherits_project_default_runner() -> None:
    for client, session in make_client():
        project = add_project(session)
        runner = RunnerRecord(
            runner_id="runner-default",
            pid=1,
            hostname="host",
            status="ONLINE",
            registered_at=utc_now(),
            last_heartbeat_at=utc_now(),
        )
        session.add(runner)
        session.commit()
        project.default_runner_id = "runner-default"
        session.add(project)
        session.commit()

        response = client.post(
            "/tasks",
            json={
                "project_id": project.id,
                "prompt": "default runner",
            },
        )

        assert response.status_code == 200
        assert response.json()["assigned_runner_id"] == "runner-default"


def test_create_task_inherits_project_codex_defaults() -> None:
    for client, session in make_client():
        project = add_project(session)
        project.default_model = "gpt-5"
        project.default_reasoning_effort = "high"
        project.default_sandbox = "read-only"
        session.add(project)
        session.commit()

        inherited = client.post(
            "/tasks",
            json={
                "project_id": project.id,
                "prompt": "inherit config",
            },
        )
        overridden = client.post(
            "/tasks",
            json={
                "project_id": project.id,
                "prompt": "override config",
                "model": "gpt-5-codex",
                "reasoning_effort": "medium",
                "sandbox": "workspace-write",
            },
        )

        assert inherited.status_code == 200
        assert inherited.json()["model"] == "gpt-5"
        assert inherited.json()["reasoning_effort"] == "high"
        assert inherited.json()["sandbox"] == "read-only"
        assert overridden.status_code == 200
        assert overridden.json()["model"] == "gpt-5-codex"
        assert overridden.json()["reasoning_effort"] == "medium"
        assert overridden.json()["sandbox"] == "workspace-write"


def test_create_task_defaults_sandbox_to_workspace_write() -> None:
    for client, session in make_client():
        project = add_project(session)

        response = client.post(
            "/tasks",
            json={
                "project_id": project.id,
                "prompt": "default sandbox",
            },
        )

        assert response.status_code == 200
        assert response.json()["sandbox"] == "workspace-write"


def test_cancel_pending_task_marks_cancelled() -> None:
    for client, session in make_client():
        project = add_project(session)
        task = add_task(
            session,
            project_id=project.id,
            prompt="cancel me",
            task_status=TaskStatus.PENDING,
        )

        response = client.post(f"/tasks/{task.id}/cancel")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "CANCELLED"
        assert body["cancel_requested"] is True


def test_cancel_running_task_sets_cancel_request_without_terminal_status() -> None:
    for client, session in make_client():
        project = add_project(session)
        task = add_task(
            session,
            project_id=project.id,
            prompt="cancel running",
            task_status=TaskStatus.RUNNING,
        )
        task.runner_id = "runner-a"
        session.add(task)
        session.commit()

        response = client.post(f"/tasks/{task.id}/cancel")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "RUNNING"
        assert body["cancel_requested"] is True


def test_cancel_agent_run_cancels_command_and_is_idempotent() -> None:
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")
        created = client.post(
            "/runs",
            json={
                "project_id": project.id,
                "workspace_id": workspace.id,
                "prompt": "cancel agent run",
                "client_request_id": "cancel-run-1",
            },
        ).json()

        first = client.post(f"/tasks/{created['id']}/cancel")
        second = client.post(f"/tasks/{created['id']}/cancel")

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["status"] == "CANCELLED"
        assert second.json()["status"] == "CANCELLED"
        assert first.json()["cancel_requested"] is True
        command = agent_command_service.list_commands_for_device(session, "device-a")[0]
        assert command.status == AgentCommandStatus.CANCELLED


def test_task_templates_are_exposed() -> None:
    for client, session in make_client():
        del session
        response = client.get("/task-templates")

        assert response.status_code == 200
        task_types = {item["task_type"] for item in response.json()}
        assert TaskType.PLAN.value in task_types
        assert TaskType.IMPLEMENT.value in task_types
