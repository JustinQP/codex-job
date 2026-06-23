from __future__ import annotations

from sqlmodel import Session

from backend.models import AgentCommand
from backend.services import agent_command_service, app_thread_service, run_service, workspace_lock_service


def expire_stale_agent_commands(
    session: Session,
    *,
    device_id: str | None = None,
) -> list[AgentCommand]:
    expired_commands = agent_command_service.expire_stale_active_commands(
        session,
        device_id=device_id,
    )
    for command in expired_commands:
        apply_terminal_command_effects(session, command)
    return expired_commands


def apply_terminal_command_effects(
    session: Session,
    command: AgentCommand,
    *,
    result_payload: dict | None = None,
) -> None:
    if command.command_type == "RUN_EXECUTE":
        run_service.complete_run_command(session, command_id=command.id)
        if command.aggregate_id:
            workspace_lock_service.release_workspace_lock(
                session,
                owner_type="run",
                owner_id=str(command.aggregate_id),
            )
    elif command.command_type == "SESSION_OPEN":
        app_thread_service.complete_agent_session_open(
            session,
            command_id=command.id,
            result_payload=result_payload,
        )
    elif command.command_type == "SESSION_CLOSE":
        app_thread_service.complete_agent_session_close(session, command_id=command.id)
    elif command.command_type == "TURN_START":
        app_thread_service.complete_agent_turn_start(
            session,
            command_id=command.id,
            result_payload=result_payload,
        )
