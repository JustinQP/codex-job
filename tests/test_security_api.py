from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

import backend.main as main_module
from backend.db import get_session
from backend.main import app
from backend.models import Project, RunnerRecord, Task, TaskStatus, utc_now


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


def test_api_token_protects_mutation_endpoints(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("API_TOKEN", "secret")
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    for client, session in make_client():
        del session
        unauthorized = client.post(
            "/projects",
            json={"name": "demo", "path": str(project_dir), "enabled": True},
        )
        authorized = client.post(
            "/projects",
            headers={"X-API-Token": "secret"},
            json={"name": "demo", "path": str(project_dir), "enabled": True},
        )

        assert unauthorized.status_code == 401
        assert authorized.status_code == 200
        body = authorized.json()
        assert "path" not in body
        assert body["path_label"] == "project"


def test_health_remains_public_when_api_token_is_enabled(monkeypatch) -> None:
    monkeypatch.setenv("API_TOKEN", "secret")

    for client, session in make_client():
        del session
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_api_token_protects_read_endpoints(monkeypatch) -> None:
    monkeypatch.setenv("API_TOKEN", "secret")

    for client, session in make_client():
        project = Project(
            name="demo",
            path="E:\\demo",
            enabled=True,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        runner = RunnerRecord(
            runner_id="local",
            pid=123,
            hostname="host",
            status="ONLINE",
            registered_at=utc_now(),
            last_heartbeat_at=utc_now(),
        )
        session.add(project)
        session.add(runner)
        session.commit()
        session.refresh(project)
        task = Task(
            project_id=project.id,
            prompt="inspect",
            status=TaskStatus.RUNNING,
            runner_id="local",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(task)
        session.commit()
        session.refresh(task)

        protected_paths = [
            "/",
            "/projects",
            "/tasks",
            f"/tasks/{task.id}",
            f"/ui/tasks/{task.id}",
            f"/tasks/{task.id}/artifacts",
            "/task-templates",
            "/runners",
            f"/runner/tasks/{task.id}/cancel-state?runner_id=local",
        ]

        for path in protected_paths:
            unauthorized = client.get(path)
            authorized = client.get(path, headers={"X-API-Token": "secret"})

            assert unauthorized.status_code == 401, path
            assert authorized.status_code == 200, path


def test_api_token_protects_runner_write_endpoints(monkeypatch) -> None:
    monkeypatch.setenv("API_TOKEN", "secret")

    for client, session in make_client():
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
        task = Task(
            project_id=project.id,
            prompt="inspect",
            status=TaskStatus.RUNNING,
            runner_id="local",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(task)
        session.commit()
        session.refresh(task)

        endpoints = [
            (
                "/runner/register",
                {"runner_id": "local", "pid": 123, "hostname": "host"},
            ),
            (
                "/runner/heartbeat",
                {"runner_id": "local", "pid": 123, "hostname": "host"},
            ),
            ("/runner/tasks/claim", {"runner_id": "local"}),
            (
                f"/runner/tasks/{task.id}/log",
                {"runner_id": "local", "content": "log", "append": False},
            ),
            (
                f"/runner/tasks/{task.id}/artifacts",
                {"runner_id": "local", "result": "result"},
            ),
            (
                f"/runner/tasks/{task.id}/finish",
                {"runner_id": "local", "status": "SUCCESS", "exit_code": 0},
            ),
        ]

        for path, payload in endpoints:
            unauthorized = client.post(path, json=payload)
            assert unauthorized.status_code == 401, path

        authorized = client.post(
            "/runner/register",
            headers={"X-API-Token": "secret"},
            json={"runner_id": "local", "pid": 123, "hostname": "host"},
        )
        assert authorized.status_code == 200


def test_api_token_protects_artifact_reads(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("API_TOKEN", "secret")
    jobs_dir = tmp_path / "jobs"
    monkeypatch.setattr(main_module, "JOBS_DIR", jobs_dir)
    job_dir = jobs_dir / "pytest-token-artifacts"
    job_dir.mkdir(parents=True, exist_ok=True)
    log_file = job_dir / "run.log"
    result_file = job_dir / "result.md"
    diff_file = job_dir / "diff.patch"
    git_status_file = job_dir / "git-status.txt"
    report_file = job_dir / "task-report.md"
    log_file.write_text("log", encoding="utf-8")
    result_file.write_text("result", encoding="utf-8")
    diff_file.write_text("diff", encoding="utf-8")
    git_status_file.write_text("status", encoding="utf-8")
    report_file.write_text("report", encoding="utf-8")

    for client, session in make_client():
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
        task = Task(
            project_id=project.id,
            prompt="inspect artifacts",
            status=TaskStatus.SUCCESS,
            log_file=str(log_file),
            result_file=str(result_file),
            diff_file=str(diff_file),
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(task)
        session.commit()
        session.refresh(task)

        protected_paths = [
            f"/tasks/{task.id}/log",
            f"/tasks/{task.id}/result",
            f"/tasks/{task.id}/diff",
            f"/tasks/{task.id}/artifacts/git-status",
            f"/tasks/{task.id}/artifacts/report",
        ]

        for path in protected_paths:
            unauthorized = client.get(path)
            authorized = client.get(path, headers={"X-API-Token": "secret"})

            assert unauthorized.status_code == 401, path
            assert authorized.status_code == 200, path


def test_api_token_protects_ui_post_endpoints(monkeypatch) -> None:
    monkeypatch.setenv("API_TOKEN", "secret")

    for client, session in make_client():
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
        task = Task(
            project_id=project.id,
            prompt="existing",
            status=TaskStatus.PENDING,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(task)
        session.commit()
        session.refresh(task)

        create_body = (
            f"project_id={project.id}&prompt=from-ui&timeout_seconds=120"
            "&task_type=IMPLEMENT"
        )
        unauthorized_create = client.post("/ui/tasks", content=create_body)
        authorized_create = client.post(
            "/ui/tasks",
            headers={"X-API-Token": "secret"},
            content=create_body,
            follow_redirects=False,
        )
        unauthorized_rerun = client.post(f"/ui/tasks/{task.id}/rerun")
        unauthorized_cancel = client.post(f"/ui/tasks/{task.id}/cancel")

        assert unauthorized_create.status_code == 401
        assert authorized_create.status_code == 303
        assert unauthorized_rerun.status_code == 401
        assert unauthorized_cancel.status_code == 401


def test_project_path_whitelist_rejects_outside_path(
    monkeypatch,
    tmp_path: Path,
) -> None:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    monkeypatch.setenv("PROJECT_PATH_WHITELIST", str(allowed))

    for client, session in make_client():
        del session
        response = client.post(
            "/projects",
            json={"name": "outside", "path": str(outside), "enabled": True},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "project path is outside PROJECT_PATH_WHITELIST"


def test_runner_register_and_heartbeat() -> None:
    for client, session in make_client():
        del session
        payload = {"runner_id": "local", "pid": 123, "hostname": "host"}
        registered = client.post("/runners/register", json=payload)
        heartbeat = client.post("/runners/heartbeat", json=payload)
        listed = client.get("/runners")

        assert registered.status_code == 200
        assert heartbeat.status_code == 200
        assert listed.status_code == 200
        assert listed.json()[0]["runner_id"] == "local"


def test_remote_runner_http_claim_upload_and_finish(
    monkeypatch,
    tmp_path: Path,
) -> None:
    jobs_dir = tmp_path / "backend-jobs"
    monkeypatch.setattr(main_module, "JOBS_DIR", jobs_dir)
    monkeypatch.setattr("backend.services.runner_service.JOBS_DIR", jobs_dir)

    for client, session in make_client():
        project = Project(
            name="demo",
            path=str(tmp_path / "project"),
            enabled=True,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(project)
        session.commit()
        session.refresh(project)
        task = Task(
            project_id=project.id,
            prompt="remote work",
            status=TaskStatus.PENDING,
            timeout_seconds=120,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(task)
        session.commit()
        session.refresh(task)

        register = client.post(
            "/runner/register",
            json={"runner_id": "desktop-1", "pid": 123, "hostname": "host"},
        )
        claim = client.post(
            "/runner/tasks/claim",
            json={"runner_id": "desktop-1"},
        )

        assert register.status_code == 200
        assert claim.status_code == 200
        claim_body = claim.json()
        assert claim_body["task_id"] == task.id
        assert claim_body["prompt"] == "remote work"

        log_upload = client.post(
            f"/runner/tasks/{task.id}/log",
            json={"runner_id": "desktop-1", "content": "run log", "append": False},
        )
        artifacts_upload = client.post(
            f"/runner/tasks/{task.id}/artifacts",
            json={
                "runner_id": "desktop-1",
                "result": "result text",
                "diff": "diff text",
                "git_status": " M file.py",
                "task_report": "# report",
            },
        )
        finish = client.post(
            f"/runner/tasks/{task.id}/finish",
            json={
                "runner_id": "desktop-1",
                "status": "SUCCESS",
                "exit_code": 0,
                "error_message": None,
            },
        )

        assert log_upload.status_code == 200
        assert artifacts_upload.status_code == 200
        assert finish.status_code == 200
        assert finish.json()["status"] == "SUCCESS"
        assert client.get(f"/tasks/{task.id}/log").text == "run log"
        assert client.get(f"/tasks/{task.id}/result").text == "result text"
        assert client.get(f"/tasks/{task.id}/diff").text == "diff text"
        assert client.get(f"/tasks/{task.id}/artifacts/git-status").text == " M file.py"


def test_remote_runner_rejects_unassigned_artifact_upload() -> None:
    for client, session in make_client():
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
        task = Task(
            project_id=project.id,
            prompt="remote work",
            status=TaskStatus.RUNNING,
            runner_id="desktop-1",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(task)
        session.commit()
        session.refresh(task)

        response = client.post(
            f"/runner/tasks/{task.id}/artifacts",
            json={"runner_id": "desktop-2", "result": "bad"},
        )

        assert response.status_code == 403
