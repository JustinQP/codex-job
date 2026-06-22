from __future__ import annotations

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine, select
from sqlmodel.pool import StaticPool

from backend.db import get_session
from backend.main import app
from backend.models import AgentCommandStatus, AppThread, AppTurn, Project, TurnEvent, utc_now
from backend.schemas import DeviceRegister
from backend.services import agent_command_service, device_service


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


def auth_headers() -> dict[str, str]:
    return {"X-Agent-Token": "agent-secret"}


def setup_claimed_command(client: TestClient, session: Session):
    device_service.register_device(
        session,
        DeviceRegister(
            device_id="device-a",
            display_name="Desk",
            hostname="host",
            os_name="Windows",
            agent_version="0.1.0",
        ),
    )
    command = agent_command_service.create_command(
        session,
        device_id="device-a",
        command_type="fake.echo",
        idempotency_key="cmd-1",
        payload={"message": "hello"},
    )
    claim = client.post(
        "/agent/commands/claim",
        headers=auth_headers(),
        json={"device_id": "device-a", "claim_request_id": "claim-1"},
    ).json()
    client.post(
        f"/agent/commands/{command.id}/ack",
        headers=auth_headers(),
        json={"device_id": "device-a", "lease_token": claim["lease_token"]},
    )
    return command, claim["lease_token"]


def setup_claimed_turn_command(client: TestClient, session: Session):
    device_service.register_device(
        session,
        DeviceRegister(
            device_id="device-a",
            display_name="Desk",
            hostname="host",
            os_name="Windows",
            agent_version="0.1.0",
        ),
    )
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
    app_thread = AppThread(
        project_id=project.id,
        title="Chat",
        device_id="device-a",
        workspace_id=None,
        agent_session_id="agent-session-1",
        app_thread_id="codex-thread-1",
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
    command = agent_command_service.create_command(
        session,
        device_id="device-a",
        command_type="TURN_START",
        aggregate_type="app_turn",
        aggregate_id=str(app_turn.id),
        idempotency_key=f"turn-start:{app_turn.id}",
        payload={
            "app_thread_id": app_thread.id,
            "app_turn_id": app_turn.id,
            "agent_session_id": "agent-session-1",
            "workspace_id": 1,
            "workspace_key": "repo",
            "message": "hello",
        },
    )
    claim = client.post(
        "/agent/commands/claim",
        headers=auth_headers(),
        json={"device_id": "device-a", "claim_request_id": "claim-turn"},
    ).json()
    client.post(
        f"/agent/commands/{command.id}/ack",
        headers=auth_headers(),
        json={"device_id": "device-a", "lease_token": claim["lease_token"]},
    )
    return app_turn, command, claim["lease_token"]


def event(sequence: int, text: str = "hello") -> dict:
    return {
        "sequence": sequence,
        "kind": "log",
        "payload": {"text": text},
        "created_at": "2026-06-22T00:00:00+00:00",
    }


def test_replayed_command_events_are_deduplicated(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        command, lease_token = setup_claimed_command(client, session)
        body = {
            "device_id": "device-a",
            "lease_token": lease_token,
            "events": [event(1), event(2)],
        }

        first = client.post(f"/agent/commands/{command.id}/events", headers=auth_headers(), json=body)
        replay = client.post(f"/agent/commands/{command.id}/events", headers=auth_headers(), json=body)

        assert first.status_code == 200
        assert first.json()["accepted_count"] == 2
        assert replay.status_code == 200
        assert replay.json()["duplicate_count"] == 2
        assert replay.json()["latest_sequence"] == 2


def test_out_of_order_command_events_are_rejected(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        command, lease_token = setup_claimed_command(client, session)

        response = client.post(
            f"/agent/commands/{command.id}/events",
            headers=auth_headers(),
            json={
                "device_id": "device-a",
                "lease_token": lease_token,
                "events": [event(2), event(1)],
            },
        )

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "out_of_order_command_events"


def test_command_event_sequence_conflict_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        command, lease_token = setup_claimed_command(client, session)
        first = {
            "device_id": "device-a",
            "lease_token": lease_token,
            "events": [event(1, "one")],
        }
        conflict = {
            "device_id": "device-a",
            "lease_token": lease_token,
            "events": [event(1, "changed")],
        }

        assert client.post(f"/agent/commands/{command.id}/events", headers=auth_headers(), json=first).status_code == 200
        response = client.post(f"/agent/commands/{command.id}/events", headers=auth_headers(), json=conflict)

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "command_event_sequence_conflict"


def test_oversized_command_event_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        command, lease_token = setup_claimed_command(client, session)

        response = client.post(
            f"/agent/commands/{command.id}/events",
            headers=auth_headers(),
            json={
                "device_id": "device-a",
                "lease_token": lease_token,
                "events": [event(1, "x" * (17 * 1024))],
            },
        )

        assert response.status_code == 413
        assert response.json()["detail"]["code"] == "command_event_too_large"


def test_turn_start_command_events_are_persisted_as_turn_events(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        app_turn, command, lease_token = setup_claimed_turn_command(client, session)
        body = {
            "device_id": "device-a",
            "lease_token": lease_token,
            "events": [
                event(1, "hel"),
                {
                    "sequence": 2,
                    "kind": "final",
                    "payload": {"assistant_final": "hello"},
                    "created_at": "2026-06-22T00:00:01+00:00",
                },
            ],
        }

        response = client.post(f"/agent/commands/{command.id}/events", headers=auth_headers(), json=body)
        listed = client.get(f"/app-turns/{app_turn.id}/events?since=0&limit=10")

        assert response.status_code == 200
        assert response.json()["accepted_count"] == 2
        assert listed.status_code == 200
        assert listed.json()["turn_id"] == app_turn.id
        events = listed.json()["events"]
        assert [item["sequence"] for item in events] == [1, 2]
        assert events[0]["kind"] == "log"
        assert events[0]["payload"]["text"] == "hel"
        assert events[0]["payload"]["command_id"] == command.id
        assert events[1]["kind"] == "final"
        assert events[1]["payload"]["assistant_final"] == "hello"
        assert session.exec(select(TurnEvent)).all()[0].turn_id == app_turn.id


def test_turn_event_replay_is_idempotent_and_conflicts_on_changed_content(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        app_turn, command, lease_token = setup_claimed_turn_command(client, session)
        first = {
            "device_id": "device-a",
            "lease_token": lease_token,
            "events": [event(1, "one")],
        }
        replay = {
            "device_id": "device-a",
            "lease_token": lease_token,
            "events": [event(1, "one")],
        }
        conflict = {
            "device_id": "device-a",
            "lease_token": lease_token,
            "events": [event(1, "changed")],
        }

        assert client.post(f"/agent/commands/{command.id}/events", headers=auth_headers(), json=first).status_code == 200
        assert client.post(f"/agent/commands/{command.id}/events", headers=auth_headers(), json=replay).status_code == 200
        response = client.post(f"/agent/commands/{command.id}/events", headers=auth_headers(), json=conflict)
        listed = client.get(f"/app-turns/{app_turn.id}/events")

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "command_event_sequence_conflict"
        assert [item["payload"]["text"] for item in listed.json()["events"]] == ["one"]


def test_turn_events_query_pages_by_sequence(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        app_turn, command, lease_token = setup_claimed_turn_command(client, session)
        body = {
            "device_id": "device-a",
            "lease_token": lease_token,
            "events": [event(1, "one"), event(2, "two"), event(3, "three")],
        }
        client.post(f"/agent/commands/{command.id}/events", headers=auth_headers(), json=body)

        first_page = client.get(f"/app-turns/{app_turn.id}/events?since=0&limit=2")
        second_page = client.get(f"/app-turns/{app_turn.id}/events?since=2&limit=2")

        assert first_page.status_code == 200
        assert [item["sequence"] for item in first_page.json()["events"]] == [1, 2]
        assert first_page.json()["next_sequence"] == 2
        assert second_page.status_code == 200
        assert [item["sequence"] for item in second_page.json()["events"]] == [3]
        assert second_page.json()["next_sequence"] is None


def test_turn_final_can_be_cross_checked_between_event_and_app_turn(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        app_turn, command, lease_token = setup_claimed_turn_command(client, session)
        upload = {
            "device_id": "device-a",
            "lease_token": lease_token,
            "events": [
                {
                    "sequence": 1,
                    "kind": "final",
                    "payload": {"assistant_final": "final answer"},
                    "created_at": "2026-06-22T00:00:01+00:00",
                },
            ],
        }
        complete = {
            "device_id": "device-a",
            "lease_token": lease_token,
            "status": AgentCommandStatus.SUCCESS.value,
            "result_payload": {
                "app_turn_id": app_turn.id,
                "codex_turn_id": "codex-turn-1",
                "assistant_final": "final answer",
                "event_summary": {"total_events": 1, "assistant_text_preview": "final answer"},
            },
        }

        assert client.post(f"/agent/commands/{command.id}/events", headers=auth_headers(), json=upload).status_code == 200
        assert client.post(f"/agent/commands/{command.id}/complete", headers=auth_headers(), json=complete).status_code == 200
        turn_body = client.get(f"/app-turns/{app_turn.id}").json()
        events_body = client.get(f"/app-turns/{app_turn.id}/events").json()

        assert turn_body["assistant_final"] == "final answer"
        assert events_body["events"][0]["kind"] == "final"
        assert events_body["events"][0]["payload"]["assistant_final"] == turn_body["assistant_final"]
