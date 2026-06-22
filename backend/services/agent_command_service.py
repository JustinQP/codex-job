from __future__ import annotations

from datetime import datetime
import json
import re
from typing import Any, Final, Mapping

from sqlmodel import Session, select

from backend.models import AgentCommand, AgentCommandStatus, Device, DeviceStatus, Workspace, utc_now


TERMINAL_STATUSES: Final[set[AgentCommandStatus]] = {
    AgentCommandStatus.SUCCESS,
    AgentCommandStatus.FAILED,
    AgentCommandStatus.CANCELLED,
    AgentCommandStatus.EXPIRED,
}

ALLOWED_TRANSITIONS: Final[dict[AgentCommandStatus, set[AgentCommandStatus]]] = {
    AgentCommandStatus.PENDING: {
        AgentCommandStatus.CLAIMED,
        AgentCommandStatus.CANCELLED,
        AgentCommandStatus.EXPIRED,
    },
    AgentCommandStatus.CLAIMED: {
        AgentCommandStatus.RUNNING,
        AgentCommandStatus.SUCCESS,
        AgentCommandStatus.FAILED,
        AgentCommandStatus.CANCELLED,
        AgentCommandStatus.EXPIRED,
    },
    AgentCommandStatus.RUNNING: {
        AgentCommandStatus.SUCCESS,
        AgentCommandStatus.FAILED,
        AgentCommandStatus.CANCELLED,
        AgentCommandStatus.EXPIRED,
    },
    AgentCommandStatus.SUCCESS: set(),
    AgentCommandStatus.FAILED: set(),
    AgentCommandStatus.CANCELLED: set(),
    AgentCommandStatus.EXPIRED: set(),
}


class AgentCommandStateError(ValueError):
    """Raised when an AgentCommand state transition is not allowed."""


class AgentCommandServiceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


ABSOLUTE_PATH_PATTERN = re.compile(r"^([A-Za-z]:[\\/]|/|\\\\)")


def _contains_absolute_path(value: Any) -> bool:
    if isinstance(value, str):
        return bool(ABSOLUTE_PATH_PATTERN.match(value))
    if isinstance(value, Mapping):
        return any(_contains_absolute_path(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_absolute_path(item) for item in value)
    return False


def _canonical_payload(payload: Mapping[str, Any]) -> str:
    if _contains_absolute_path(payload):
        raise AgentCommandServiceError(
            "invalid_command_payload",
            "command payload must not contain absolute paths",
        )
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def create_command(
    session: Session,
    *,
    device_id: str,
    command_type: str,
    idempotency_key: str,
    payload: Mapping[str, Any],
    aggregate_type: str | None = None,
    aggregate_id: str | None = None,
    workspace_id: int | None = None,
    max_attempts: int = 3,
) -> AgentCommand:
    if not idempotency_key:
        raise AgentCommandServiceError(
            "missing_idempotency_key",
            "idempotency_key is required",
        )
    payload_json = _canonical_payload(payload)
    device = session.get(Device, device_id)
    if device is None:
        raise AgentCommandServiceError("device_not_found", "device not found")
    if device.status == DeviceStatus.DISABLED:
        raise AgentCommandServiceError("device_disabled", "device is disabled")
    if workspace_id is not None:
        workspace = session.get(Workspace, workspace_id)
        if workspace is None or not workspace.enabled or workspace.device_id != device_id:
            raise AgentCommandServiceError(
                "workspace_unavailable",
                "workspace is unavailable for this device",
            )

    existing = session.exec(
        select(AgentCommand).where(AgentCommand.idempotency_key == idempotency_key)
    ).first()
    if existing is not None:
        if (
            existing.device_id == device_id
            and existing.command_type == command_type
            and existing.aggregate_type == aggregate_type
            and existing.aggregate_id == aggregate_id
            and existing.payload_json == payload_json
            and existing.max_attempts == max_attempts
        ):
            return existing
        raise AgentCommandServiceError(
            "agent_command_idempotency_conflict",
            "idempotency_key already exists with a different command payload",
        )

    command = AgentCommand(
        device_id=device_id,
        command_type=command_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        idempotency_key=idempotency_key,
        payload_json=payload_json,
        max_attempts=max_attempts,
    )
    session.add(command)
    session.commit()
    session.refresh(command)
    return command


def is_transition_allowed(
    current: AgentCommandStatus,
    target: AgentCommandStatus,
) -> bool:
    return target in ALLOWED_TRANSITIONS[current]


def transition_command(
    session: Session,
    command: AgentCommand,
    target_status: AgentCommandStatus,
    *,
    lease_token: str | None = None,
    lease_expires_at: datetime | None = None,
    last_error: str | None = None,
) -> AgentCommand:
    if command.status in TERMINAL_STATUSES and command.status == target_status:
        return command

    if not is_transition_allowed(command.status, target_status):
        raise AgentCommandStateError(
            f"invalid AgentCommand transition: {command.status} -> {target_status}"
        )

    now = utc_now()
    command.status = target_status
    if target_status == AgentCommandStatus.CLAIMED:
        command.claimed_at = now
        command.attempt_count += 1
        command.lease_token = lease_token
        command.lease_expires_at = lease_expires_at
    elif target_status == AgentCommandStatus.RUNNING:
        if lease_token is not None:
            command.lease_token = lease_token
        if lease_expires_at is not None:
            command.lease_expires_at = lease_expires_at

    if target_status in TERMINAL_STATUSES:
        command.completed_at = now
        command.lease_token = None
        command.lease_expires_at = None
    if last_error is not None:
        command.last_error = last_error

    session.add(command)
    session.commit()
    session.refresh(command)
    return command


def list_commands_for_device(
    session: Session,
    device_id: str,
    *,
    status: AgentCommandStatus | None = None,
) -> list[AgentCommand]:
    statement = select(AgentCommand).where(AgentCommand.device_id == device_id)
    if status is not None:
        statement = statement.where(AgentCommand.status == status)
    statement = statement.order_by(AgentCommand.created_at)
    return list(session.exec(statement).all())
