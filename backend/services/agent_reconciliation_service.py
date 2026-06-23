from __future__ import annotations

from sqlmodel import Session
from sqlmodel import select

from backend.models import AgentCommand, AgentCommandStatus, Device
from backend.schemas import AgentReconcileRead, AgentReconcileRequest
from backend.services.agent_command_event_service import latest_event_sequence
from backend.services.agent_command_service import AgentCommandServiceError, TERMINAL_STATUSES


def reconcile_agent(
    session: Session,
    payload: AgentReconcileRequest,
) -> AgentReconcileRead:
    device = session.get(Device, payload.device_id)
    if device is None:
        raise AgentCommandServiceError("device_not_found", "device not found")

    if not payload.command_id:
        _mark_active_sessions_recover_required(session, payload.device_id)
        return AgentReconcileRead(
            action="IDLE",
            latest_sequence=None,
            reason="no local command reported; active sessions marked recover required",
        )

    command = session.get(AgentCommand, payload.command_id)
    if command is None:
        return AgentReconcileRead(
            action="STOP",
            command_id=payload.command_id,
            latest_sequence=None,
            reason="server command not found",
        )
    if command.device_id != payload.device_id:
        raise AgentCommandServiceError(
            "agent_command_device_mismatch",
            "agent command does not belong to this device",
        )

    latest_sequence = latest_event_sequence(session, command.id)
    upload_from_sequence = None
    if latest_sequence is not None:
        last_uploaded = payload.last_uploaded_sequence or 0
        if last_uploaded > latest_sequence:
            upload_from_sequence = latest_sequence + 1

    if command.cancel_requested:
        action = "STOP"
        reason = "server command cancel requested"
    elif command.status == AgentCommandStatus.CANCELLED:
        action = "STOP"
        reason = "server command is cancelled"
    elif command.status in TERMINAL_STATUSES:
        action = "STOP"
        reason = f"server command is terminal: {command.status}"
    elif command.status in {AgentCommandStatus.CLAIMED, AgentCommandStatus.RUNNING}:
        action = "UPLOAD_EVENTS" if upload_from_sequence is not None else "CONTINUE"
        reason = "server command is still active"
    elif command.status == AgentCommandStatus.PENDING:
        action = "STOP"
        reason = "server command is pending and must be claimed again"
    else:
        action = "MARK_FAILED"
        reason = f"unsupported server command status: {command.status}"

    return AgentReconcileRead(
        action=action,
        command_id=command.id,
        server_status=command.status,
        latest_sequence=latest_sequence,
        upload_from_sequence=upload_from_sequence,
        reason=reason,
    )


def _mark_active_sessions_recover_required(session: Session, device_id: str) -> None:
    from backend.services import app_thread_service, workspace_lock_service
    from backend.models import AppThread, utc_now

    active_threads = list(
        session.exec(
            select(AppThread).where(
                AppThread.device_id == device_id,
                AppThread.status == app_thread_service.APP_THREAD_ACTIVE,
            )
        ).all()
    )
    if not active_threads:
        return
    now = utc_now()
    for app_thread in active_threads:
        app_thread.status = app_thread_service.APP_THREAD_RECOVER_REQUIRED
        app_thread.last_error = "agent restarted without active app-server session; reopen required"
        app_thread.agent_session_id = None
        app_thread.updated_at = now
        session.add(app_thread)
        if app_thread.id is not None:
            workspace_lock_service.release_workspace_lock(
                session,
                owner_type="app_thread",
                owner_id=str(app_thread.id),
            )
    session.commit()
