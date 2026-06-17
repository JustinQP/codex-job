from __future__ import annotations

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from backend import ui
from backend.db import get_session
from backend.main import app
from backend.models import Project, Task, TaskStatus, utc_now


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
    project = Project(
        name="demo",
        path="E:\\demo",
        enabled=True,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def add_task(session: Session, project_id: int) -> Task:
    task = Task(
        project_id=project_id,
        prompt="old prompt",
        status=TaskStatus.FAILED,
        timeout_seconds=120,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def test_dashboard_renders_projects_and_tasks() -> None:
    for client, session in make_client():
        project = add_project(session)
        task = add_task(session, project.id)

        response = client.get("/")

        assert response.status_code == 200
        assert "创建任务" in response.text
        assert "项目列表" in response.text
        assert f"/ui/tasks/{task.id}" in response.text


def test_mobile_console_is_public_static_page() -> None:
    for client, session in make_client():
        del session
        response = client.get("/mobile")

        assert response.status_code == 200
        assert "Codex Mobile Console" in response.text
        assert "localStorage" in response.text


def test_mobile_console_escapes_inner_html_dynamic_fields() -> None:
    for client, session in make_client():
        del session
        response = client.get("/mobile")

        assert response.status_code == 200
        html = response.text
        assert "function escapeHtml(value)" in html
        assert 'replaceAll("<", "&lt;")' in html
        assert "${escapeHtml(p.name)}" in html
        assert "${escapeHtml(r.runner_id)}" in html
        assert "${escapeHtml(r.status)}" in html
        assert "${escapeHtml(r.hostname)}" in html
        assert "${escapeHtml(r.supported_models || \"\")}" in html
        assert "${escapeHtml(t.status)}" in html
        assert "${escapeHtml(t.task_type)}" in html
        assert "${escapeHtml(t.assigned_runner_id || t.runner_id || \"\")}" in html
        assert "${escapeHtml(t.model || \"\")}" in html
        assert "${escapeHtml(task.reasoning_effort || \"\")}" in html
        assert "${escapeHtml(task.sandbox || \"\")}" in html
        assert 'href="${escapeHtml(task.log_url)}"' in html
        assert 'href="${escapeHtml(task.result_url)}"' in html
        assert 'href="${escapeHtml(task.diff_url)}"' in html


def test_mobile_console_contains_app_server_session_block() -> None:
    for client, session in make_client():
        del session
        response = client.get("/mobile")

        assert response.status_code == 200
        html = response.text
        assert "App Server 会话" in html
        assert "检查 App Server Bridge" in html
        assert 'api("/app-server-bridge/health"' in html
        assert 'api("/app-threads?limit=20"' in html
        assert 'api("/app-threads", {method: "POST"' in html
        assert 'api(`/app-threads/${selectedAppThreadId}/turns`' in html
        assert 'api(`/app-threads/${selectedAppThreadId}`, {method: "DELETE"' in html
        assert "${escapeHtml(t.title)}" in html
        assert "${escapeHtml(t.status)}" in html
        assert "${escapeHtml(t.assistant_final || t.error_message || \"\")}" in html


def test_create_task_form_redirects_to_detail() -> None:
    for client, session in make_client():
        project = add_project(session)

        response = client.post(
            "/ui/tasks",
            data={
                "project_id": str(project.id),
                "prompt": "new prompt",
                "timeout_seconds": "60",
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"].startswith("/ui/tasks/")


def test_rerun_form_redirects_to_new_task_detail() -> None:
    for client, session in make_client():
        project = add_project(session)
        task = add_task(session, project.id)

        response = client.post(
            f"/ui/tasks/{task.id}/rerun",
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] != f"/ui/tasks/{task.id}"


def test_cancel_form_redirects_to_task_detail() -> None:
    for client, session in make_client():
        project = add_project(session)
        task = Task(
            project_id=project.id,
            prompt="cancel from ui",
            status=TaskStatus.PENDING,
            timeout_seconds=120,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(task)
        session.commit()
        session.refresh(task)

        response = client.post(
            f"/ui/tasks/{task.id}/cancel",
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == f"/ui/tasks/{task.id}"


def test_task_detail_auto_refreshes_running_task() -> None:
    task = Task(
        id=1,
        project_id=1,
        prompt="running",
        status=TaskStatus.RUNNING,
        created_at=utc_now(),
        updated_at=utc_now(),
    )

    html = ui.task_detail(task)

    assert '<meta http-equiv="refresh" content="5">' in html


def test_task_detail_does_not_auto_refresh_terminal_task() -> None:
    task = Task(
        id=1,
        project_id=1,
        prompt="done",
        status=TaskStatus.SUCCESS,
        created_at=utc_now(),
        updated_at=utc_now(),
    )

    html = ui.task_detail(task)

    assert 'http-equiv="refresh"' not in html
