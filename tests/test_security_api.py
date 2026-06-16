from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from backend.db import get_session
from backend.main import app


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
