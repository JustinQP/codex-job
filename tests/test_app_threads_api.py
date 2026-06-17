from __future__ import annotations

from collections.abc import Generator
from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

import backend.main as main_module
from backend.db import get_session
from backend.main import app
from backend.models import AppThread, AppTurn, Project, utc_now
from backend.services.app_server_bridge_client import AppServerBridgeError


def test_fastapi_version_is_1_0_0() -> None:
    assert app.version == "1.0.0"


class FakeBridgeClient:
    def __init__(self) -> None:
        self.deleted: list[str] = []
        self.create_count = 0
        self.missing_bridge_thread_id = False
        self.preview_final = "short preview"
        self.full_final = "full assistant final"

    def get_health(self) -> dict[str, Any]:
        return {"status": "ok", "mode": "poc", "sandbox": "readOnly", "threads": 0}

    def create_thread(self, title: str) -> dict[str, Any]:
        self.create_count += 1
        if self.missing_bridge_thread_id:
            return {
                "app_thread_id": f"app-{self.create_count}",
                "title": title,
            }
        return {
            "bridge_thread_id": f"bridge-{self.create_count}",
            "app_thread_id": f"app-{self.create_count}",
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
            "assistant_final_preview": self.preview_final,
        }

    def get_events(self, bridge_thread_id: str) -> dict[str, Any]:
        return {"summary": {"total_events": 2, "bridge_thread_id": bridge_thread_id}}

    def get_final(self, bridge_thread_id: str) -> dict[str, Any]:
        return {"assistant_final": self.full_final}


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
        assert created["turn_count"] == 0
        assert created["latest_assistant_final"] is None
        assert listed.status_code == 200
        assert listed.json()[0]["id"] == created["id"]
        assert detail.status_code == 200
        assert renamed.status_code == 200
        assert renamed.json()["title"] == "Renamed"
        assert turn.status_code == 200
        assert turn.json()["assistant_final"] == "full assistant final"
        assert turn.json()["bridge_turn_id"] == "turn-1"
        assert turn.json()["event_summary"]["total_events"] == 2
        assert turns.status_code == 200
        assert len(turns.json()) == 1
        listed_after_turn = client.get("/app-threads")
        detail_after_turn = client.get(f"/app-threads/{created['id']}")
        assert listed_after_turn.status_code == 200
        assert detail_after_turn.status_code == 200
        assert listed_after_turn.json()[0]["turn_count"] == 1
        assert listed_after_turn.json()[0]["latest_assistant_final"] == "full assistant final"
        assert detail_after_turn.json()["turn_count"] == 1
        assert detail_after_turn.json()["latest_assistant_final"] == "full assistant final"
        assert final.status_code == 200
        assert final.json()["assistant_final"] == "full assistant final"
        assert events.status_code == 200
        assert events.json()["event_summary"]["total_events"] == 2
        assert closed.status_code == 200
        assert closed.json()["status"] == "CLOSED"
        assert fake.deleted == ["bridge-1"]


def test_app_threads_api_token_protection(monkeypatch) -> None:
    monkeypatch.setenv("API_TOKEN", "secret")
    monkeypatch.setattr("backend.services.app_turn_executor.submit_app_turn", lambda app_turn_id: None)
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
        created = authorized_post.json()
        protected_reopen = client.post(f"/app-threads/{created['id']}/reopen")
        authorized_reopen = client.post(
            f"/app-threads/{created['id']}/reopen",
            headers={"X-API-Token": "secret"},
        )
        protected_async = client.post(
            f"/app-threads/{created['id']}/turns/async",
            json={"message": "hello"},
        )
        authorized_async = client.post(
            f"/app-threads/{created['id']}/turns/async",
            headers={"X-API-Token": "secret"},
            json={"message": "hello"},
        )
        turn_id = authorized_async.json()["id"]
        protected_get_turn = client.get(f"/app-turns/{turn_id}")
        authorized_get_turn = client.get(
            f"/app-turns/{turn_id}",
            headers={"X-API-Token": "secret"},
        )
        protected_cancel_turn = client.post(f"/app-turns/{turn_id}/cancel")
        authorized_cancel_turn = client.post(
            f"/app-turns/{turn_id}/cancel",
            headers={"X-API-Token": "secret"},
        )
        protected_recover = client.post("/app-turns/recover-stale")
        authorized_recover = client.post("/app-turns/recover-stale", headers={"X-API-Token": "secret"})

        assert client.get("/health").status_code == 200
        assert protected_get.status_code == 401
        assert authorized_get.status_code == 200
        assert protected_post.status_code == 401
        assert authorized_post.status_code == 200
        assert protected_reopen.status_code == 401
        assert authorized_reopen.status_code == 200
        assert protected_async.status_code == 401
        assert authorized_async.status_code == 200
        assert protected_get_turn.status_code == 401
        assert authorized_get_turn.status_code == 200
        assert protected_cancel_turn.status_code == 401
        assert authorized_cancel_turn.status_code == 200
        assert protected_recover.status_code == 401
        assert authorized_recover.status_code == 200


def test_async_app_turn_api_creates_pending_turn_and_gets_turn(monkeypatch) -> None:
    submitted: list[int] = []
    monkeypatch.setattr(
        "backend.services.app_turn_executor.submit_app_turn",
        lambda app_turn_id: submitted.append(app_turn_id),
    )
    for client, session, _fake in make_client(monkeypatch):
        project = add_project(session)
        created = create_app_thread(client, project.id)

        response = client.post(f"/app-threads/{created['id']}/turns/async", json={"message": "hello"})
        body = response.json()
        fetched = client.get(f"/app-turns/{body['id']}")

        assert response.status_code == 200
        assert body["status"] == "PENDING"
        assert body["assistant_final"] is None
        assert body["duration_seconds"] is None
        assert submitted == [body["id"]]
        assert fetched.status_code == 200
        assert fetched.json()["id"] == body["id"]


def test_async_app_turn_rejects_closed_thread(monkeypatch) -> None:
    monkeypatch.setattr("backend.services.app_turn_executor.submit_app_turn", lambda app_turn_id: None)
    for client, session, _fake in make_client(monkeypatch):
        project = add_project(session)
        created = create_app_thread(client, project.id)
        closed = client.delete(f"/app-threads/{created['id']}")

        response = client.post(f"/app-threads/{created['id']}/turns/async", json={"message": "hello"})

        assert closed.status_code == 200
        assert response.status_code == 400


def test_cancel_app_turn_api_success(monkeypatch) -> None:
    monkeypatch.setattr("backend.services.app_turn_executor.submit_app_turn", lambda app_turn_id: None)
    for client, session, _fake in make_client(monkeypatch):
        project = add_project(session)
        created = create_app_thread(client, project.id)
        turn = client.post(f"/app-threads/{created['id']}/turns/async", json={"message": "hello"}).json()

        response = client.post(f"/app-turns/{turn['id']}/cancel")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "CANCELLED"
        assert body["error_message"] == "cancelled by user"


def test_async_app_turn_conflict_api(monkeypatch) -> None:
    monkeypatch.setattr("backend.services.app_turn_executor.submit_app_turn", lambda app_turn_id: None)
    for client, session, _fake in make_client(monkeypatch):
        project = add_project(session)
        created = create_app_thread(client, project.id)
        first = client.post(f"/app-threads/{created['id']}/turns/async", json={"message": "first"})

        second = client.post(f"/app-threads/{created['id']}/turns/async", json={"message": "second"})

        assert first.status_code == 200
        assert second.status_code == 409
        detail = second.json()["detail"]
        assert detail["code"] == "app_turn_conflict"
        assert detail["app_turn_id"] == first.json()["id"]


def test_reopen_app_thread_api_returns_read_with_stats(monkeypatch) -> None:
    for client, session, _fake in make_client(monkeypatch):
        project = add_project(session)
        created = create_app_thread(client, project.id)
        turn = client.post(f"/app-threads/{created['id']}/turns", json={"message": "hello"})

        reopened = client.post(f"/app-threads/{created['id']}/reopen")

        assert turn.status_code == 200
        assert reopened.status_code == 200
        body = reopened.json()
        assert body["id"] == created["id"]
        assert body["bridge_thread_id"] == "bridge-2"
        assert body["app_thread_id"] == "app-2"
        assert body["status"] == "ACTIVE"
        assert body["last_error"] is None
        assert body["turn_count"] == 1
        assert body["latest_assistant_final"] == "full assistant final"


def test_create_app_thread_rejects_missing_bridge_thread_id(monkeypatch) -> None:
    fake = FakeBridgeClient()
    fake.missing_bridge_thread_id = True
    for client, session, _fake in make_client(monkeypatch, fake):
        project = add_project(session)

        response = client.post(
            "/app-threads",
            json={"project_id": project.id, "title": "Chat"},
        )

        assert response.status_code == 502
        assert response.json()["detail"]["code"] == "invalid_bridge_response"
        assert response.json()["detail"]["message"] == "Bridge response missing bridge_thread_id"


def test_recover_stale_app_turns_api_is_idempotent(monkeypatch) -> None:
    for client, session, _fake in make_client(monkeypatch):
        project = add_project(session)
        app_thread = AppThread(
            project_id=project.id,
            title="Chat",
            bridge_thread_id="bridge-1",
            app_thread_id="app-1",
            status="ACTIVE",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(app_thread)
        session.commit()
        session.refresh(app_thread)
        app_turn = AppTurn(
            app_thread_id=app_thread.id,
            user_message="stale",
            status="PENDING",
            created_at=utc_now(),
        )
        session.add(app_turn)
        session.commit()
        session.refresh(app_turn)

        first = client.post("/app-turns/recover-stale")
        second = client.post("/app-turns/recover-stale")

        session.refresh(app_thread)
        session.refresh(app_turn)
        assert first.status_code == 200
        assert first.json() == {"recovered_count": 1, "recovered_turn_ids": [app_turn.id]}
        assert second.status_code == 200
        assert second.json() == {"recovered_count": 0, "recovered_turn_ids": []}
        assert app_turn.status == "FAILED"
        assert app_thread.status == "ERROR"


def test_app_thread_and_turn_filters_and_cleanup_api(monkeypatch) -> None:
    for client, session, _fake in make_client(monkeypatch):
        project = add_project(session)
        active = AppThread(
            project_id=project.id,
            title="Active",
            status="ACTIVE",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        closed = AppThread(
            project_id=project.id,
            title="Closed",
            status="CLOSED",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        archived = AppThread(
            project_id=project.id,
            title="[archived] Error",
            status="ERROR",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(active)
        session.add(closed)
        session.add(archived)
        session.commit()
        session.refresh(active)
        session.refresh(closed)
        session.refresh(archived)
        session.add(
            AppTurn(
                app_thread_id=active.id,
                user_message="ok",
                status="SUCCESS",
                created_at=utc_now(),
            )
        )
        session.add(
            AppTurn(
                app_thread_id=active.id,
                user_message="bad",
                status="FAILED",
                created_at=utc_now(),
            )
        )
        session.commit()

        active_threads = client.get("/app-threads?status=ACTIVE")
        bad_threads = client.get("/app-threads?status=BAD")
        default_threads = client.get("/app-threads")
        with_archived = client.get("/app-threads?include_archived=true")
        success_turns = client.get(f"/app-threads/{active.id}/turns?status=SUCCESS")
        bad_turns = client.get(f"/app-threads/{active.id}/turns?status=BAD")
        cleanup_closed = client.post("/app-threads/cleanup", json={"status": "CLOSED", "limit": 50})
        cleanup_active = client.post("/app-threads/cleanup", json={"status": "ACTIVE"})

        assert active_threads.status_code == 200
        assert [thread["status"] for thread in active_threads.json()] == ["ACTIVE"]
        assert bad_threads.status_code == 400
        assert all(not thread["title"].startswith("[archived]") for thread in default_threads.json())
        assert any(thread["title"].startswith("[archived]") for thread in with_archived.json())
        assert success_turns.status_code == 200
        assert [turn["status"] for turn in success_turns.json()] == ["SUCCESS"]
        assert bad_turns.status_code == 400
        assert cleanup_closed.status_code == 200
        assert cleanup_closed.json() == {"archived_count": 1, "archived_thread_ids": [closed.id]}
        assert cleanup_active.status_code == 400


def test_app_threads_not_found_and_empty_turn(monkeypatch) -> None:
    for client, session, _fake in make_client(monkeypatch):
        project = add_project(session)
        created = create_app_thread(client, project.id)

        missing = client.get("/app-threads/404")
        empty_turn = client.post(f"/app-threads/{created['id']}/turns", json={"message": ""})

        assert missing.status_code == 404
        assert empty_turn.status_code == 422
