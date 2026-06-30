from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import RLock
import time
from typing import Callable
from uuid import uuid4

from agent.codex_executor import find_codex_bin
from agent.app_server.client import JsonlRpcClient, extract_thread_id, response_result
from agent.app_server.event_parser import extract_assistant_text, summarize_events
from agent.workspace_registry import WorkspaceRegistry


DEFAULT_DEVELOPER_INSTRUCTIONS = "Do not modify files unless the controlling command allows it."


@dataclass
class AgentAppSession:
    agent_session_id: str
    workspace_key: str
    cwd: Path
    codex_thread_id: str
    sandbox: str
    approval_policy: str
    network_access: bool
    client: JsonlRpcClient
    run_dir: Path
    raw_events_path: Path
    stderr_path: Path
    created_at: str
    last_activity_at: str
    turn_count: int = 0
    active_turn_id: str | None = None
    last_turn_id: str | None = None
    workspace_lock_owner: str | None = None
    workspace_lock_release: Callable[[Path, str], None] | None = None


@dataclass(frozen=True)
class AgentAppTurnResult:
    codex_turn_id: str
    assistant_final: str
    event_summary: dict
    events: list[dict]
    turn_count: int


class AgentAppSessionManager:
    def __init__(
        self,
        *,
        workspace_registry: WorkspaceRegistry,
        codex_command: str | None = None,
        data_dir: Path = Path("data") / "agent-app-server",
        client_factory: Callable[[list[str], Path, Path, Path], JsonlRpcClient] = JsonlRpcClient,
        max_client_messages: int = 200,
    ) -> None:
        self.workspace_registry = workspace_registry
        self.codex_command = codex_command or find_codex_bin()
        self.data_dir = data_dir
        self.client_factory = client_factory
        self.max_client_messages = max_client_messages
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
        workspace_lock_owner: str | None = None,
        workspace_lock_release: Callable[[Path, str], None] | None = None,
    ) -> AgentAppSession:
        cwd = self.workspace_registry.resolve(workspace_key)
        now = _utc_iso()
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
            sandbox=sandbox,
            approval_policy=approval_policy,
            network_access=network_access,
            client=client,
            run_dir=run_dir,
            raw_events_path=raw_events_path,
            stderr_path=stderr_path,
            created_at=now,
            last_activity_at=now,
            workspace_lock_owner=workspace_lock_owner,
            workspace_lock_release=workspace_lock_release,
        )
        with self._lock:
            self._sessions[agent_session_id] = session
        return session

    def get_session(self, agent_session_id: str) -> AgentAppSession | None:
        with self._lock:
            return self._sessions.get(agent_session_id)

    def run_turn(
        self,
        *,
        agent_session_id: str,
        message: str,
        timeout: float = 180.0,
        command_id: str | None = None,
        uploader=None,
        device_id: str | None = None,
        lease_token: str | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> AgentAppTurnResult:
        session = self.get_session(agent_session_id)
        if session is None:
            raise KeyError(f"agent session not found: {agent_session_id}")
        clean_message = message.strip()
        if not clean_message:
            raise ValueError("message cannot be empty")

        turn_number = session.turn_count + 1
        request_id = f"{agent_session_id}-turn-{turn_number}-start"
        start_index = session.client.message_count
        session.last_activity_at = _utc_iso()
        sequence = 1
        if uploader is not None and command_id and device_id and lease_token:
            uploader.cache_event(
                command_id=command_id,
                sequence=sequence,
                kind="status",
                payload={"status": "RUNNING", "agent_session_id": agent_session_id},
            )
            _flush_events_safely(uploader, command_id=command_id, device_id=device_id, lease_token=lease_token)
            sequence += 1

        session.client.request(
            request_id,
            "turn/start",
            {
                "threadId": session.codex_thread_id,
                "cwd": str(session.cwd),
                "approvalPolicy": session.approval_policy,
                "sandboxPolicy": _sandbox_policy(session.sandbox, session.network_access),
                "clientUserMessageId": f"{request_id}-user-message-{int(time.time())}",
                "input": [
                    {
                        "type": "text",
                        "text": clean_message,
                    }
                ],
            },
        )
        turn_start_result = response_result(
            session.client.wait_for_response(request_id, timeout=60),
            "turn/start",
        )
        codex_turn_id = _extract_turn_id(turn_start_result)
        session.active_turn_id = codex_turn_id
        session.last_turn_id = codex_turn_id

        try:
            end_index, sequence = self._wait_for_turn_completed(
                session=session,
                codex_turn_id=codex_turn_id,
                request_id=request_id,
                start_index=start_index,
                timeout=timeout,
                command_id=command_id,
                uploader=uploader,
                device_id=device_id,
                lease_token=lease_token,
                first_sequence=sequence,
                should_cancel=should_cancel,
            )
        except Exception:
            session.active_turn_id = None
            raise

        all_events = _client_messages(session.client)
        if end_index is not None and start_index < end_index:
            turn_events = all_events[start_index:end_index]
        else:
            turn_events = _events_for_turn(all_events, codex_turn_id, request_id)
        turn_dir = session.run_dir / f"turn-{turn_number}"
        turn_dir.mkdir(parents=True, exist_ok=True)
        _write_events_jsonl(turn_dir / "events.jsonl", turn_events)
        event_summary = summarize_events(turn_events)
        assistant_final = extract_assistant_text(turn_events)

        session.turn_count = turn_number
        session.active_turn_id = None
        session.last_turn_id = codex_turn_id
        session.last_activity_at = _utc_iso()
        if uploader is not None and command_id and device_id and lease_token:
            uploader.cache_event(
                command_id=command_id,
                sequence=sequence,
                kind="final",
                payload={
                    "agent_session_id": agent_session_id,
                    "codex_turn_id": codex_turn_id,
                    "assistant_final_preview": assistant_final[:500],
                    "event_summary": event_summary,
                },
            )
            _flush_events_safely(uploader, command_id=command_id, device_id=device_id, lease_token=lease_token)
        _trim_client_messages(session.client, self.max_client_messages)
        return AgentAppTurnResult(
            codex_turn_id=codex_turn_id,
            assistant_final=assistant_final,
            event_summary=event_summary,
            events=turn_events,
            turn_count=turn_number,
        )

    def _wait_for_turn_completed(
        self,
        *,
        session: AgentAppSession,
        codex_turn_id: str,
        request_id: str,
        start_index: int,
        timeout: float,
        command_id: str | None,
        uploader,
        device_id: str | None,
        lease_token: str | None,
        first_sequence: int,
        should_cancel: Callable[[], bool] | None,
    ) -> tuple[int, int]:
        deadline = time.monotonic() + timeout
        next_index = start_index
        sequence = first_sequence
        while time.monotonic() < deadline:
            if should_cancel is not None and should_cancel():
                self.close_session(session.agent_session_id)
                raise RuntimeError("turn cancelled by server; app session closed")
            try:
                message_index, event = session.client.wait_for_match(
                    lambda item: _event_turn_id(item) == codex_turn_id or item.get("id") == request_id,
                    timeout=min(1.0, max(0.1, deadline - time.monotonic())),
                    start_index=next_index,
                )
            except TimeoutError as exc:
                if time.monotonic() >= deadline:
                    self.close_session(session.agent_session_id)
                    raise TimeoutError(f"timed out waiting for turn/completed: {codex_turn_id}") from exc
                continue
            next_index = message_index + 1
            if _event_turn_id(event) != codex_turn_id and event.get("id") != request_id:
                continue
            if uploader is not None and command_id and device_id and lease_token:
                uploader.cache_event(
                    command_id=command_id,
                    sequence=sequence,
                    kind=_event_name(event),
                    payload={
                        "agent_session_id": session.agent_session_id,
                        "codex_turn_id": codex_turn_id,
                        "event": event,
                    },
                )
                _flush_events_safely(uploader, command_id=command_id, device_id=device_id, lease_token=lease_token)
                sequence += 1
            if _is_turn_completed(event, codex_turn_id):
                return message_index + 1, sequence
        self.close_session(session.agent_session_id)
        raise TimeoutError(f"timed out waiting for turn/completed: {codex_turn_id}")

    def close_session(self, agent_session_id: str) -> bool:
        with self._lock:
            session = self._sessions.pop(agent_session_id, None)
        if session is None:
            return False
        session.client.close()
        if session.workspace_lock_owner and session.workspace_lock_release:
            session.workspace_lock_release(session.cwd, session.workspace_lock_owner)
        return True

    def close_all(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.client.close()
            if session.workspace_lock_owner and session.workspace_lock_release:
                session.workspace_lock_release(session.cwd, session.workspace_lock_owner)


def _extract_turn_id(turn_start_result) -> str:
    if not isinstance(turn_start_result, dict):
        raise RuntimeError("turn/start result is not an object")
    turn = turn_start_result.get("turn")
    if not isinstance(turn, dict):
        raise RuntimeError("turn/start result.turn is not an object")
    turn_id = turn.get("id")
    if not isinstance(turn_id, str) or not turn_id:
        raise RuntimeError("turn/start result.turn.id is missing")
    return turn_id


def _flush_events_safely(uploader, *, command_id: str, device_id: str, lease_token: str) -> None:
    try:
        uploader.flush(command_id=command_id, device_id=device_id, lease_token=lease_token)
    except Exception:
        return


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sandbox_policy(sandbox: str, network_access: bool) -> dict:
    normalized = sandbox.replace("_", "-").lower()
    if normalized == "workspace-write":
        sandbox_type = "workspaceWrite"
    else:
        sandbox_type = "readOnly"
    return {
        "type": sandbox_type,
        "networkAccess": network_access,
    }


def _client_messages(client: JsonlRpcClient) -> list[dict]:
    with client._condition:
        return list(client._messages)


def _trim_client_messages(client: JsonlRpcClient, max_messages: int) -> None:
    if max_messages < 1:
        return
    trim = getattr(client, "trim_messages", None)
    if callable(trim):
        trim(max_messages)
        return
    with client._condition:
        excess = len(client._messages) - max_messages
        if excess > 0:
            del client._messages[:excess]


def _events_for_turn(events: list[dict], turn_id: str, request_id: str) -> list[dict]:
    return [
        event
        for event in events
        if event.get("id") == request_id or _event_turn_id(event) == turn_id
    ]


def _is_turn_completed(event: dict, turn_id: str) -> bool:
    return _event_name(event) == "turn/completed" and _event_turn_id(event) == turn_id


def _event_name(event: dict) -> str:
    for key in ("method", "type", "event"):
        value = event.get(key)
        if isinstance(value, str):
            return value
    if "id" in event and ("result" in event or "error" in event):
        return "response"
    return "unknown"


def _event_turn_id(event: dict) -> str | None:
    result = event.get("result")
    if isinstance(result, dict):
        turn = result.get("turn")
        if isinstance(turn, dict) and isinstance(turn.get("id"), str):
            return turn["id"]
        if isinstance(result.get("turnId"), str):
            return result["turnId"]

    params = event.get("params")
    if isinstance(params, dict):
        if isinstance(params.get("turnId"), str):
            return params["turnId"]
        turn = params.get("turn")
        if isinstance(turn, dict) and isinstance(turn.get("id"), str):
            return turn["id"]
    return None


def _write_events_jsonl(path: Path, events: list[dict]) -> None:
    with path.open("w", encoding="utf-8", errors="replace") as file:
        for event in events:
            file.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
