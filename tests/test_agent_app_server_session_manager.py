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
        self.instances.append(self)

    def request(self, request_id: str, method: str, params: dict[str, Any] | None = None) -> None:
        self.requests.append({"id": request_id, "method": method, "params": params or {}})

    def wait_for_response(self, request_id: str, timeout: float) -> dict[str, Any]:
        del timeout
        if request_id.endswith("-initialize"):
            return {"id": request_id, "result": {"ok": True}}
        if request_id.endswith("-thread-start"):
            return {"id": request_id, "result": {"thread": {"id": self.thread_id}}}
        raise AssertionError(f"unexpected request id: {request_id}")

    def close(self) -> None:
        self.closed = True


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
