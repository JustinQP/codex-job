from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent.app_server.event_parser import extract_assistant_text, summarize_events
from agent.app_server.session_manager import AgentAppSessionManager
from agent.session_handlers import SessionOpenHandler
from agent.workspace_registry import WorkspaceRegistry


class FakeJsonlRpcClient:
    instances: list["FakeJsonlRpcClient"] = []

    def __init__(
        self,
        command: list[str],
        cwd: Path,
        events_path: Path,
        stderr_path: Path,
    ) -> None:
        self.command = command
        self.cwd = cwd
        self.events_path = events_path
        self.stderr_path = stderr_path
        self.requests: list[dict[str, Any]] = []
        self.closed = False
        self.thread_id = f"codex-thread-{len(self.instances) + 1}"
        self.turn_count = 0
        self.turn_id = f"codex-turn-{len(self.instances) + 1}-0"
        self._messages: list[dict[str, Any]] = []
        self._condition = _NoopCondition(self)
        self.instances.append(self)

    @property
    def message_count(self) -> int:
        return len(self._messages)

    def request(self, request_id: str, method: str, params: dict[str, Any] | None = None) -> None:
        self.requests.append({"id": request_id, "method": method, "params": params or {}})
        if method == "turn/start":
            self.turn_count += 1
            self.turn_id = f"{self.thread_id}-turn-{self.turn_count}"
            self._messages.extend(
                [
                    {
                        "id": request_id,
                        "result": {"turn": {"id": self.turn_id}},
                    },
                    {
                        "method": "agent/message_delta",
                        "params": {"turnId": self.turn_id, "itemId": "a", "delta": f"hello-{self.turn_count}"},
                    },
                    {
                        "method": "turn/completed",
                        "params": {"turnId": self.turn_id},
                    },
                ]
            )

    def wait_for_response(self, request_id: str, timeout: float) -> dict[str, Any]:
        del timeout
        if request_id.endswith("-initialize"):
            return {"id": request_id, "result": {"ok": True}}
        if request_id.endswith("-thread-start"):
            return {"id": request_id, "result": {"thread": {"id": self.thread_id}}}
        if "-turn-" in request_id:
            return {"id": request_id, "result": {"turn": {"id": self.turn_id}}}
        raise AssertionError(f"unexpected request id: {request_id}")

    def wait_for_match(self, predicate, timeout: float, start_index: int = 0):
        del timeout
        for index, message in enumerate(self._messages[start_index:], start=start_index):
            if predicate(message):
                return index, message
        raise AssertionError("no matching message")

    def close(self) -> None:
        self.closed = True


class HangingJsonlRpcClient(FakeJsonlRpcClient):
    def request(self, request_id: str, method: str, params: dict[str, Any] | None = None) -> None:
        self.requests.append({"id": request_id, "method": method, "params": params or {}})
        if method == "turn/start":
            self.turn_count += 1
            self.turn_id = f"{self.thread_id}-turn-{self.turn_count}"
            self._messages.append({"id": request_id, "result": {"turn": {"id": self.turn_id}}})

    def wait_for_match(self, predicate, timeout: float, start_index: int = 0):
        del timeout
        for index, message in enumerate(self._messages[start_index:], start=start_index):
            if predicate(message):
                return index, message
        raise TimeoutError("timed out waiting for app-server JSONL message")


class _NoopCondition:
    def __init__(self, client: FakeJsonlRpcClient) -> None:
        self.client = client

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class FakeUploader:
    def __init__(self) -> None:
        self.cached: list[dict[str, Any]] = []
        self.flushed: list[dict[str, str]] = []

    def cache_event(self, *, command_id: str, sequence: int, kind: str, payload: dict[str, Any]) -> None:
        self.cached.append(
            {
                "command_id": command_id,
                "sequence": sequence,
                "kind": kind,
                "payload": payload,
            }
        )

    def flush(self, *, command_id: str, device_id: str, lease_token: str) -> dict[str, Any]:
        self.flushed.append(
            {
                "command_id": command_id,
                "device_id": device_id,
                "lease_token": lease_token,
            }
        )
        return {"latest_sequence": self.cached[-1]["sequence"]}


def test_session_manager_opens_isolated_sessions_per_workspace(tmp_path: Path) -> None:
    FakeJsonlRpcClient.instances.clear()
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    manager = AgentAppSessionManager(
        workspace_registry=WorkspaceRegistry.load(_registry(tmp_path, repo_a, repo_b)),
        codex_command="codex.cmd",
        data_dir=tmp_path / "agent-app-server",
        client_factory=FakeJsonlRpcClient,
    )

    session_a = manager.open_session(workspace_key="repo-a", title="A")
    session_b = manager.open_session(workspace_key="repo-b", title="B", sandbox="workspace-write")

    assert session_a.cwd == repo_a.resolve()
    assert session_b.cwd == repo_b.resolve()
    assert session_a.agent_session_id != session_b.agent_session_id
    assert session_a.codex_thread_id == "codex-thread-1"
    assert session_b.codex_thread_id == "codex-thread-2"
    assert FakeJsonlRpcClient.instances[0].command == ["codex.cmd", "app-server", "--listen", "stdio://"]
    assert FakeJsonlRpcClient.instances[0].requests[1]["method"] == "thread/start"
    assert FakeJsonlRpcClient.instances[0].requests[1]["params"]["cwd"] == str(repo_a.resolve())
    assert FakeJsonlRpcClient.instances[1].requests[1]["params"]["cwd"] == str(repo_b.resolve())
    assert FakeJsonlRpcClient.instances[1].requests[1]["params"]["sandbox"] == "workspace-write"
    assert manager.get_session(session_a.agent_session_id) is session_a

    assert manager.close_session(session_a.agent_session_id) is True
    assert FakeJsonlRpcClient.instances[0].closed is True
    assert manager.close_session("missing") is False
    manager.close_all()
    assert FakeJsonlRpcClient.instances[1].closed is True


def test_agent_event_parser_entrypoint_matches_poc_behavior() -> None:
    events = [
        {"method": "agent/message_delta", "params": {"itemId": "a", "delta": "hel"}},
        {"method": "agent/message_delta", "params": {"itemId": "a", "delta": "lo"}},
    ]

    assert extract_assistant_text(events) == "hello"
    assert summarize_events(events)["assistant_text_preview"] == "hello"


def test_session_open_handler_returns_agent_session_payload(tmp_path: Path) -> None:
    FakeJsonlRpcClient.instances.clear()
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    manager = AgentAppSessionManager(
        workspace_registry=WorkspaceRegistry.load(_registry(tmp_path, repo_a, repo_b)),
        data_dir=tmp_path / "agent-app-server",
        client_factory=FakeJsonlRpcClient,
    )
    handler = SessionOpenHandler(manager)

    result = handler.handle(
        {
            "id": "cmd-1",
            "command_type": "SESSION_OPEN",
            "payload_json": json.dumps(
                {
                    "workspace_key": "repo-a",
                    "title": "Chat",
                    "sandbox": "workspace-write",
                    "approval_policy": "never",
                    "network_access": False,
                }
            ),
        }
    )

    assert result.success is True
    assert result.result_payload is not None
    assert result.result_payload["agent_session_id"]
    assert result.result_payload["codex_thread_id"] == "codex-thread-1"
    assert FakeJsonlRpcClient.instances[0].requests[1]["params"]["cwd"] == str(repo_a.resolve())


def test_session_open_handler_rejects_cwd_in_payload(tmp_path: Path) -> None:
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    manager = AgentAppSessionManager(
        workspace_registry=WorkspaceRegistry.load(_registry(tmp_path, repo_a, repo_b)),
        data_dir=tmp_path / "agent-app-server",
        client_factory=FakeJsonlRpcClient,
    )

    result = SessionOpenHandler(manager).handle(
        {
            "id": "cmd-1",
            "command_type": "SESSION_OPEN",
            "payload_json": json.dumps({"workspace_key": "repo-a", "cwd": str(repo_a)}),
        }
    )

    assert result.success is False
    assert result.message == "session open payload must not specify cwd"


def test_session_manager_runs_turn_on_existing_session_and_uploads_events(tmp_path: Path) -> None:
    FakeJsonlRpcClient.instances.clear()
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    manager = AgentAppSessionManager(
        workspace_registry=WorkspaceRegistry.load(_registry(tmp_path, repo_a, repo_b)),
        data_dir=tmp_path / "agent-app-server",
        client_factory=FakeJsonlRpcClient,
    )
    session = manager.open_session(workspace_key="repo-a", title="Chat")
    uploader = FakeUploader()

    result = manager.run_turn(
        agent_session_id=session.agent_session_id,
        message="hello",
        command_id="cmd-1",
        uploader=uploader,
        device_id="device-a",
        lease_token="lease-a",
    )

    client = FakeJsonlRpcClient.instances[0]
    assert result.codex_turn_id == "codex-thread-1-turn-1"
    assert result.assistant_final == "hello-1"
    assert result.event_summary["total_events"] == 3
    assert session.turn_count == 1
    assert client.requests[2]["method"] == "turn/start"
    assert client.requests[2]["params"]["threadId"] == session.codex_thread_id
    assert client.requests[2]["params"]["cwd"] == str(repo_a.resolve())
    assert [event["kind"] for event in uploader.cached] == [
        "status",
        "response",
        "agent/message_delta",
        "turn/completed",
        "final",
    ]
    assert [event["sequence"] for event in uploader.cached] == [1, 2, 3, 4, 5]
    assert all(flush["device_id"] == "device-a" for flush in uploader.flushed)


def test_session_manager_keeps_turn_running_when_event_flush_fails(tmp_path: Path) -> None:
    class FailingUploader(FakeUploader):
        def flush(self, *, command_id: str, device_id: str, lease_token: str) -> dict[str, Any]:
            super().flush(command_id=command_id, device_id=device_id, lease_token=lease_token)
            raise RuntimeError("network down")

    FakeJsonlRpcClient.instances.clear()
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    manager = AgentAppSessionManager(
        workspace_registry=WorkspaceRegistry.load(_registry(tmp_path, repo_a, repo_b)),
        data_dir=tmp_path / "agent-app-server",
        client_factory=FakeJsonlRpcClient,
    )
    session = manager.open_session(workspace_key="repo-a", title="Chat")
    uploader = FailingUploader()

    result = manager.run_turn(
        agent_session_id=session.agent_session_id,
        message="hello",
        command_id="cmd-1",
        uploader=uploader,
        device_id="device-a",
        lease_token="lease-a",
    )

    assert result.assistant_final == "hello-1"
    assert [event["sequence"] for event in uploader.cached] == [1, 2, 3, 4, 5]


def test_session_manager_closes_session_when_turn_is_cancelled(tmp_path: Path) -> None:
    FakeJsonlRpcClient.instances.clear()
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    manager = AgentAppSessionManager(
        workspace_registry=WorkspaceRegistry.load(_registry(tmp_path, repo_a, repo_b)),
        data_dir=tmp_path / "agent-app-server",
        client_factory=HangingJsonlRpcClient,
    )
    session = manager.open_session(workspace_key="repo-a", title="Chat")

    try:
        manager.run_turn(
            agent_session_id=session.agent_session_id,
            message="hello",
            timeout=5,
            should_cancel=lambda: True,
        )
    except RuntimeError as exc:
        assert "turn cancelled by server" in str(exc)
    else:
        raise AssertionError("expected cancelled turn to fail")

    assert manager.get_session(session.agent_session_id) is None
    assert FakeJsonlRpcClient.instances[0].closed is True


def test_session_manager_closes_session_when_turn_times_out(tmp_path: Path) -> None:
    FakeJsonlRpcClient.instances.clear()
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    manager = AgentAppSessionManager(
        workspace_registry=WorkspaceRegistry.load(_registry(tmp_path, repo_a, repo_b)),
        data_dir=tmp_path / "agent-app-server",
        client_factory=HangingJsonlRpcClient,
    )
    session = manager.open_session(workspace_key="repo-a", title="Chat")

    try:
        manager.run_turn(agent_session_id=session.agent_session_id, message="hello", timeout=0.1)
    except TimeoutError as exc:
        assert "timed out waiting for turn/completed" in str(exc)
    else:
        raise AssertionError("expected timed out turn to fail")

    assert manager.get_session(session.agent_session_id) is None
    assert FakeJsonlRpcClient.instances[0].closed is True


def test_turn_start_handler_returns_final_payload(tmp_path: Path) -> None:
    FakeJsonlRpcClient.instances.clear()
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    manager = AgentAppSessionManager(
        workspace_registry=WorkspaceRegistry.load(_registry(tmp_path, repo_a, repo_b)),
        data_dir=tmp_path / "agent-app-server",
        client_factory=FakeJsonlRpcClient,
    )
    session = manager.open_session(workspace_key="repo-a", title="Chat")
    uploader = FakeUploader()

    result = SessionOpenHandler(manager).handle(
        {
            "id": "cmd-open",
            "command_type": "SESSION_OPEN",
            "payload_json": json.dumps({"workspace_key": "repo-b"}),
        }
    )
    assert result.success is True

    from agent.session_handlers import TurnStartHandler

    turn_result = TurnStartHandler(manager, uploader).handle(
        {
            "id": "cmd-turn",
            "device_id": "device-a",
            "lease_token": "lease-a",
            "command_type": "TURN_START",
            "payload_json": json.dumps(
                {
                    "app_thread_id": 1,
                    "app_turn_id": 10,
                    "agent_session_id": session.agent_session_id,
                    "workspace_id": 1,
                    "workspace_key": "repo-a",
                    "message": "hello",
                }
            ),
        }
    )

    assert turn_result.success is True
    assert turn_result.result_payload is not None
    assert turn_result.result_payload["app_turn_id"] == 10
    assert turn_result.result_payload["agent_session_id"] == session.agent_session_id
    assert turn_result.result_payload["codex_turn_id"] == "codex-thread-1-turn-1"
    assert turn_result.result_payload["assistant_final"] == "hello-1"
    assert "cwd" not in json.dumps(turn_result.result_payload)


def test_turn_start_handler_rejects_wrong_workspace(tmp_path: Path) -> None:
    FakeJsonlRpcClient.instances.clear()
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    manager = AgentAppSessionManager(
        workspace_registry=WorkspaceRegistry.load(_registry(tmp_path, repo_a, repo_b)),
        data_dir=tmp_path / "agent-app-server",
        client_factory=FakeJsonlRpcClient,
    )
    session = manager.open_session(workspace_key="repo-a", title="Chat")

    from agent.session_handlers import TurnStartHandler

    result = TurnStartHandler(manager).handle(
        {
            "id": "cmd-turn",
            "device_id": "device-a",
            "lease_token": "lease-a",
            "command_type": "TURN_START",
            "payload_json": json.dumps(
                {
                    "app_turn_id": 10,
                    "agent_session_id": session.agent_session_id,
                    "workspace_key": "repo-b",
                    "message": "hello",
                }
            ),
        }
    )

    assert result.success is False
    assert result.message == "turn workspace does not match agent session"


def test_session_manager_reuses_same_codex_thread_for_five_turns(tmp_path: Path) -> None:
    FakeJsonlRpcClient.instances.clear()
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    manager = AgentAppSessionManager(
        workspace_registry=WorkspaceRegistry.load(_registry(tmp_path, repo_a, repo_b)),
        data_dir=tmp_path / "agent-app-server",
        client_factory=FakeJsonlRpcClient,
    )
    session = manager.open_session(workspace_key="repo-a", title="Chat")
    created_at = session.created_at

    results = [
        manager.run_turn(
            agent_session_id=session.agent_session_id,
            message=f"hello {index}",
        )
        for index in range(5)
    ]

    client = FakeJsonlRpcClient.instances[0]
    turn_requests = [request for request in client.requests if request["method"] == "turn/start"]
    thread_start_requests = [request for request in client.requests if request["method"] == "thread/start"]
    assert len(FakeJsonlRpcClient.instances) == 1
    assert len(thread_start_requests) == 1
    assert len(turn_requests) == 5
    assert session.turn_count == 5
    assert session.created_at == created_at
    assert session.last_activity_at >= created_at
    assert [result.turn_count for result in results] == [1, 2, 3, 4, 5]
    assert [result.codex_turn_id for result in results] == [
        "codex-thread-1-turn-1",
        "codex-thread-1-turn-2",
        "codex-thread-1-turn-3",
        "codex-thread-1-turn-4",
        "codex-thread-1-turn-5",
    ]
    assert all(request["params"]["threadId"] == session.codex_thread_id for request in turn_requests)
    assert all(request["params"]["cwd"] == str(repo_a.resolve()) for request in turn_requests)


def test_session_manager_keeps_sessions_isolated_when_switching(tmp_path: Path) -> None:
    FakeJsonlRpcClient.instances.clear()
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    manager = AgentAppSessionManager(
        workspace_registry=WorkspaceRegistry.load(_registry(tmp_path, repo_a, repo_b)),
        data_dir=tmp_path / "agent-app-server",
        client_factory=FakeJsonlRpcClient,
    )
    session_a = manager.open_session(workspace_key="repo-a", title="A")
    session_b = manager.open_session(workspace_key="repo-b", title="B")

    result_a1 = manager.run_turn(agent_session_id=session_a.agent_session_id, message="a1")
    result_b1 = manager.run_turn(agent_session_id=session_b.agent_session_id, message="b1")
    result_a2 = manager.run_turn(agent_session_id=session_a.agent_session_id, message="a2")

    client_a = FakeJsonlRpcClient.instances[0]
    client_b = FakeJsonlRpcClient.instances[1]
    a_turn_requests = [request for request in client_a.requests if request["method"] == "turn/start"]
    b_turn_requests = [request for request in client_b.requests if request["method"] == "turn/start"]
    assert result_a1.codex_turn_id == "codex-thread-1-turn-1"
    assert result_a2.codex_turn_id == "codex-thread-1-turn-2"
    assert result_b1.codex_turn_id == "codex-thread-2-turn-1"
    assert session_a.turn_count == 2
    assert session_b.turn_count == 1
    assert all(request["params"]["threadId"] == session_a.codex_thread_id for request in a_turn_requests)
    assert all(request["params"]["threadId"] == session_b.codex_thread_id for request in b_turn_requests)
    assert all(request["params"]["cwd"] == str(repo_a.resolve()) for request in a_turn_requests)
    assert all(request["params"]["cwd"] == str(repo_b.resolve()) for request in b_turn_requests)


def test_same_workspace_key_on_different_devices_does_not_share_sessions(tmp_path: Path) -> None:
    FakeJsonlRpcClient.instances.clear()
    device_a_root = tmp_path / "device-a"
    device_b_root = tmp_path / "device-b"
    repo_a = device_a_root / "repo"
    repo_b = device_b_root / "repo"
    repo_a.mkdir(parents=True)
    repo_b.mkdir(parents=True)
    manager_a = AgentAppSessionManager(
        workspace_registry=WorkspaceRegistry.load(_single_workspace_registry(tmp_path, "device-a", repo_a)),
        data_dir=tmp_path / "agent-a-app-server",
        client_factory=FakeJsonlRpcClient,
    )
    manager_b = AgentAppSessionManager(
        workspace_registry=WorkspaceRegistry.load(_single_workspace_registry(tmp_path, "device-b", repo_b)),
        data_dir=tmp_path / "agent-b-app-server",
        client_factory=FakeJsonlRpcClient,
    )

    session_a = manager_a.open_session(workspace_key="repo", title="A")
    session_b = manager_b.open_session(workspace_key="repo", title="B")
    result_a = manager_a.run_turn(agent_session_id=session_a.agent_session_id, message="a")
    result_b = manager_b.run_turn(agent_session_id=session_b.agent_session_id, message="b")

    client_a = FakeJsonlRpcClient.instances[0]
    client_b = FakeJsonlRpcClient.instances[1]
    a_turn_request = [request for request in client_a.requests if request["method"] == "turn/start"][0]
    b_turn_request = [request for request in client_b.requests if request["method"] == "turn/start"][0]
    assert session_a.workspace_key == session_b.workspace_key == "repo"
    assert session_a.agent_session_id != session_b.agent_session_id
    assert session_a.codex_thread_id != session_b.codex_thread_id
    assert result_a.codex_turn_id == "codex-thread-1-turn-1"
    assert result_b.codex_turn_id == "codex-thread-2-turn-1"
    assert a_turn_request["params"]["cwd"] == str(repo_a.resolve())
    assert b_turn_request["params"]["cwd"] == str(repo_b.resolve())
    assert a_turn_request["params"]["threadId"] == session_a.codex_thread_id
    assert b_turn_request["params"]["threadId"] == session_b.codex_thread_id


def _registry(tmp_path: Path, repo_a: Path, repo_b: Path) -> Path:
    path = tmp_path / "workspaces.json"
    path.write_text(
        json.dumps(
            {
                "allowed_roots": [str(tmp_path)],
                "workspaces": [
                    {"key": "repo-a", "name": "Repo A", "path": str(repo_a)},
                    {"key": "repo-b", "name": "Repo B", "path": str(repo_b)},
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _single_workspace_registry(tmp_path: Path, name: str, repo: Path) -> Path:
    path = tmp_path / f"{name}-workspaces.json"
    path.write_text(
        json.dumps(
            {
                "allowed_roots": [str(repo.parent)],
                "workspaces": [
                    {"key": "repo", "name": "Repo", "path": str(repo)},
                ],
            }
        ),
        encoding="utf-8",
    )
    return path
