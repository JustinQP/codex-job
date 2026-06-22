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


class TurnStartHandler:
    def __init__(self, session_manager: AgentAppSessionManager, event_uploader=None) -> None:
        self.session_manager = session_manager
        self.event_uploader = event_uploader

    def handle(self, command: dict[str, Any]) -> CommandResult:
        try:
            payload = json.loads(command.get("payload_json") or "{}")
            agent_session_id = str(payload["agent_session_id"])
            app_turn_id = int(payload["app_turn_id"])
            message = str(payload["message"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return CommandResult(False, f"invalid turn start payload: {exc}")

        if payload.get("cwd") or payload.get("project_path"):
            return CommandResult(False, "turn start payload must not specify cwd")

        session = self.session_manager.get_session(agent_session_id)
        if session is None:
            return CommandResult(False, f"agent session not found: {agent_session_id}")
        workspace_key = payload.get("workspace_key")
        if isinstance(workspace_key, str) and workspace_key and workspace_key != session.workspace_key:
            return CommandResult(False, "turn workspace does not match agent session")

        command_id = _string_or_none(command.get("id"))
        device_id = _string_or_none(command.get("device_id"))
        lease_token = _string_or_none(command.get("lease_token"))
        try:
            result = self.session_manager.run_turn(
                agent_session_id=agent_session_id,
                message=message,
                command_id=command_id,
                uploader=self.event_uploader,
                device_id=device_id,
                lease_token=lease_token,
            )
        except Exception as exc:  # noqa: BLE001
            return CommandResult(False, f"failed to run app turn: {exc}")

        return CommandResult(
            True,
            f"turn completed for app turn {app_turn_id}",
            result_payload={
                "app_turn_id": app_turn_id,
                "agent_session_id": agent_session_id,
                "codex_turn_id": result.codex_turn_id,
                "assistant_final": result.assistant_final,
                "event_summary": result.event_summary,
                "turn_count": result.turn_count,
            },
        )


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
