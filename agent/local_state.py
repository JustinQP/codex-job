from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


class AgentLocalStateError(RuntimeError):
    pass


@dataclass(frozen=True)
class CurrentCommandState:
    command_id: str
    claim_request_id: str
    lease_token: str


class AgentLocalState:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load_current_command(self) -> CurrentCommandState | None:
        if not self.path.exists():
            return None
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AgentLocalStateError(f"agent state is not valid JSON: {self.path}") from exc
        except OSError as exc:
            raise AgentLocalStateError(f"agent state cannot be read: {self.path}") from exc
        current = raw.get("current_command") if isinstance(raw, dict) else None
        if current is None:
            return None
        if not isinstance(current, dict):
            raise AgentLocalStateError(f"current_command must be an object: {self.path}")
        return CurrentCommandState(
            command_id=_required_string(current, "command_id", self.path),
            claim_request_id=_required_string(current, "claim_request_id", self.path),
            lease_token=_required_string(current, "lease_token", self.path),
        )

    def save_current_command(self, state: CurrentCommandState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "current_command": {
                        "command_id": state.command_id,
                        "claim_request_id": state.claim_request_id,
                        "lease_token": state.lease_token,
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def clear_current_command(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"current_command": None}, indent=2) + "\n", encoding="utf-8")


def _required_string(raw: dict, key: str, path: Path) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AgentLocalStateError(f"current_command.{key} is missing or invalid: {path}")
    return value
