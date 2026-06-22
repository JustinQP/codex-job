from __future__ import annotations

from collections.abc import Generator

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


def register_payload(device_id: str = "device-a") -> dict:
    return {
        "device_id": device_id,
        "display_name": "Desk A",
        "hostname": "host-a",
        "os_name": "Windows",
        "agent_version": "0.1.0",
        "capabilities_json": '{"codex_exec":true}',
    }


def test_agent_register_and_heartbeat_require_agent_token(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    monkeypatch.setenv("API_TOKEN", "api-secret")

    for client, session in make_client():
        del session
        no_token = client.post("/agent/register", json=register_payload())
        wrong_token = client.post(
            "/agent/register",
            headers={"X-Agent-Token": "wrong"},
            json=register_payload(),
        )
        api_token = client.post(
            "/agent/register",
            headers={"X-API-Token": "api-secret"},
            json=register_payload(),
        )
        registered = client.post(
            "/agent/register",
            headers={"X-Agent-Token": "agent-secret"},
            json=register_payload(),
        )
        heartbeat = client.post(
            "/agent/heartbeat",
            headers={"X-Agent-Token": "agent-secret"},
            json={
                "device_id": "device-a",
                "agent_version": "0.1.1",
            },
        )

        assert no_token.status_code == 401
        assert wrong_token.status_code == 401
        assert api_token.status_code == 401
        assert registered.status_code == 200
        assert registered.json()["device_id"] == "device-a"
        assert heartbeat.status_code == 200
        assert heartbeat.json()["agent_version"] == "0.1.1"


def test_agent_token_cannot_call_mobile_api_and_api_token_can_read_devices(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    monkeypatch.setenv("API_TOKEN", "api-secret")

    for client, session in make_client():
        del session
        registered = client.post(
            "/agent/register",
            headers={"X-Agent-Token": "agent-secret"},
            json=register_payload(),
        )
        agent_reads_devices = client.get(
            "/devices",
            headers={"X-Agent-Token": "agent-secret"},
        )
        api_reads_devices = client.get(
            "/devices",
            headers={"X-API-Token": "api-secret"},
        )
        api_heartbeat = client.post(
            "/agent/heartbeat",
            headers={"X-API-Token": "api-secret"},
            json={"device_id": "device-a"},
        )

        assert registered.status_code == 200
        assert agent_reads_devices.status_code == 401
        assert api_reads_devices.status_code == 200
        assert api_reads_devices.json()[0]["device_id"] == "device-a"
        assert api_heartbeat.status_code == 401


def test_agent_write_returns_503_when_agent_token_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("AGENT_TOKEN", raising=False)

    for client, session in make_client():
        del session
        response = client.post("/agent/register", json=register_payload())

        assert response.status_code == 503
