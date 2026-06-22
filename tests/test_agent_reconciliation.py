from __future__ import annotations

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from backend.db import get_session
from backend.main import app
from backend.models import AgentCommandStatus
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


def add_device(session: Session) -> None:
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


def create_command(session: Session):
    return agent_command_service.create_command(
        session,
        device_id="device-a",
        command_type="fake.echo",
        idempotency_key="cmd-1",
        payload={"message": "hello"},
    )


def claim_command(client: TestClient, command_id: str) -> str:
    claim = client.post(
        "/agent/commands/claim",
        headers=auth_headers(),
        json={"device_id": "device-a", "claim_request_id": "claim-1"},
    ).json()
    client.post(
        f"/agent/commands/{command_id}/ack",
        headers=auth_headers(),
        json={"device_id": "device-a", "lease_token": claim["lease_token"]},
    )
    return claim["lease_token"]


def test_reconcile_stops_success_command_after_agent_restart(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        add_device(session)
        command = create_command(session)
        lease_token = claim_command(client, command.id)
        client.post(
            f"/agent/commands/{command.id}/complete",
            headers=auth_headers(),
            json={"device_id": "device-a", "lease_token": lease_token, "status": "SUCCESS"},
        )

        response = client.post(
            "/agent/reconcile",
            headers=auth_headers(),
            json={
                "device_id": "device-a",
                "command_id": command.id,
                "process_status": "STARTING",
                "last_uploaded_sequence": 0,
            },
        )

        assert response.status_code == 200
        assert response.json()["action"] == "STOP"
        assert response.json()["server_status"] == "SUCCESS"


def test_reconcile_requests_unconfirmed_event_upload(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        add_device(session)
        command = create_command(session)
        lease_token = claim_command(client, command.id)
        upload = client.post(
            f"/agent/commands/{command.id}/events",
            headers=auth_headers(),
            json={
                "device_id": "device-a",
                "lease_token": lease_token,
                "events": [
                    {
                        "sequence": 1,
                        "kind": "log",
                        "payload": {"text": "one"},
                        "created_at": "2026-06-22T00:00:00+00:00",
                    }
                ],
            },
        )
        assert upload.status_code == 200

        response = client.post(
            "/agent/reconcile",
            headers=auth_headers(),
            json={
                "device_id": "device-a",
                "command_id": command.id,
                "process_status": "STARTING",
                "last_uploaded_sequence": 2,
            },
        )

        assert response.status_code == 200
        assert response.json()["action"] == "UPLOAD_EVENTS"
        assert response.json()["upload_from_sequence"] == 2
        assert response.json()["latest_sequence"] == 1


def test_reconcile_stops_cancelled_command(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        add_device(session)
        command = create_command(session)
        agent_command_service.transition_command(
            session,
            command,
            AgentCommandStatus.CANCELLED,
        )

        response = client.post(
            "/agent/reconcile",
            headers=auth_headers(),
            json={
                "device_id": "device-a",
                "command_id": command.id,
                "process_status": "STARTING",
            },
        )

        assert response.status_code == 200
        assert response.json()["action"] == "STOP"
        assert response.json()["reason"] == "server command is cancelled"


def test_reconcile_without_local_command_keeps_pending_queue(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        add_device(session)
        command = create_command(session)

        response = client.post(
            "/agent/reconcile",
            headers=auth_headers(),
            json={"device_id": "device-a", "process_status": "STARTING"},
        )
        claim = client.post(
            "/agent/commands/claim",
            headers=auth_headers(),
            json={"device_id": "device-a", "claim_request_id": "claim-after-reconcile"},
        )

        assert response.status_code == 200
        assert response.json()["action"] == "IDLE"
        assert claim.status_code == 200
        assert claim.json()["id"] == command.id
