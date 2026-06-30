from __future__ import annotations

import os
from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine, select
from sqlmodel.pool import StaticPool

from backend.db import get_session
from backend.main import app
from backend.models import AgentCommandStatus, AppThread, AppTurn, Project, TurnEvent, utc_now
from backend.schemas import DeviceRegister
from backend.services import agent_command_service, device_service, workspace_service
from backend.schemas import WorkspaceSyncItem, WorkspaceSyncRequest


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
            client.headers.update({"X-API-Token": os.environ["API_TOKEN"]})
            yield client, session
    finally:
        app.dependency_overrides.clear()
        session.close()


def auth_headers() -> dict[str, str]:
    return {"X-Agent-Token": "agent-secret"}


def register_device(session: Session, device_id: str) -> None:
    device_service.register_device(
        session,
        DeviceRegister(
            device_id=device_id,
            display_name=device_id,
            hostname=device_id,
            os_name="Windows",
            agent_version="0.1.0",
        ),
    )


def sync_same_named_workspace(session: Session, device_id: str):
    result = workspace_service.sync_device_workspaces(
        session,
        WorkspaceSyncRequest(
            device_id=device_id,
            workspaces=[
                WorkspaceSyncItem(
                    workspace_key="repo",
                    name="Same Repo",
                    path_label="codex-job",
                    default_sandbox="read-only",
                )
            ],
        ),
    )
    return result.workspaces[0]


def claim(client: TestClient, device_id: str, request_id: str):
    response = client.post(
        "/agent/commands/claim",
        headers=auth_headers(),
        json={"device_id": device_id, "claim_request_id": request_id},
    )
    assert response.status_code == 200
    return response.json()


def ack(client: TestClient, command: dict) -> None:
    response = client.post(
        f"/agent/commands/{command['id']}/ack",
        headers=auth_headers(),
        json={"device_id": command["device_id"], "lease_token": command["lease_token"]},
    )
    assert response.status_code == 200


def upload_events(client: TestClient, command: dict, events: list[dict]):
    response = client.post(
        f"/agent/commands/{command['id']}/events",
        headers=auth_headers(),
        json={
            "device_id": command["device_id"],
            "lease_token": command["lease_token"],
            "events": events,
        },
    )
    assert response.status_code == 200
    return response.json()


def complete_success(client: TestClient, command: dict, result_payload: dict | None = None) -> dict:
    response = client.post(
        f"/agent/commands/{command['id']}/complete",
        headers=auth_headers(),
        json={
            "device_id": command["device_id"],
            "lease_token": command["lease_token"],
            "status": AgentCommandStatus.SUCCESS.value,
            "result_payload": result_payload or {},
        },
    )
    assert response.status_code == 200
    return response.json()


def event(sequence: int, text: str) -> dict:
    return {
        "sequence": sequence,
        "kind": "agent/message_delta",
        "payload": {"event": {"method": "agent/message_delta", "params": {"turnId": "codex-turn", "delta": text}}},
        "created_at": "2026-06-22T00:00:00+00:00",
    }


def test_two_fake_agents_route_commands_events_and_reconcile(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        register_device(session, "fake-a")
        register_device(session, "fake-b")
        workspace_a = sync_same_named_workspace(session, "fake-a")
        workspace_b = sync_same_named_workspace(session, "fake-b")
        project = Project(
            name="demo",
            path="E:\\demo",
            workspace_id=workspace_a.id,
            enabled=True,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(project)
        session.commit()
        session.refresh(project)

        assert workspace_a.name == workspace_b.name
        assert workspace_a.id != workspace_b.id
        assert workspace_a.device_id == "fake-a"
        assert workspace_b.device_id == "fake-b"

        command_a = agent_command_service.create_command(
            session,
            device_id="fake-a",
            command_type="RUN_EXECUTE",
            aggregate_type="run",
            aggregate_id="run-a",
            idempotency_key="run-a",
            workspace_id=workspace_a.id,
            payload={"run_id": "run-a", "workspace_id": workspace_a.id},
        )
        command_b = agent_command_service.create_command(
            session,
            device_id="fake-b",
            command_type="RUN_EXECUTE",
            aggregate_type="run",
            aggregate_id="run-b",
            idempotency_key="run-b",
            workspace_id=workspace_b.id,
            payload={"run_id": "run-b", "workspace_id": workspace_b.id},
        )

        a_claim = claim(client, "fake-a", "claim-a")
        repeated_a_claim = claim(client, "fake-a", "claim-a")
        b_claim = claim(client, "fake-b", "claim-b")
        assert a_claim["id"] == command_a.id
        assert repeated_a_claim["id"] == command_a.id
        assert b_claim["id"] == command_b.id
        assert a_claim["id"] != b_claim["id"]
        assert claim(client, "fake-a", "claim-a-empty") is None

        ack(client, a_claim)
        ack(client, b_claim)
        assert complete_success(client, a_claim)["status"] == "SUCCESS"
        assert complete_success(client, b_claim)["status"] == "SUCCESS"

        app_thread = AppThread(
            project_id=project.id,
            title="Chat A",
            device_id="fake-a",
            workspace_id=workspace_a.id,
            agent_session_id="agent-session-a",
            app_thread_id="codex-thread-a",
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
            status="RUNNING",
            created_at=utc_now(),
            started_at=utc_now(),
        )
        session.add(app_turn)
        session.commit()
        session.refresh(app_turn)
        turn_command = agent_command_service.create_command(
            session,
            device_id="fake-a",
            command_type="TURN_START",
            aggregate_type="app_turn",
            aggregate_id=str(app_turn.id),
            idempotency_key=f"turn-start:{app_turn.id}",
            workspace_id=workspace_a.id,
            payload={
                "app_thread_id": app_thread.id,
                "app_turn_id": app_turn.id,
                "agent_session_id": "agent-session-a",
                "workspace_id": workspace_a.id,
                "workspace_key": workspace_a.workspace_key,
                "message": "hello",
            },
        )
        turn_claim = claim(client, "fake-a", "claim-turn-a")
        assert turn_claim["id"] == turn_command.id
        ack(client, turn_claim)
        first_upload = upload_events(client, turn_claim, [event(1, "hel"), event(2, "lo")])
        replay_upload = upload_events(client, turn_claim, [event(1, "hel"), event(2, "lo")])
        assert first_upload["accepted_count"] == 2
        assert replay_upload["duplicate_count"] == 2
        assert len(session.exec(select(TurnEvent).where(TurnEvent.turn_id == app_turn.id)).all()) == 2

        reconcile_upload = client.post(
            "/agent/reconcile",
            headers=auth_headers(),
            json={
                "device_id": "fake-a",
                "command_id": turn_command.id,
                "process_status": "RUNNING",
                "last_uploaded_sequence": 3,
            },
        )
        assert reconcile_upload.status_code == 200
        assert reconcile_upload.json()["action"] == "UPLOAD_EVENTS"
        assert reconcile_upload.json()["latest_sequence"] == 2

        complete_success(
            client,
            turn_claim,
            {
                "app_turn_id": app_turn.id,
                "agent_session_id": "agent-session-a",
                "codex_turn_id": "codex-turn-a",
                "assistant_final": "hello",
                "event_summary": {"total_events": 2, "assistant_text_preview": "hello"},
            },
        )
        session.refresh(app_turn)
        session.refresh(app_thread)
        assert app_turn.status == "SUCCESS"
        assert app_turn.assistant_final == "hello"
        assert app_thread.status == "ACTIVE"

        listed_events = client.get(f"/app-turns/{app_turn.id}/events?since=0&limit=10")
        stream = client.get(f"/app-turns/{app_turn.id}/stream?since=1")
        assert listed_events.status_code == 200
        assert [item["sequence"] for item in listed_events.json()["events"]] == [1, 2]
        assert stream.status_code == 200
        assert "id: 1" not in stream.text
        assert "id: 2" in stream.text
        assert '"text":"lo"' in stream.text

        reconcile_stop = client.post(
            "/agent/reconcile",
            headers=auth_headers(),
            json={
                "device_id": "fake-a",
                "command_id": turn_command.id,
                "process_status": "STARTING",
                "last_uploaded_sequence": 2,
            },
        )
        assert reconcile_stop.status_code == 200
        assert reconcile_stop.json()["action"] == "STOP"
        assert reconcile_stop.json()["server_status"] == "SUCCESS"
