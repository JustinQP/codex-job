from __future__ import annotations

from datetime import datetime
from typing import Final

from sqlmodel import Session, select

from backend.models import AgentCommand, AgentCommandStatus, utc_now


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
