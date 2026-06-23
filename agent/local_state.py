from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path


class AgentLocalStateError(RuntimeError):
    pass


@dataclass(frozen=True)
class CurrentCommandState:
    command_id: str
    claim_request_id: str
    lease_token: str
    phase: str = "CLAIMED"
    status: str | None = None
    error_message: str | None = None
    result_payload: dict | None = None


@dataclass(frozen=True)
class PendingCommandEvent:
    command_id: str
    sequence: int
    kind: str
    payload: dict
    created_at: str


class AgentLocalState:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load_current_command(self) -> CurrentCommandState | None:
        raw = self._load_raw()
        current = raw.get("current_command") if isinstance(raw, dict) else None
        if current is None:
            return None
        if not isinstance(current, dict):
            raise AgentLocalStateError(f"current_command must be an object: {self.path}")
        return CurrentCommandState(
            command_id=_required_string(current, "command_id", self.path),
            claim_request_id=_required_string(current, "claim_request_id", self.path),
            lease_token=_required_string(current, "lease_token", self.path),
            phase=str(current.get("phase") or "CLAIMED"),
            status=current.get("status") if isinstance(current.get("status"), str) else None,
            error_message=current.get("error_message") if isinstance(current.get("error_message"), str) else None,
            result_payload=current.get("result_payload") if isinstance(current.get("result_payload"), dict) else None,
        )

    def save_current_command(self, state: CurrentCommandState) -> None:
        raw = self._load_raw()
        raw["current_command"] = {
            "command_id": state.command_id,
            "claim_request_id": state.claim_request_id,
            "lease_token": state.lease_token,
            "phase": state.phase,
            "status": state.status,
            "error_message": state.error_message,
            "result_payload": state.result_payload,
        }
        self._write_raw(raw)

    def clear_current_command(self) -> None:
        raw = self._load_raw()
        raw["current_command"] = None
        self._write_raw(raw)

    def load_pending_events(self, command_id: str) -> list[PendingCommandEvent]:
        raw = self._load_raw()
        events = raw.get("pending_events", [])
        if not isinstance(events, list):
            raise AgentLocalStateError(f"pending_events must be a list: {self.path}")
        result = []
        for event in events:
            if not isinstance(event, dict) or event.get("command_id") != command_id:
                continue
            result.append(
                PendingCommandEvent(
                    command_id=_required_string(event, "command_id", self.path),
                    sequence=int(event["sequence"]),
                    kind=_required_string(event, "kind", self.path),
                    payload=event.get("payload") if isinstance(event.get("payload"), dict) else {},
                    created_at=_required_string(event, "created_at", self.path),
                )
            )
        return sorted(result, key=lambda item: item.sequence)

    def append_pending_event(self, event: PendingCommandEvent) -> None:
        raw = self._load_raw()
        events = raw.setdefault("pending_events", [])
        if not isinstance(events, list):
            raise AgentLocalStateError(f"pending_events must be a list: {self.path}")
        events.append(
            {
                "command_id": event.command_id,
                "sequence": event.sequence,
                "kind": event.kind,
                "payload": event.payload,
                "created_at": event.created_at,
            }
        )
        self._write_raw(raw)

    def clear_pending_events(self, command_id: str, through_sequence: int) -> None:
        raw = self._load_raw()
        events = raw.get("pending_events", [])
        if not isinstance(events, list):
            raise AgentLocalStateError(f"pending_events must be a list: {self.path}")
        raw["pending_events"] = [
            event for event in events
            if not (
                isinstance(event, dict)
                and event.get("command_id") == command_id
                and int(event.get("sequence", 0)) <= through_sequence
            )
        ]
        self._write_raw(raw)

    def _load_raw(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AgentLocalStateError(f"agent state is not valid JSON: {self.path}") from exc
        except OSError as exc:
            raise AgentLocalStateError(f"agent state cannot be read: {self.path}") from exc
        if not isinstance(raw, dict):
            raise AgentLocalStateError(f"agent state must contain a JSON object: {self.path}")
        return raw

    def _write_raw(self, raw: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp_path, self.path)


def _required_string(raw: dict, key: str, path: Path) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AgentLocalStateError(f"current_command.{key} is missing or invalid: {path}")
    return value
