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
        self.backup_path = path.with_suffix(path.suffix + ".bak")

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

    def latest_pending_event_sequence(self, command_id: str) -> int | None:
        pending = self.load_pending_events(command_id)
        if not pending:
            return None
        return max(event.sequence for event in pending)

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

    def clear_pending_events_range(
        self,
        command_id: str,
        *,
        from_sequence: int,
        through_sequence: int,
    ) -> None:
        raw = self._load_raw()
        events = raw.get("pending_events", [])
        if not isinstance(events, list):
            raise AgentLocalStateError(f"pending_events must be a list: {self.path}")
        raw["pending_events"] = [
            event for event in events
            if not (
                isinstance(event, dict)
                and event.get("command_id") == command_id
                and from_sequence <= int(event.get("sequence", 0)) <= through_sequence
            )
        ]
        self._write_raw(raw)

    def _load_raw(self) -> dict:
        if not self.path.exists():
            if self.backup_path.exists():
                return self._load_backup_raw()
            return {}
        try:
            raw = self._read_json_object(self.path)
        except json.JSONDecodeError as exc:
            if self.backup_path.exists():
                return self._load_backup_raw()
            raise AgentLocalStateError(f"agent state is not valid JSON: {self.path}") from exc
        except OSError as exc:
            if self.backup_path.exists():
                return self._load_backup_raw()
            raise AgentLocalStateError(f"agent state cannot be read: {self.path}") from exc
        return raw

    def _write_raw(self, raw: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        _write_json_atomic_source(tmp_path, raw)
        if self.path.exists():
            backup_tmp_path = self.backup_path.with_suffix(self.backup_path.suffix + ".tmp")
            _copy_file_with_fsync(self.path, backup_tmp_path)
            os.replace(backup_tmp_path, self.backup_path)
        os.replace(tmp_path, self.path)
        _fsync_directory(self.path.parent)

    def _load_backup_raw(self) -> dict:
        try:
            raw = self._read_json_object(self.backup_path)
        except json.JSONDecodeError as exc:
            raise AgentLocalStateError(
                f"agent state and backup are not valid JSON: {self.path}"
            ) from exc
        except OSError as exc:
            raise AgentLocalStateError(f"agent state backup cannot be read: {self.backup_path}") from exc
        self._write_raw(raw)
        return raw

    def _read_json_object(self, path: Path) -> dict:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise AgentLocalStateError(f"agent state must contain a JSON object: {path}")
        return raw


def _write_json_atomic_source(path: Path, raw: dict) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(raw, file, indent=2)
        file.write("\n")
        file.flush()
        os.fsync(file.fileno())


def _copy_file_with_fsync(source_path: Path, target_path: Path) -> None:
    with source_path.open("rb") as source, target_path.open("wb") as target:
        target.write(source.read())
        target.flush()
        os.fsync(target.fileno())


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        directory_fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _required_string(raw: dict, key: str, path: Path) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AgentLocalStateError(f"current_command.{key} is missing or invalid: {path}")
    return value
