from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Protocol


@dataclass(frozen=True)
class CommandResult:
    success: bool
    message: str | None = None


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
    def __init__(self) -> None:
        self._handlers: dict[str, CommandHandler] = {
            "fake.echo": FakeCommandHandler(),
        }
        self._fallback = UnsupportedCommandHandler()

    def handle(self, command: dict[str, Any]) -> CommandResult:
        handler = self._handlers.get(str(command.get("command_type")), self._fallback)
        return handler.handle(command)
