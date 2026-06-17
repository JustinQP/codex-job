from __future__ import annotations

from collections.abc import Generator
from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

import backend.main as main_module
from backend.db import get_session
from backend.main import app
from backend.models import Project, utc_now
from backend.services.app_server_bridge_client import AppServerBridgeError


class FakeBridgeClient:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def get_health(self) -> dict[str, Any]:
        return {"status": "ok", "mode": "poc", "sandbox": "readOnly", "threads": 0}

    def create_thread(self, title: str) -> dict[str, Any]:
        return {
            "bridge_thread_id": "bridge-1",
            "app_thread_id": "app-1",
            "title": title,
        }

    def rename_thread(self, bridge_thread_id: str, title: str) -> dict[str, Any]:
        return {"bridge_thread_id": bridge_thread_id, "title": title}

    def delete_thread(self, bridge_thread_id: str) -> dict[str, Any]:
        self.deleted.append(bridge_thread_id)
        return {"closed": True}

    def send_turn(self, bridge_thread_id: str, message: str) -> dict[str, Any]:
        return {
            "turn_id": "turn-1",
            "assistant_final_preview": f"assistant:{message}",
        }

    def get_events(self, bridge_thread_id: str) -> dict[str, Any]:
        return {"summary": {"total_events": 2, "bridge_thread_id": bridge_thread_id}}

    def get_final(self, bridge_thread_id: str) -> dict[str, Any]:
        return {"assistant_final": "final fallback"}


def make_client(monkeypatch, fake: FakeBridgeClient | None = None) -> Generator[tuple[TestClient, Session, FakeBridgeClient], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    fake_client = fake or FakeBridgeClient()
    monkeypatch.setattr(main_module, "get_default_client", lambda: fake_client)
    monkeypatch.setattr("backend.services.app_thread_service.get_default_client", lambda: fake_client)

    def override_get_session() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            yield client, session, fake_client
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


def create_app_thread(client: TestClient, project_id: int) -> dict[str, Any]:
    response = client.post(
        "/app-threads",
        json={"project_id": project_id, "title": "Chat"},
    )
    assert response.status_code == 200
    return response.json()


def test_app_server_bridge_health(monkeypatch) -> None:
    for client, session, _fake in make_client(monkeypatch):
        del session
        response = client.get("/app-server-bridge/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_app_server_bridge_health_unavailable(monkeypatch) -> None:
    class FailingBridge(FakeBridgeClient):
        def get_health(self) -> dict[str, Any]:
            raise AppServerBridgeError(None, "network_error", "bridge down", "request")

    for client, session, _fake in make_client(monkeypatch, FailingBridge()):
        del session
        response = client.get("/app-server-bridge/health")

        assert response.status_code == 503
        assert response.json()["detail"]["status"] == "unavailable"


def test_app_threads_crud_turns_final_and_events(monkeypatch) -> None:
    for client, session, fake in make_client(monkeypatch):
        project = add_project(session)

        created = create_app_thread(client, project.id)
        listed = client.get("/app-threads")
        detail = client.get(f"/app-threads/{created['id']}")
        renamed = client.patch(f"/app-threads/{created['id']}", json={"title": "Renamed"})
        turn = client.post(f"/app-threads/{created['id']}/turns", json={"message": "hello"})
        turns = client.get(f"/app-threads/{created['id']}/turns")
        final = client.get(f"/app-threads/{created['id']}/final")
        events = client.get(f"/app-threads/{created['id']}/events")
        closed = client.delete(f"/app-threads/{created['id']}")

        assert created["title"] == "Chat"
        assert created["bridge_thread_id"] == "bridge-1"
        assert listed.status_code == 200
        assert listed.json()[0]["id"] == created["id"]
        assert detail.status_code == 200
        assert renamed.status_code == 200
        assert renamed.json()["title"] == "Renamed"
        assert turn.status_code == 200
        assert turn.json()["assistant_final"] == "assistant:hello"
        assert turn.json()["bridge_turn_id"] == "turn-1"
        assert turns.status_code == 200
        assert len(turns.json()) == 1
        assert final.status_code == 200
        assert final.json()["assistant_final"] == "assistant:hello"
        assert events.status_code == 200
        assert events.json()["event_summary"]["total_events"] == 2
        assert closed.status_code == 200
        assert closed.json()["status"] == "CLOSED"
        assert fake.deleted == ["bridge-1"]


def test_app_threads_api_token_protection(monkeypatch) -> None:
    monkeypatch.setenv("API_TOKEN", "secret")
    for client, session, _fake in make_client(monkeypatch):
        project = add_project(session)

        protected_get = client.get("/app-threads")
        authorized_get = client.get("/app-threads", headers={"X-API-Token": "secret"})
        protected_post = client.post("/app-threads", json={"project_id": project.id})
        authorized_post = client.post(
            "/app-threads",
            headers={"X-API-Token": "secret"},
            json={"project_id": project.id},
        )

        assert client.get("/health").status_code == 200
        assert protected_get.status_code == 401
        assert authorized_get.status_code == 200
        assert protected_post.status_code == 401
        assert authorized_post.status_code == 200


def test_app_threads_not_found_and_empty_turn(monkeypatch) -> None:
    for client, session, _fake in make_client(monkeypatch):
        project = add_project(session)
        created = create_app_thread(client, project.id)

        missing = client.get("/app-threads/404")
        empty_turn = client.post(f"/app-threads/{created['id']}/turns", json={"message": ""})

        assert missing.status_code == 404
        assert empty_turn.status_code == 422
