from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Protocol

from agent.api_client import AgentApiClient
from agent.process_registry import ProcessRegistry
from agent.workspace_lock import LocalWorkspaceLock
from agent.workspace_registry import WorkspaceRegistry


@dataclass(frozen=True)
class CommandResult:
    success: bool
    message: str | None = None
    result_payload: dict[str, Any] | None = None


class CommandHandler(Protocol):
    def handle(self, command: dict[str, Any]) -> CommandResult:
        ...


class FakeCommandHandler:
    def handle(self, command: dict[str, Any]) -> CommandResult:
        payload_json = command.get("payload_json") or "{}"
        payload = json.loads(payload_json)
        return CommandResult(
            success=True,
            message=f"fake command handled: {payload.get('message', command.get('id'))}",
        )


class UnsupportedCommandHandler:
    def handle(self, command: dict[str, Any]) -> CommandResult:
        return CommandResult(
            success=False,
            message=f"unsupported command type: {command.get('command_type')}",
        )


class CommandHandlerRegistry:
    def __init__(
        self,
        workspace_registry: WorkspaceRegistry | None = None,
        *,
        client: AgentApiClient | None = None,
        device_id: str | None = None,
        process_registry: ProcessRegistry | None = None,
        app_session_manager: Any | None = None,
        event_uploader: Any | None = None,
        workspace_lock: LocalWorkspaceLock | None = None,
    ) -> None:
        local_workspace_lock = workspace_lock or LocalWorkspaceLock()
        self._handlers: dict[str, CommandHandler] = {
            "fake.echo": FakeCommandHandler(),
        }
        if workspace_registry is not None:
            from agent.run_executor import RunExecutor

            self._handlers["RUN_EXECUTE"] = RunExecutor(
                workspace_registry,
                client=client,
                device_id=device_id,
                process_registry=process_registry,
                workspace_lock=local_workspace_lock,
            )
        if app_session_manager is not None:
            from agent.session_handlers import SessionOpenHandler, TurnStartHandler

            self._handlers["SESSION_OPEN"] = SessionOpenHandler(app_session_manager, local_workspace_lock)
            self._handlers["TURN_START"] = TurnStartHandler(app_session_manager, event_uploader, client)
        self._fallback = UnsupportedCommandHandler()

    def handle(self, command: dict[str, Any]) -> CommandResult:
        handler = self._handlers.get(str(command.get("command_type")), self._fallback)
        return handler.handle(command)
