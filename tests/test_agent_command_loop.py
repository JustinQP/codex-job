from __future__ import annotations

from threading import Event
from typing import Any

from agent.api_client import AgentApiError
from agent.command_loop import AgentCommandLoop
from agent.identity import AgentIdentity
from agent.local_state import AgentLocalState


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail_heartbeat_once = False
        self.command: dict[str, Any] | None = {
            "id": "cmd-1",
            "device_id": "device-a",
            "command_type": "fake.echo",
            "payload_json": '{"message":"hello"}',
            "lease_token": "lease-a",
        }
        self.completed: list[dict[str, Any]] = []

    def register(self, payload):
        self.calls.append("register")
        return {"device_id": payload.device_id}

    def heartbeat(self, payload):
        self.calls.append("heartbeat")
        if self.fail_heartbeat_once:
            self.fail_heartbeat_once = False
            raise AgentApiError("temporary network")
        return {"device_id": payload.device_id}

    def sync_workspaces(self, payload):
        self.calls.append("sync")
        return {"synced_count": len(payload.workspaces)}

    def claim_command(self, payload):
        self.calls.append(f"claim:{payload.claim_request_id}")
        return self.command

    def ack_command(self, command_id, payload):
        self.calls.append(f"ack:{command_id}:{payload.lease_token}")
        return self.command or {}

    def renew_command(self, command_id, payload):
        self.calls.append(f"renew:{command_id}:{payload.lease_token}")
        return self.command or {}

    def complete_command(self, command_id, payload):
        self.calls.append(f"complete:{command_id}:{payload.status}")
        self.completed.append(payload.model_dump())
        self.command = None
        return {"id": command_id, "status": payload.status}


def identity() -> AgentIdentity:
    return AgentIdentity(
        device_id="device-a",
        display_name="Desk",
        created_at="2026-01-01T00:00:00+00:00",
    )


def test_fake_command_runs_through_claim_ack_renew_complete(tmp_path) -> None:
    client = FakeClient()
    state = AgentLocalState(tmp_path / "state.json")
    loop = AgentCommandLoop(
        client=client,
        identity=identity(),
        local_state=state,
        poll_interval_seconds=0,
    )

    command = loop.run_once()

    assert command is not None
    assert "heartbeat" in client.calls
    assert any(call.startswith("claim:") for call in client.calls)
    assert "ack:cmd-1:lease-a" in client.calls
    assert "renew:cmd-1:lease-a" in client.calls
    assert "complete:cmd-1:AgentCommandStatus.SUCCESS" in client.calls
    assert state.load_current_command() is None


def test_temporary_network_error_is_retried(tmp_path) -> None:
    client = FakeClient()
    client.fail_heartbeat_once = True
    loop = AgentCommandLoop(
        client=client,
        identity=identity(),
        local_state=AgentLocalState(tmp_path / "state.json"),
        poll_interval_seconds=0,
        max_retries=2,
    )

    command = loop.run_once()

    assert command is not None
    assert client.calls.count("heartbeat") == 2


def test_unsupported_command_type_completes_failed(tmp_path) -> None:
    client = FakeClient()
    client.command["command_type"] = "unknown.command"
    loop = AgentCommandLoop(
        client=client,
        identity=identity(),
        local_state=AgentLocalState(tmp_path / "state.json"),
        poll_interval_seconds=0,
    )

    loop.run_once()

    assert client.completed[0]["status"] == "FAILED"
    assert "unsupported command type" in (client.completed[0]["error_message"] or "")


def test_run_forever_stops_when_stop_event_is_set(tmp_path) -> None:
    client = FakeClient()
    stop_event = Event()

    class StoppingLoop(AgentCommandLoop):
        def run_once(self):
            stop_event.set()
            return None

    loop = StoppingLoop(
        client=client,
        identity=identity(),
        local_state=AgentLocalState(tmp_path / "state.json"),
        poll_interval_seconds=0,
    )

    loop.run_forever(stop_event)

    assert "register" in client.calls
