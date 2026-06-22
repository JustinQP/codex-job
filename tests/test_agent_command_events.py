from __future__ import annotations

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from backend.db import get_session
from backend.main import app
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
