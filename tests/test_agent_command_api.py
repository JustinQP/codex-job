from __future__ import annotations

from collections.abc import Generator
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from backend.db import get_session
from backend.main import app
from backend.models import AgentCommand, utc_now
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


def add_device(session: Session, device_id: str) -> None:
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


def create_command(session: Session, device_id: str, key: str):
    return agent_command_service.create_command(
        session,
        device_id=device_id,
        command_type="codex.exec",
        aggregate_type="run",
        aggregate_id=key,
        idempotency_key=key,
        payload={"run_id": key},
    )


def auth_headers() -> dict[str, str]:
    return {"X-Agent-Token": "agent-secret"}


def test_repeated_claim_request_returns_same_command(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        add_device(session, "device-a")
        first_command = create_command(session, "device-a", "cmd-1")
        second_command = create_command(session, "device-a", "cmd-2")

        first_claim = client.post(
            "/agent/commands/claim",
            headers=auth_headers(),
            json={"device_id": "device-a", "claim_request_id": "claim-1"},
        )
        repeated_claim = client.post(
            "/agent/commands/claim",
            headers=auth_headers(),
            json={"device_id": "device-a", "claim_request_id": "claim-1"},
        )

        assert first_claim.status_code == 200
        assert repeated_claim.status_code == 200
        assert first_claim.json()["id"] == first_command.id
        assert repeated_claim.json()["id"] == first_command.id
        assert second_command.id not in {first_claim.json()["id"], repeated_claim.json()["id"]}


def test_agent_cannot_claim_other_device_command(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        add_device(session, "device-a")
        add_device(session, "device-b")
        create_command(session, "device-b", "cmd-b")

        claim = client.post(
            "/agent/commands/claim",
            headers=auth_headers(),
            json={"device_id": "device-a", "claim_request_id": "claim-a"},
        )

        assert claim.status_code == 200
        assert claim.json() is None


def test_ack_renew_and_complete_require_valid_lease_token(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        add_device(session, "device-a")
        create_command(session, "device-a", "cmd-1")
        claim = client.post(
            "/agent/commands/claim",
            headers=auth_headers(),
            json={"device_id": "device-a", "claim_request_id": "claim-1"},
        ).json()

        bad_ack = client.post(
            f"/agent/commands/{claim['id']}/ack",
            headers=auth_headers(),
            json={"device_id": "device-a", "lease_token": "wrong"},
        )
        ack = client.post(
            f"/agent/commands/{claim['id']}/ack",
            headers=auth_headers(),
            json={"device_id": "device-a", "lease_token": claim["lease_token"]},
        )
        renew = client.post(
            f"/agent/commands/{claim['id']}/renew",
            headers=auth_headers(),
            json={"device_id": "device-a", "lease_token": claim["lease_token"]},
        )
        complete = client.post(
            f"/agent/commands/{claim['id']}/complete",
            headers=auth_headers(),
            json={
                "device_id": "device-a",
                "lease_token": claim["lease_token"],
                "status": "SUCCESS",
            },
        )
        repeated_complete = client.post(
            f"/agent/commands/{claim['id']}/complete",
            headers=auth_headers(),
            json={
                "device_id": "device-a",
                "lease_token": claim["lease_token"],
                "status": "SUCCESS",
            },
        )

        assert bad_ack.status_code == 409
        assert bad_ack.json()["detail"]["code"] == "invalid_lease_token"
        assert ack.status_code == 200
        assert ack.json()["status"] == "RUNNING"
        assert renew.status_code == 200
        assert complete.status_code == 200
        assert complete.json()["status"] == "SUCCESS"
        assert repeated_complete.status_code == 200
        assert repeated_complete.json()["id"] == claim["id"]


def test_expired_lease_marks_command_expired_without_requeue(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        add_device(session, "device-a")
        create_command(session, "device-a", "cmd-1")
        claim = client.post(
            "/agent/commands/claim",
            headers=auth_headers(),
            json={"device_id": "device-a", "claim_request_id": "claim-1"},
        ).json()
        command = session.get(AgentCommand, claim["id"])
        command.lease_expires_at = utc_now() - timedelta(seconds=1)
        session.add(command)
        session.commit()

        renew = client.post(
            f"/agent/commands/{claim['id']}/renew",
            headers=auth_headers(),
            json={"device_id": "device-a", "lease_token": claim["lease_token"]},
        )
        next_claim = client.post(
            "/agent/commands/claim",
            headers=auth_headers(),
            json={"device_id": "device-a", "claim_request_id": "claim-2"},
        )

        assert renew.status_code == 409
        assert renew.json()["detail"]["code"] == "lease_expired"
        assert next_claim.status_code == 200
        assert next_claim.json() is None
        session.refresh(command)
        assert command.status == "EXPIRED"
