from __future__ import annotations

from threading import Event
from typing import Any

from agent.api_client import AgentApiError
from agent.command_handlers import CommandResult
from agent.command_loop import AgentCommandLoop
from agent.identity import AgentIdentity
from agent.local_state import AgentLocalState, CurrentCommandState, PendingCommandEvent
from agent.process_registry import ProcessRegistry
from agent.workspace_registry import WorkspaceRegistry


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
        self.reconciliations: list[Any] = []
        self.event_uploads: list[tuple[str, Any]] = []
        self.fail_complete_once = False

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

    def reconcile(self, payload):
        self.calls.append("reconcile")
        self.reconciliations.append(payload)
        return {"action": "IDLE"}

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
        if self.fail_complete_once:
            self.fail_complete_once = False
            raise AgentApiError("response lost")
        self.completed.append(payload.model_dump())
        self.command = None
        return {"id": command_id, "status": payload.status}

    def upload_command_events(self, command_id, payload):
        self.calls.append(f"events:{command_id}")
        self.event_uploads.append((command_id, payload))
        latest_sequence = max((event.sequence for event in payload.events), default=None)
        return {
            "accepted_count": len(payload.events),
            "duplicate_count": 0,
            "latest_sequence": latest_sequence,
        }


class CountingHandler:
    def __init__(self) -> None:
        self.count = 0

    def handle(self, command):
        self.count += 1
        return CommandResult(True, "handled")


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


def test_complete_retry_does_not_execute_handler_twice(tmp_path) -> None:
    client = FakeClient()
    client.fail_complete_once = True
    state = AgentLocalState(tmp_path / "state.json")
    loop = AgentCommandLoop(
        client=client,
        identity=identity(),
        local_state=state,
        poll_interval_seconds=0,
        max_retries=1,
    )

    try:
        loop.run_once()
    except AgentApiError:
        pass
    else:
        raise AssertionError("expected first complete to fail")

    pending = state.load_current_command()
    assert pending is not None
    assert pending.phase == "COMPLETION_PENDING"
    first_calls = list(client.calls)

    loop.run_once()

    assert client.calls.count("ack:cmd-1:lease-a") == first_calls.count("ack:cmd-1:lease-a")
    assert client.calls.count("renew:cmd-1:lease-a") == first_calls.count("renew:cmd-1:lease-a")
    assert len(client.completed) == 1
    assert state.load_current_command() is None


def test_completion_pending_after_process_restart_does_not_execute_handler_again(tmp_path) -> None:
    client = FakeClient()
    client.fail_complete_once = True
    state = AgentLocalState(tmp_path / "state.json")
    first_handler = CountingHandler()
    first_loop = AgentCommandLoop(
        client=client,
        identity=identity(),
        local_state=state,
        handlers=type("Handlers", (), {"handle": first_handler.handle})(),
        poll_interval_seconds=0,
        max_retries=1,
    )

    try:
        first_loop.run_once()
    except AgentApiError:
        pass
    else:
        raise AssertionError("expected first complete to fail")

    second_handler = CountingHandler()
    restarted_loop = AgentCommandLoop(
        client=client,
        identity=identity(),
        local_state=state,
        handlers=type("Handlers", (), {"handle": second_handler.handle})(),
        poll_interval_seconds=0,
    )
    restarted_loop.run_once()

    assert first_handler.count == 1
    assert second_handler.count == 0
    assert len(client.completed) == 1
    assert state.load_current_command() is None


def test_executing_command_after_agent_restart_completes_failed_without_rerun(tmp_path) -> None:
    client = FakeClient()
    state = AgentLocalState(tmp_path / "state.json")
    state.save_current_command(
        CurrentCommandState(
            command_id="cmd-1",
            claim_request_id="claim-restart",
            lease_token="lease-a",
            phase="EXECUTING",
        )
    )
    handler = CountingHandler()
    handlers = type("Handlers", (), {"handle": handler.handle})()
    loop = AgentCommandLoop(
        client=client,
        identity=identity(),
        local_state=state,
        handlers=handlers,
        poll_interval_seconds=0,
    )

    loop.run_once()

    assert handler.count == 0
    assert client.completed[0]["status"] == "FAILED"
    assert "not retried" in (client.completed[0]["error_message"] or "")
    assert state.load_current_command() is None


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


def test_run_forever_starts_background_heartbeat_during_blocking_handler(tmp_path) -> None:
    class BlockingLoop(AgentCommandLoop):
        def run_once(self):
            if self.client.calls.count("heartbeat") >= 2:
                stop_event.set()
            else:
                stop_event.wait(0.05)
            return None

    client = FakeClient()
    stop_event = Event()
    loop = BlockingLoop(
        client=client,
        identity=identity(),
        local_state=AgentLocalState(tmp_path / "state.json"),
        poll_interval_seconds=0.01,
        heartbeat_interval_seconds=0.01,
    )

    loop.run_forever(stop_event)

    assert client.calls.count("heartbeat") >= 2


def test_command_loop_injects_process_registry_into_run_executor(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    registry_path = tmp_path / "workspaces.json"
    registry_path.write_text(
        '{"allowed_roots":["%s"],"workspaces":[{"key":"repo","name":"Repo","path":"%s"}]}'
        % (str(tmp_path).replace("\\", "\\\\"), str(repo).replace("\\", "\\\\")),
        encoding="utf-8",
    )
    process_registry = ProcessRegistry()

    loop = AgentCommandLoop(
        client=FakeClient(),
        identity=identity(),
        local_state=AgentLocalState(tmp_path / "state.json"),
        workspace_registry=WorkspaceRegistry.load(registry_path),
        process_registry=process_registry,
        poll_interval_seconds=0,
    )

    run_executor = loop.handlers._handlers["RUN_EXECUTE"]

    assert run_executor.client is loop.client
    assert run_executor.device_id == "device-a"
    assert run_executor.process_registry is process_registry


def test_bootstrap_reconcile_reports_pending_event_sequence(tmp_path) -> None:
    client = FakeClient()
    state = AgentLocalState(tmp_path / "state.json")
    state.save_current_command(
        CurrentCommandState(
            command_id="cmd-1",
            claim_request_id="claim-1",
            lease_token="lease-a",
        )
    )
    state.append_pending_event(
        PendingCommandEvent(
            command_id="cmd-1",
            sequence=3,
            kind="log",
            payload={"text": "three"},
            created_at="2026-06-22T00:00:03+00:00",
        )
    )

    loop = AgentCommandLoop(
        client=client,
        identity=identity(),
        local_state=state,
        poll_interval_seconds=0,
    )
    loop.bootstrap()

    assert client.reconciliations[-1].last_uploaded_sequence == 3


def test_bootstrap_reconcile_uploads_missing_pending_events(tmp_path) -> None:
    class UploadRequestClient(FakeClient):
        def reconcile(self, payload):
            self.calls.append("reconcile")
            self.reconciliations.append(payload)
            return {
                "action": "UPLOAD_EVENTS",
                "command_id": "cmd-1",
                "upload_from_sequence": 2,
                "latest_sequence": 1,
            }

    client = UploadRequestClient()
    state = AgentLocalState(tmp_path / "state.json")
    state.save_current_command(
        CurrentCommandState(
            command_id="cmd-1",
            claim_request_id="claim-1",
            lease_token="lease-a",
        )
    )
    for sequence in (1, 2, 3):
        state.append_pending_event(
            PendingCommandEvent(
                command_id="cmd-1",
                sequence=sequence,
                kind="log",
                payload={"text": str(sequence)},
                created_at=f"2026-06-22T00:00:0{sequence}+00:00",
            )
        )

    loop = AgentCommandLoop(
        client=client,
        identity=identity(),
        local_state=state,
        poll_interval_seconds=0,
    )
    loop.bootstrap()

    assert client.event_uploads
    _command_id, upload_payload = client.event_uploads[-1]
    assert [event.sequence for event in upload_payload.events] == [2, 3]
    assert [event.sequence for event in state.load_pending_events("cmd-1")] == [1]
