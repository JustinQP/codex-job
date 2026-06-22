from __future__ import annotations

from collections.abc import Generator
from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

import backend.main as main_module
import backend.routers.ui as ui_router
from backend.db import get_session
from backend.main import app
from backend.models import AgentCommandStatus, AppThread, AppTurn, Project, TurnEvent, utc_now
from backend.services import agent_command_service
from tests.test_runs_api import add_device, add_workspace
from backend.services.app_server_bridge_client import AppServerBridgeError


def test_fastapi_version_is_2_0_0() -> None:
    assert app.version == "2.0.0"


class FakeBridgeClient:
    def __init__(self) -> None:
        self.deleted: list[str] = []
        self.created_cwds: list[str | None] = []
        self.create_count = 0
        self.missing_bridge_thread_id = False
        self.preview_final = "short preview"
        self.full_final = "full assistant final"

    def get_health(self) -> dict[str, Any]:
        return {"status": "ok", "mode": "poc", "sandbox": "readOnly", "threads": 0}

    def create_thread(self, title: str, cwd: str | None = None) -> dict[str, Any]:
        self.created_cwds.append(cwd)
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

    def get_live_events(self, bridge_thread_id: str, since: int = 0) -> dict[str, Any]:
        return {"next_index": since, "active_turn_id": "turn-1", "events": []}

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
    monkeypatch.setattr(ui_router, "get_default_client", lambda: fake_client)
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
        assert fake.created_cwds == [project.path]
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


def test_create_app_thread_in_agent_mode_creates_session_open_command(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_COMMAND_MODE", "true")
    for client, session, fake in make_client(monkeypatch):
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")

        created = client.post(
            "/app-threads",
            json={
                "project_id": project.id,
                "workspace_id": workspace.id,
                "title": "Agent chat",
                "sandbox": "workspace-write",
                "approval_policy": "never",
                "client_request_id": "session-open-api-1",
            },
        )

        assert created.status_code == 200
        body = created.json()
        assert body["status"] == "OPENING"
        assert body["device_id"] == "device-a"
        assert body["workspace_id"] == workspace.id
        assert body["sandbox"] == "workspace-write"
        assert body["approval_policy"] == "never"
        assert body["bridge_thread_id"] is None
        assert fake.created_cwds == []
        commands = agent_command_service.list_commands_for_device(session, "device-a")
        assert len(commands) == 1
        assert commands[0].command_type == "SESSION_OPEN"
        assert body["command_id"] == commands[0].id
        assert "cwd" not in commands[0].payload_json


def test_session_open_complete_updates_app_thread(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_COMMAND_MODE", "true")
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session, _fake in make_client(monkeypatch):
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")
        created = client.post(
            "/app-threads",
            json={
                "project_id": project.id,
                "workspace_id": workspace.id,
                "title": "Agent chat",
            },
        ).json()
        command_id = created["command_id"]
        claim = client.post(
            "/agent/commands/claim",
            headers={"X-Agent-Token": "agent-secret"},
            json={"device_id": "device-a", "claim_request_id": "claim-session-open"},
        ).json()
        ack = client.post(
            f"/agent/commands/{command_id}/ack",
            headers={"X-Agent-Token": "agent-secret"},
            json={"device_id": "device-a", "lease_token": claim["lease_token"]},
        )
        complete = client.post(
            f"/agent/commands/{command_id}/complete",
            headers={"X-Agent-Token": "agent-secret"},
            json={
                "device_id": "device-a",
                "lease_token": claim["lease_token"],
                "status": AgentCommandStatus.SUCCESS.value,
                "result_payload": {
                    "agent_session_id": "agent-session-1",
                    "codex_thread_id": "codex-thread-1",
                },
            },
        )
        detail = client.get(f"/app-threads/{created['id']}")

        assert ack.status_code == 200
        assert complete.status_code == 200
        assert detail.status_code == 200
        assert detail.json()["status"] == "ACTIVE"
        assert detail.json()["agent_session_id"] == "agent-session-1"
        assert detail.json()["app_thread_id"] == "codex-thread-1"


def test_agent_app_thread_reopen_creates_new_generation_session(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_COMMAND_MODE", "true")
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session, _fake in make_client(monkeypatch):
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")
        app_thread = AppThread(
            project_id=project.id,
            title="Agent chat",
            device_id="device-a",
            workspace_id=workspace.id,
            agent_session_id="old-agent-session",
            app_thread_id="old-codex-thread",
            generation=1,
            status="RECOVER_REQUIRED",
            sandbox="workspace-write",
            approval_policy="never",
            network_access=False,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(app_thread)
        session.commit()
        session.refresh(app_thread)
        old_turn = AppTurn(
            app_thread_id=app_thread.id,
            user_message="old",
            assistant_final="old final",
            status="SUCCESS",
            created_at=utc_now(),
            completed_at=utc_now(),
        )
        session.add(old_turn)
        session.commit()

        reopened = client.post(f"/app-threads/{app_thread.id}/reopen")

        assert reopened.status_code == 200
        body = reopened.json()
        assert body["id"] == app_thread.id
        assert body["status"] == "OPENING"
        assert body["generation"] == 2
        assert body["agent_session_id"] is None
        assert body["app_thread_id"] is None
        assert body["turn_count"] == 1
        commands = agent_command_service.list_commands_for_device(session, "device-a")
        assert len(commands) == 1
        command = commands[0]
        assert command.command_type == "SESSION_OPEN"
        assert '"generation":2' in command.payload_json

        claim = client.post(
            "/agent/commands/claim",
            headers={"X-Agent-Token": "agent-secret"},
            json={"device_id": "device-a", "claim_request_id": "claim-reopen"},
        ).json()
        client.post(
            f"/agent/commands/{command.id}/ack",
            headers={"X-Agent-Token": "agent-secret"},
            json={"device_id": "device-a", "lease_token": claim["lease_token"]},
        )
        complete = client.post(
            f"/agent/commands/{command.id}/complete",
            headers={"X-Agent-Token": "agent-secret"},
            json={
                "device_id": "device-a",
                "lease_token": claim["lease_token"],
                "status": AgentCommandStatus.SUCCESS.value,
                "result_payload": {
                    "agent_session_id": "new-agent-session",
                    "codex_thread_id": "new-codex-thread",
                },
            },
        )
        detail = client.get(f"/app-threads/{app_thread.id}")
        new_turn = client.post(f"/app-threads/{app_thread.id}/turns/async", json={"message": "after reopen"})

        assert complete.status_code == 200
        assert detail.json()["status"] == "ACTIVE"
        assert detail.json()["generation"] == 2
        assert detail.json()["agent_session_id"] == "new-agent-session"
        assert detail.json()["app_thread_id"] == "new-codex-thread"
        assert new_turn.status_code == 200


def test_create_async_app_turn_in_agent_mode_creates_turn_start_command(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_COMMAND_MODE", "true")
    for client, session, fake in make_client(monkeypatch):
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")
        app_thread = AppThread(
            project_id=project.id,
            title="Agent chat",
            device_id="device-a",
            workspace_id=workspace.id,
            agent_session_id="agent-session-1",
            app_thread_id="codex-thread-1",
            status="ACTIVE",
            sandbox="workspace-write",
            approval_policy="never",
            network_access=False,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(app_thread)
        session.commit()
        session.refresh(app_thread)

        response = client.post(f"/app-threads/{app_thread.id}/turns/async", json={"message": "hello"})

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "PENDING"
        assert body["command_id"] is not None
        assert fake.created_cwds == []
        commands = agent_command_service.list_commands_for_device(session, "device-a")
        assert [command.command_type for command in commands] == ["TURN_START"]
        command = commands[0]
        assert command.aggregate_type == "app_turn"
        assert command.aggregate_id == str(body["id"])
        assert body["command_id"] == command.id
        payload = command.payload_json
        assert "cwd" not in payload
        assert "project_path" not in payload
        assert '"agent_session_id":"agent-session-1"' in payload
        assert f'"app_turn_id":{body["id"]}' in payload


def test_turn_start_ack_and_complete_updates_app_turn(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_COMMAND_MODE", "true")
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session, _fake in make_client(monkeypatch):
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")
        app_thread = AppThread(
            project_id=project.id,
            title="Agent chat",
            device_id="device-a",
            workspace_id=workspace.id,
            agent_session_id="agent-session-1",
            app_thread_id="codex-thread-1",
            status="ACTIVE",
            sandbox="read-only",
            approval_policy="never",
            network_access=False,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(app_thread)
        session.commit()
        session.refresh(app_thread)
        created = client.post(f"/app-threads/{app_thread.id}/turns/async", json={"message": "hello"}).json()
        command_id = created["command_id"]
        claim = client.post(
            "/agent/commands/claim",
            headers={"X-Agent-Token": "agent-secret"},
            json={"device_id": "device-a", "claim_request_id": "claim-turn-start"},
        ).json()

        ack = client.post(
            f"/agent/commands/{command_id}/ack",
            headers={"X-Agent-Token": "agent-secret"},
            json={"device_id": "device-a", "lease_token": claim["lease_token"]},
        )
        running = client.get(f"/app-turns/{created['id']}")
        complete = client.post(
            f"/agent/commands/{command_id}/complete",
            headers={"X-Agent-Token": "agent-secret"},
            json={
                "device_id": "device-a",
                "lease_token": claim["lease_token"],
                "status": AgentCommandStatus.SUCCESS.value,
                "result_payload": {
                    "app_turn_id": created["id"],
                    "agent_session_id": "agent-session-1",
                    "codex_turn_id": "codex-turn-1",
                    "assistant_final": "hello back",
                    "event_summary": {"total_events": 3, "assistant_text_preview": "hello back"},
                },
            },
        )
        finished = client.get(f"/app-turns/{created['id']}")

        assert ack.status_code == 200
        assert running.json()["status"] == "RUNNING"
        assert running.json()["started_at"] is not None
        assert complete.status_code == 200
        assert finished.json()["status"] == "SUCCESS"
        assert finished.json()["assistant_final"] == "hello back"
        assert finished.json()["bridge_turn_id"] == "codex-turn-1"
        assert finished.json()["duration_seconds"] is not None
        assert finished.json()["event_summary"]["total_events"] == 3


def test_turn_start_complete_from_wrong_device_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_COMMAND_MODE", "true")
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session, _fake in make_client(monkeypatch):
        project = add_project(session)
        add_device(session, "device-a")
        add_device(session, "device-b")
        workspace = add_workspace(session, "device-a")
        app_thread = AppThread(
            project_id=project.id,
            title="Agent chat",
            device_id="device-a",
            workspace_id=workspace.id,
            agent_session_id="agent-session-1",
            app_thread_id="codex-thread-1",
            status="ACTIVE",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(app_thread)
        session.commit()
        session.refresh(app_thread)
        created = client.post(f"/app-threads/{app_thread.id}/turns/async", json={"message": "hello"}).json()
        claim = client.post(
            "/agent/commands/claim",
            headers={"X-Agent-Token": "agent-secret"},
            json={"device_id": "device-a", "claim_request_id": "claim-device-a"},
        ).json()

        response = client.post(
            f"/agent/commands/{created['command_id']}/complete",
            headers={"X-Agent-Token": "agent-secret"},
            json={
                "device_id": "device-b",
                "lease_token": claim["lease_token"],
                "status": AgentCommandStatus.SUCCESS.value,
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "agent_command_device_mismatch"


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
        protected_stream_turn = client.get(f"/app-turns/{turn_id}/stream")
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
        assert protected_stream_turn.status_code == 401
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


def test_app_turn_stream_returns_terminal_final_event(monkeypatch) -> None:
    for client, session, _fake in make_client(monkeypatch):
        project = add_project(session)
        created = create_app_thread(client, project.id)
        turn = client.post(f"/app-threads/{created['id']}/turns", json={"message": "hello"}).json()

        response = client.get(f"/app-turns/{turn['id']}/stream")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "event: status" in response.text
        assert "event: final" in response.text
        assert '"kind":"final"' in response.text


def test_app_turn_stream_returns_terminal_error_event(monkeypatch) -> None:
    for client, session, _fake in make_client(monkeypatch):
        project = add_project(session)
        app_thread = AppThread(
            project_id=project.id,
            title="Chat",
            bridge_thread_id="bridge-1",
            app_thread_id="app-1",
            status="ERROR",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(app_thread)
        session.commit()
        session.refresh(app_thread)
        app_turn = AppTurn(
            app_thread_id=app_thread.id,
            user_message="bad",
            status="FAILED",
            error_message="boom",
            created_at=utc_now(),
            completed_at=utc_now(),
        )
        session.add(app_turn)
        session.commit()
        session.refresh(app_turn)

        response = client.get(f"/app-turns/{app_turn.id}/stream")

        assert response.status_code == 200
        assert "event: error" in response.text
        assert '"message":"boom"' in response.text


def test_app_turn_stream_replays_persisted_events_from_sequence(monkeypatch) -> None:
    for client, session, _fake in make_client(monkeypatch):
        project = add_project(session)
        app_thread = AppThread(
            project_id=project.id,
            title="Chat",
            status="ACTIVE",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(app_thread)
        session.commit()
        session.refresh(app_thread)
        app_turn = AppTurn(
            app_thread_id=app_thread.id,
            user_message="hello",
            status="SUCCESS",
            assistant_final="one two",
            created_at=utc_now(),
            started_at=utc_now(),
            completed_at=utc_now(),
        )
        session.add(app_turn)
        session.commit()
        session.refresh(app_turn)
        session.add(
            TurnEvent(
                turn_id=app_turn.id,
                sequence=1,
                kind="agent/message_delta",
                payload_json='{"event":{"method":"agent/message_delta","params":{"turnId":"codex-turn-1","delta":"one"}}}',
                created_at=utc_now(),
            )
        )
        session.add(
            TurnEvent(
                turn_id=app_turn.id,
                sequence=2,
                kind="agent/message_delta",
                payload_json='{"event":{"method":"agent/message_delta","params":{"turnId":"codex-turn-1","delta":"two"}}}',
                created_at=utc_now(),
            )
        )
        session.commit()

        response = client.get(f"/app-turns/{app_turn.id}/stream?since=1")

        assert response.status_code == 200
        assert "id: 1" not in response.text
        assert "id: 2" in response.text
        assert '"sequence":2' in response.text
        assert '"text":"two"' in response.text
        assert '"text":"one"' not in response.text


def test_app_turn_stream_uses_last_event_id_header(monkeypatch) -> None:
    for client, session, _fake in make_client(monkeypatch):
        project = add_project(session)
        app_thread = AppThread(
            project_id=project.id,
            title="Chat",
            status="ACTIVE",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(app_thread)
        session.commit()
        session.refresh(app_thread)
        app_turn = AppTurn(
            app_thread_id=app_thread.id,
            user_message="hello",
            status="SUCCESS",
            assistant_final="done",
            created_at=utc_now(),
            started_at=utc_now(),
            completed_at=utc_now(),
        )
        session.add(app_turn)
        session.commit()
        session.refresh(app_turn)
        session.add(
            TurnEvent(
                turn_id=app_turn.id,
                sequence=1,
                kind="agent/message_delta",
                payload_json='{"event":{"method":"agent/message_delta","params":{"turnId":"codex-turn-1","delta":"old"}}}',
                created_at=utc_now(),
            )
        )
        session.add(
            TurnEvent(
                turn_id=app_turn.id,
                sequence=2,
                kind="final",
                payload_json='{"assistant_final":"done"}',
                created_at=utc_now(),
            )
        )
        session.commit()

        response = client.get(
            f"/app-turns/{app_turn.id}/stream",
            headers={"Last-Event-ID": "1"},
        )

        assert response.status_code == 200
        assert "id: 1" not in response.text
        assert "id: 2" in response.text
        assert "event: final" in response.text
        assert '"assistant_final":"done"' in response.text


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
        detail = client.get(f"/app-threads/{created['id']}").json()
        assert detail["status"] == "RECOVER_REQUIRED"
        assert detail["last_error"] == "cancelled by user; reopen required before next turn"
        blocked = client.post(f"/app-threads/{created['id']}/turns/async", json={"message": "after cancel"})
        assert blocked.status_code == 409
        assert blocked.json()["detail"]["code"] == "app_thread_not_active"


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
        assert app_thread.status == "RECOVER_REQUIRED"


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
