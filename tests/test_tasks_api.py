from __future__ import annotations

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from backend.main import app
from backend.db import get_session
from backend.models import Project, Task, TaskStatus, TaskType, utc_now


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


def test_create_task_inherits_project_default_runner() -> None:
    for client, session in make_client():
        project = add_project(session)
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


def test_task_templates_are_exposed() -> None:
    for client, session in make_client():
        del session
        response = client.get("/task-templates")

        assert response.status_code == 200
        task_types = {item["task_type"] for item in response.json()}
        assert TaskType.PLAN.value in task_types
        assert TaskType.IMPLEMENT.value in task_types
