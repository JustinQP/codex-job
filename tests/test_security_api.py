from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.routers.runs import _read_run_artifact
from tests.test_runs_api import add_device, add_project, add_workspace, make_client


def auth_headers() -> dict[str, str]:
    return {"X-API-Token": "secret"}


class FakeRun:
    def __init__(self, log_file: str) -> None:
        self.log_file = log_file


def test_api_token_protects_mainline_mutation_endpoints(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("API_TOKEN", "secret")
    monkeypatch.setenv("PROJECT_PATH_WHITELIST", str(tmp_path))
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    for client, session in make_client(include_api_token=False):
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")

        unauthorized_project = client.post(
            "/projects",
            json={"name": "demo", "path": str(project_dir), "enabled": True},
        )
        authorized_project = client.post(
            "/projects",
            headers=auth_headers(),
            json={"name": "demo", "path": str(project_dir), "enabled": True},
        )
        unauthorized_run = client.post(
            "/runs",
            json={"project_id": project.id, "workspace_id": workspace.id, "prompt": "run"},
        )
        authorized_run = client.post(
            "/runs",
            headers=auth_headers(),
            json={"project_id": project.id, "workspace_id": workspace.id, "prompt": "run"},
        )

        assert unauthorized_project.status_code == 401
        assert authorized_project.status_code == 200
        assert "path" not in authorized_project.json()
        assert unauthorized_run.status_code == 401
        assert authorized_run.status_code == 200


def test_api_token_protects_mainline_read_endpoints(monkeypatch) -> None:
    monkeypatch.setenv("API_TOKEN", "secret")

    for client, session in make_client(include_api_token=False):
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")
        run = client.post(
            "/runs",
            headers=auth_headers(),
            json={"project_id": project.id, "workspace_id": workspace.id, "prompt": "inspect"},
        ).json()
        app_thread = client.post(
            "/app-threads",
            headers=auth_headers(),
            json={"project_id": project.id, "workspace_id": workspace.id, "title": "Demo"},
        ).json()

        protected_paths = [
            "/projects",
            "/devices",
            "/workspaces",
            "/runs",
            f"/runs/{run['id']}",
            f"/runs/{run['id']}/artifacts",
            "/run-templates",
            "/app-threads",
            f"/app-threads/{app_thread['id']}",
        ]

        for path in protected_paths:
            unauthorized = client.get(path)
            authorized = client.get(path, headers=auth_headers())

            assert unauthorized.status_code == 401, path
            assert authorized.status_code == 200, path


def test_health_remains_public_when_api_token_is_enabled(monkeypatch) -> None:
    monkeypatch.setenv("API_TOKEN", "secret")

    for client, session in make_client():
        del session
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "execution_mode": "agent_command",
            "session_mode": "agent_managed_app_server",
        }


def test_mainline_api_requires_configured_api_token(monkeypatch) -> None:
    monkeypatch.delenv("API_TOKEN", raising=False)

    for client, session in make_client(include_api_token=False):
        del session
        response = client.get("/projects")

        assert response.status_code == 503
        assert response.json()["detail"] == "API token is not configured"


def test_api_and_agent_tokens_must_be_distinct(monkeypatch) -> None:
    monkeypatch.setenv("API_TOKEN", "shared-secret")
    monkeypatch.setenv("AGENT_TOKEN", "shared-secret")

    for client, session in make_client(include_api_token=False):
        del session
        response = client.get("/projects", headers={"X-API-Token": "shared-secret"})

        assert response.status_code == 503
        assert response.json()["detail"] == "API token and agent token must be distinct"


def test_project_path_whitelist_rejects_outside_path(monkeypatch, tmp_path: Path) -> None:
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


def test_unbound_project_creation_requires_path_whitelist(monkeypatch, tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.setenv("API_TOKEN", "secret")
    monkeypatch.delenv("PROJECT_PATH_WHITELIST", raising=False)

    for client, session in make_client(include_api_token=False):
        del session
        response = client.post(
            "/projects",
            headers=auth_headers(),
            json={"name": "project", "path": str(project_dir), "enabled": True},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "PROJECT_PATH_WHITELIST must be configured for unbound project paths"


def test_run_artifact_read_rejects_path_outside_jobs_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    outside_file = tmp_path / "outside.log"
    outside_file.write_text("outside", encoding="utf-8")

    def fake_get_run_or_404(session, run_id: int) -> FakeRun:
        return FakeRun(str(outside_file))

    monkeypatch.setattr(
        "backend.routers.runs.run_service.get_run_or_404",
        fake_get_run_or_404,
    )

    with pytest.raises(HTTPException) as exc_info:
        _read_run_artifact(1, "log_file", session=object())

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "artifact path is outside jobs directory"
