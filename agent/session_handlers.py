from __future__ import annotations

import json
from typing import Any

from agent.app_server.session_manager import AgentAppSessionManager
from agent.command_handlers import CommandResult


class SessionOpenHandler:
    def __init__(self, session_manager: AgentAppSessionManager) -> None:
        self.session_manager = session_manager

    def handle(self, command: dict[str, Any]) -> CommandResult:
        try:
            payload = json.loads(command.get("payload_json") or "{}")
            workspace_key = str(payload["workspace_key"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return CommandResult(False, f"invalid session open payload: {exc}")

        if payload.get("cwd") or payload.get("project_path"):
            return CommandResult(False, "session open payload must not specify cwd")

        try:
            session = self.session_manager.open_session(
                workspace_key=workspace_key,
                title=_string_or_none(payload.get("title")),
                sandbox=str(payload.get("sandbox") or "read-only"),
                approval_policy=str(payload.get("approval_policy") or "never"),
                network_access=bool(payload.get("network_access")),
            )
        except Exception as exc:  # noqa: BLE001
            return CommandResult(False, f"failed to open app session: {exc}")
        return CommandResult(
            True,
            f"session opened in {session.cwd}",
            result_payload={
                "agent_session_id": session.agent_session_id,
                "codex_thread_id": session.codex_thread_id,
                "workspace_key": session.workspace_key,
            },
        )


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
