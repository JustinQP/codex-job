from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Callable
from uuid import uuid4

from agent.app_server.client import JsonlRpcClient, extract_thread_id, response_result
from agent.workspace_registry import WorkspaceRegistry


DEFAULT_DEVELOPER_INSTRUCTIONS = "Do not modify files unless the controlling command allows it."


@dataclass
class AgentAppSession:
    agent_session_id: str
    workspace_key: str
    cwd: Path
    codex_thread_id: str
    client: JsonlRpcClient
    run_dir: Path
    raw_events_path: Path
    stderr_path: Path
    turn_count: int = 0


class AgentAppSessionManager:
    def __init__(
        self,
        *,
        workspace_registry: WorkspaceRegistry,
        codex_command: str = "codex.cmd",
        data_dir: Path = Path("data") / "agent-app-server",
        client_factory: Callable[[list[str], Path, Path, Path], JsonlRpcClient] = JsonlRpcClient,
    ) -> None:
        self.workspace_registry = workspace_registry
        self.codex_command = codex_command
        self.data_dir = data_dir
        self.client_factory = client_factory
        self._sessions: dict[str, AgentAppSession] = {}
        self._lock = RLock()

    def open_session(
        self,
        *,
        workspace_key: str,
        title: str | None = None,
        sandbox: str = "read-only",
        approval_policy: str = "never",
        network_access: bool = False,
        developer_instructions: str = DEFAULT_DEVELOPER_INSTRUCTIONS,
    ) -> AgentAppSession:
        cwd = self.workspace_registry.resolve(workspace_key)
        agent_session_id = str(uuid4())
        run_dir = self.data_dir / agent_session_id
        run_dir.mkdir(parents=True, exist_ok=False)
        raw_events_path = run_dir / "_all-events.jsonl"
        stderr_path = run_dir / "stderr.log"
        client = self.client_factory(
            [self.codex_command, "app-server", "--listen", "stdio://"],
            cwd,
            raw_events_path,
            stderr_path,
        )
        try:
            client.request(
                f"{agent_session_id}-initialize",
                "initialize",
                {
                    "clientInfo": {
                        "name": "codex-job-device-agent",
                        "title": "Codex Job Device Agent",
                        "version": "0.1.0",
                    },
                    "capabilities": {"experimentalApi": True},
                },
            )
            response_result(
                client.wait_for_response(f"{agent_session_id}-initialize", timeout=30),
                "initialize",
            )
            client.request(
                f"{agent_session_id}-thread-start",
                "thread/start",
                {
                    "cwd": str(cwd),
                    "approvalPolicy": approval_policy,
                    "sandbox": sandbox,
                    "sessionStartSource": "agent",
                    "threadSource": "codex-job-device-agent",
                    "ephemeral": False,
                    "networkAccess": network_access,
                    "title": title,
                    "developerInstructions": developer_instructions,
                },
            )
            thread_start_result = response_result(
                client.wait_for_response(f"{agent_session_id}-thread-start", timeout=60),
                "thread/start",
            )
            codex_thread_id = extract_thread_id(thread_start_result)
        except Exception:
            client.close()
            raise

        session = AgentAppSession(
            agent_session_id=agent_session_id,
            workspace_key=workspace_key,
            cwd=cwd,
            codex_thread_id=codex_thread_id,
            client=client,
            run_dir=run_dir,
            raw_events_path=raw_events_path,
            stderr_path=stderr_path,
        )
        with self._lock:
            self._sessions[agent_session_id] = session
        return session

    def get_session(self, agent_session_id: str) -> AgentAppSession | None:
        with self._lock:
            return self._sessions.get(agent_session_id)

    def close_session(self, agent_session_id: str) -> bool:
        with self._lock:
            session = self._sessions.pop(agent_session_id, None)
        if session is None:
            return False
        session.client.close()
        return True

    def close_all(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.client.close()
