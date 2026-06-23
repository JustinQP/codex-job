from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from backend.models import AgentCommand, AgentCommandStatus, AppThread, AppTurn, Device, DeviceStatus, Project, Workspace, utc_now
from backend.schemas import (
    AppThreadCreate,
    AppThreadEventsRead,
    AppThreadFinalRead,
    AppThreadRead,
    AppThreadUpdate,
    AppTurnCreate,
    AppTurnRead,
)
from backend.services import agent_command_service, project_service, turn_event_service, workspace_lock_service


APP_THREAD_CREATED = "CREATED"
APP_THREAD_OPENING = "OPENING"
APP_THREAD_ACTIVE = "ACTIVE"
APP_THREAD_CLOSING = "CLOSING"
APP_THREAD_RECOVER_REQUIRED = "RECOVER_REQUIRED"
APP_THREAD_ERROR = "ERROR"
APP_THREAD_CLOSED = "CLOSED"

APP_TURN_PENDING = "PENDING"
APP_TURN_RUNNING = "RUNNING"
APP_TURN_SUCCESS = "SUCCESS"
APP_TURN_FAILED = "FAILED"
APP_TURN_CANCELLED = "CANCELLED"

STALE_TURN_ERROR = "backend restarted before app turn completed"
ARCHIVED_PREFIX = "[archived] "

APP_THREAD_STATUSES = {
    APP_THREAD_CREATED,
    APP_THREAD_OPENING,
    APP_THREAD_ACTIVE,
    APP_THREAD_CLOSING,
    APP_THREAD_RECOVER_REQUIRED,
    APP_THREAD_ERROR,
    APP_THREAD_CLOSED,
}
APP_TURN_STATUSES = {
    APP_TURN_PENDING,
    APP_TURN_RUNNING,
    APP_TURN_SUCCESS,
    APP_TURN_FAILED,
    APP_TURN_CANCELLED,
}


def create_app_thread(session: Session, payload: AppThreadCreate) -> AppThread:
    project = session.get(Project, payload.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    if not project.enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="project is disabled")

    title = _clean_title(payload.title) or _default_title()
    workspace_id = payload.workspace_id or project.workspace_id
    if workspace_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="workspace is required")
    workspace = _get_usable_workspace(session, workspace_id)
    project_service.ensure_project_workspace(session, project, workspace.id)
    device = _get_usable_device(session, workspace.device_id)

    sandbox = payload.sandbox or workspace.default_sandbox or project.default_sandbox or "read-only"
    approval_policy = payload.approval_policy or workspace.default_approval_policy or "never"
    workspace_lock_service.ensure_workspace_available(session, workspace_id=workspace.id, sandbox=sandbox)
    app_thread = AppThread(
        project_id=project.id,
        title=title,
        device_id=device.device_id,
        workspace_id=workspace.id,
        generation=1,
        sandbox=sandbox,
        approval_policy=approval_policy,
        network_access=payload.network_access,
        status=APP_THREAD_OPENING,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(app_thread)
    session.flush()
    if app_thread.id is None:
        raise ValueError("app thread id is required")
    workspace_lock_service.acquire_workspace_lock(
        session,
        workspace_id=workspace.id,
        owner_type="app_thread",
        owner_id=str(app_thread.id),
        sandbox=sandbox,
    )
    try:
        command = agent_command_service.create_command(
            session,
            device_id=device.device_id,
            command_type="SESSION_OPEN",
            aggregate_type="app_thread",
            aggregate_id=str(app_thread.id),
            idempotency_key=payload.client_request_id or f"session-open:{app_thread.id}:1",
            workspace_id=workspace.id,
            payload={
                "app_thread_id": app_thread.id,
                "workspace_id": workspace.id,
                "workspace_key": workspace.workspace_key,
                "title": title,
                "sandbox": sandbox,
                "approval_policy": approval_policy,
                "network_access": payload.network_access,
                "generation": app_thread.generation,
            },
            commit=False,
        )
    except Exception:
        session.rollback()
        raise
    app_thread.command_id = command.id
    session.add(app_thread)
    session.commit()
    session.refresh(app_thread)
    return app_thread


def complete_agent_session_open(
    session: Session,
    *,
    command_id: str,
    result_payload: dict[str, Any] | None,
) -> AppThread | None:
    command = session.get(AgentCommand, command_id)
    if command is None or command.aggregate_type != "app_thread":
        return None
    app_thread = _get_aggregate_app_thread(session, command)
    if app_thread is None:
        return None
    payload = result_payload or {}
    agent_session_id = _string_or_none(payload.get("agent_session_id"))
    codex_thread_id = _string_or_none(payload.get("codex_thread_id"))
    if command.status == AgentCommandStatus.SUCCESS and agent_session_id and codex_thread_id:
        app_thread.agent_session_id = agent_session_id
        app_thread.codex_thread_id = codex_thread_id
        app_thread.status = APP_THREAD_ACTIVE
        app_thread.last_error = None
    elif command.status == AgentCommandStatus.SUCCESS:
        app_thread.status = APP_THREAD_ERROR
        app_thread.last_error = "SESSION_OPEN succeeded without agent_session_id or codex_thread_id"
        if app_thread.id is not None:
            workspace_lock_service.release_workspace_lock(session, owner_type="app_thread", owner_id=str(app_thread.id))
    elif command.status in {AgentCommandStatus.FAILED, AgentCommandStatus.CANCELLED, AgentCommandStatus.EXPIRED}:
        app_thread.status = APP_THREAD_ERROR
        app_thread.last_error = command.last_error or f"SESSION_OPEN ended with {command.status}"
        if app_thread.id is not None:
            workspace_lock_service.release_workspace_lock(session, owner_type="app_thread", owner_id=str(app_thread.id))
    app_thread.updated_at = utc_now()
    session.add(app_thread)
    session.commit()
    session.refresh(app_thread)
    return app_thread


def complete_agent_session_close(
    session: Session,
    *,
    command_id: str,
) -> AppThread | None:
    command = session.get(AgentCommand, command_id)
    if command is None or command.aggregate_type != "app_thread":
        return None
    app_thread = _get_aggregate_app_thread(session, command)
    if app_thread is None:
        return None
    now = utc_now()
    if command.status == AgentCommandStatus.SUCCESS:
        app_thread.status = APP_THREAD_CLOSED
        app_thread.agent_session_id = None
        app_thread.last_error = None
    elif command.status in {AgentCommandStatus.FAILED, AgentCommandStatus.CANCELLED, AgentCommandStatus.EXPIRED}:
        app_thread.status = APP_THREAD_RECOVER_REQUIRED
        app_thread.last_error = command.last_error or f"SESSION_CLOSE ended with {command.status}"
    app_thread.updated_at = now
    session.add(app_thread)
    if app_thread.id is not None:
        workspace_lock_service.release_workspace_lock(session, owner_type="app_thread", owner_id=str(app_thread.id))
    session.commit()
    session.refresh(app_thread)
    return app_thread


def complete_agent_turn_start(
    session: Session,
    *,
    command_id: str,
    result_payload: dict[str, Any] | None = None,
) -> AppTurn | None:
    command = session.get(AgentCommand, command_id)
    if command is None or command.aggregate_type != "app_turn":
        return None
    app_turn = _get_aggregate_app_turn(session, command)
    if app_turn is None:
        return None
    app_thread = session.get(AppThread, app_turn.app_thread_id)
    payload = result_payload or {}
    now = utc_now()
    if app_thread is not None:
        command_payload = _json_object(command.payload_json)
        payload_generation = _int_or_none(command_payload.get("generation"))
        if payload_generation is not None and payload_generation != app_thread.generation:
            return app_turn

    if app_turn.status in {APP_TURN_CANCELLED, APP_TURN_FAILED, APP_TURN_SUCCESS}:
        return app_turn

    if command.status == AgentCommandStatus.SUCCESS:
        app_turn.status = APP_TURN_SUCCESS
        app_turn.error_message = None
        app_turn.assistant_final = _string_or_none(payload.get("assistant_final"))
        app_turn.codex_turn_id = _string_or_none(payload.get("codex_turn_id")) or _string_or_none(payload.get("turn_id"))
        app_turn.event_summary_json = _summary_json(_dict_or_empty(payload.get("event_summary")))
        if app_turn.started_at is None:
            app_turn.started_at = command.claimed_at or now
        app_turn.completed_at = now
        if app_thread is not None:
            app_thread.status = APP_THREAD_ACTIVE
            app_thread.last_error = None
            app_thread.updated_at = now
            session.add(app_thread)
    elif command.status in {AgentCommandStatus.FAILED, AgentCommandStatus.CANCELLED, AgentCommandStatus.EXPIRED}:
        app_turn.status = APP_TURN_CANCELLED if command.status == AgentCommandStatus.CANCELLED else APP_TURN_FAILED
        app_turn.error_message = command.last_error or _string_or_none(payload.get("error")) or f"TURN_START ended with {command.status}"
        if app_turn.started_at is None:
            app_turn.started_at = command.claimed_at
        app_turn.completed_at = now
        if app_thread is not None:
            app_thread.status = APP_THREAD_RECOVER_REQUIRED
            app_thread.last_error = app_turn.error_message
            app_thread.updated_at = now
            session.add(app_thread)

    session.add(app_turn)
    session.commit()
    session.refresh(app_turn)
    return app_turn


def mark_agent_turn_running(session: Session, *, command_id: str) -> AppTurn | None:
    command = session.get(AgentCommand, command_id)
    if command is None or command.aggregate_type != "app_turn":
        return None
    app_turn = _get_aggregate_app_turn(session, command)
    if app_turn is None or app_turn.status != APP_TURN_PENDING:
        return app_turn
    now = utc_now()
    app_turn.status = APP_TURN_RUNNING
    app_turn.started_at = now
    app_thread = session.get(AppThread, app_turn.app_thread_id)
    if app_thread is not None:
        app_thread.status = APP_THREAD_ACTIVE
        app_thread.updated_at = now
        session.add(app_thread)
    session.add(app_turn)
    session.commit()
    session.refresh(app_turn)
    return app_turn


def list_app_threads(
    session: Session,
    project_id: int | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    include_archived: bool = False,
) -> list[AppThread]:
    normalized_status = _normalize_status(status_filter, APP_THREAD_STATUSES, "app thread status")
    statement = select(AppThread)
    if project_id is not None:
        statement = statement.where(AppThread.project_id == project_id)
    if normalized_status is not None:
        statement = statement.where(AppThread.status == normalized_status)
    if not include_archived:
        statement = statement.where(AppThread.title.not_like(f"{ARCHIVED_PREFIX}%"))
    statement = statement.order_by(AppThread.id.desc()).limit(limit)
    return list(session.exec(statement).all())


def cleanup_app_threads(session: Session, status_filter: str, limit: int = 50) -> dict[str, Any]:
    normalized_status = _normalize_status(
        status_filter,
        {APP_THREAD_CLOSED, APP_THREAD_ERROR, APP_THREAD_RECOVER_REQUIRED},
        "cleanup status",
    )
    if normalized_status is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cleanup status is required")
    app_threads = list(
        session.exec(
            select(AppThread)
            .where(AppThread.status == normalized_status, AppThread.title.not_like(f"{ARCHIVED_PREFIX}%"))
            .order_by(AppThread.id.desc())
            .limit(limit)
        ).all()
    )
    archived_ids: list[int] = []
    now = utc_now()
    for app_thread in app_threads:
        if app_thread.id is None:
            continue
        app_thread.title = f"{ARCHIVED_PREFIX}{app_thread.title}"
        app_thread.updated_at = now
        session.add(app_thread)
        archived_ids.append(app_thread.id)
    session.commit()
    return {"archived_count": len(archived_ids), "archived_thread_ids": archived_ids}


def get_app_thread_or_404(session: Session, app_thread_id: int) -> AppThread:
    app_thread = session.get(AppThread, app_thread_id)
    if app_thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="app thread not found")
    return app_thread


def rename_app_thread(session: Session, app_thread_id: int, payload: AppThreadUpdate) -> AppThread:
    title = _clean_title(payload.title)
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="title cannot be empty")
    app_thread = get_app_thread_or_404(session, app_thread_id)
    app_thread.title = title
    app_thread.updated_at = utc_now()
    session.add(app_thread)
    session.commit()
    session.refresh(app_thread)
    return app_thread


def close_app_thread(session: Session, app_thread_id: int) -> AppThread:
    app_thread = get_app_thread_or_404(session, app_thread_id)
    if app_thread.status == APP_THREAD_CLOSED:
        return app_thread
    if app_thread.device_id and app_thread.workspace_id is not None and app_thread.agent_session_id:
        command = agent_command_service.create_command(
            session,
            device_id=app_thread.device_id,
            command_type="SESSION_CLOSE",
            aggregate_type="app_thread",
            aggregate_id=str(app_thread.id),
            idempotency_key=f"session-close:{app_thread.id}:{app_thread.generation}",
            workspace_id=app_thread.workspace_id,
            payload={
                "app_thread_id": app_thread.id,
                "agent_session_id": app_thread.agent_session_id,
                "generation": app_thread.generation,
            },
        )
        app_thread.command_id = command.id
        app_thread.status = APP_THREAD_CLOSING
    else:
        app_thread.status = APP_THREAD_CLOSED
        if app_thread.id is not None:
            workspace_lock_service.release_workspace_lock(session, owner_type="app_thread", owner_id=str(app_thread.id))
    app_thread.updated_at = utc_now()
    session.add(app_thread)
    session.commit()
    session.refresh(app_thread)
    return app_thread


def reopen_app_thread(session: Session, app_thread_id: int) -> AppThread:
    app_thread = get_app_thread_or_404(session, app_thread_id)
    if app_thread.id is None:
        raise ValueError("app thread id is required")
    if app_thread.workspace_id is None:
        project = session.get(Project, app_thread.project_id)
        if project is None or project.workspace_id is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="app thread is not bound to a workspace")
        app_thread.workspace_id = project.workspace_id
    workspace = _get_usable_workspace(session, app_thread.workspace_id)
    device = _get_usable_device(session, workspace.device_id)
    next_generation = (app_thread.generation or 1) + 1
    reopen_sandbox = app_thread.sandbox or workspace.default_sandbox or "read-only"
    workspace_lock_service.ensure_workspace_available(session, workspace_id=workspace.id, sandbox=reopen_sandbox)
    now = utc_now()
    app_thread.device_id = device.device_id
    app_thread.workspace_id = workspace.id
    app_thread.agent_session_id = None
    app_thread.codex_thread_id = None
    app_thread.generation = next_generation
    app_thread.status = APP_THREAD_OPENING
    app_thread.last_error = None
    app_thread.updated_at = now
    session.add(app_thread)
    session.flush()
    workspace_lock_service.acquire_workspace_lock(
        session,
        workspace_id=workspace.id,
        owner_type="app_thread",
        owner_id=str(app_thread.id),
        sandbox=reopen_sandbox,
    )
    try:
        command = agent_command_service.create_command(
            session,
            device_id=device.device_id,
            command_type="SESSION_OPEN",
            aggregate_type="app_thread",
            aggregate_id=str(app_thread.id),
            idempotency_key=f"session-open:{app_thread.id}:{next_generation}",
            workspace_id=workspace.id,
            payload={
                "app_thread_id": app_thread.id,
                "workspace_id": workspace.id,
                "workspace_key": workspace.workspace_key,
                "title": app_thread.title,
                "sandbox": reopen_sandbox,
                "approval_policy": app_thread.approval_policy or workspace.default_approval_policy or "never",
                "network_access": app_thread.network_access,
                "generation": next_generation,
            },
            commit=False,
        )
    except Exception:
        session.rollback()
        raise
    app_thread.command_id = command.id
    session.add(app_thread)
    session.commit()
    session.refresh(app_thread)
    return app_thread


def send_app_turn(session: Session, app_thread_id: int, payload: AppTurnCreate) -> AppTurn:
    return create_async_app_turn(session, app_thread_id, payload)


def create_async_app_turn(session: Session, app_thread_id: int, payload: AppTurnCreate) -> AppTurn:
    app_thread = get_app_thread_or_404(session, app_thread_id)
    message = str(payload.message or "").strip()
    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="message cannot be empty")
    return create_agent_async_app_turn(session, app_thread, message)


def create_agent_async_app_turn(session: Session, app_thread: AppThread, message: str) -> AppTurn:
    if app_thread.id is None:
        raise ValueError("app thread id is required")
    _ensure_app_thread_can_accept_turn(app_thread)
    if not app_thread.device_id or app_thread.workspace_id is None or not app_thread.agent_session_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="app thread is not bound to an agent session")
    workspace = _get_usable_workspace(session, app_thread.workspace_id)
    if workspace.device_id != app_thread.device_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="workspace device mismatch")
    _get_usable_device(session, app_thread.device_id)
    app_turn = _create_active_app_turn(
        session,
        app_thread_id=app_thread.id,
        message=message,
        status_value=APP_TURN_PENDING,
        created_at=utc_now(),
        commit=False,
    )
    if app_turn.id is None:
        raise ValueError("app turn id is required")

    try:
        command = agent_command_service.create_command(
            session,
            device_id=app_thread.device_id,
            command_type="TURN_START",
            aggregate_type="app_turn",
            aggregate_id=str(app_turn.id),
            idempotency_key=f"turn-start:{app_turn.id}",
            workspace_id=workspace.id,
            payload={
                "app_thread_id": app_thread.id,
                "app_turn_id": app_turn.id,
                "agent_session_id": app_thread.agent_session_id,
                "codex_thread_id": app_thread.codex_thread_id,
                "workspace_id": workspace.id,
                "workspace_key": workspace.workspace_key,
                "generation": app_thread.generation,
                "message": message,
                "sandbox": app_thread.sandbox,
                "approval_policy": app_thread.approval_policy,
                "network_access": app_thread.network_access,
            },
            commit=False,
        )
    except Exception:
        session.rollback()
        raise
    app_turn.command_id = command.id
    session.add(app_turn)
    session.commit()
    session.refresh(app_turn)
    return app_turn


def list_app_turns(
    session: Session,
    app_thread_id: int,
    status_filter: str | None = None,
    limit: int = 100,
) -> list[AppTurn]:
    get_app_thread_or_404(session, app_thread_id)
    normalized_status = _normalize_status(status_filter, APP_TURN_STATUSES, "app turn status")
    statement = select(AppTurn).where(AppTurn.app_thread_id == app_thread_id).order_by(AppTurn.id.desc()).limit(limit)
    if normalized_status is not None:
        statement = (
            select(AppTurn)
            .where(AppTurn.app_thread_id == app_thread_id, AppTurn.status == normalized_status)
            .order_by(AppTurn.id.desc())
            .limit(limit)
        )
    return sorted(session.exec(statement).all(), key=lambda app_turn: app_turn.id or 0)


def recover_stale_app_turns(session: Session) -> dict[str, Any]:
    stale_turns = list(
        session.exec(
            select(AppTurn)
            .where(AppTurn.status.in_([APP_TURN_PENDING, APP_TURN_RUNNING]))
            .order_by(AppTurn.id)
        ).all()
    )
    if not stale_turns:
        return {"recovered_count": 0, "recovered_turn_ids": []}

    now = utc_now()
    recovered_turn_ids: list[int] = []
    touched_thread_ids: set[int] = set()
    for app_turn in stale_turns:
        app_turn.status = APP_TURN_FAILED
        app_turn.error_message = STALE_TURN_ERROR
        app_turn.completed_at = now
        session.add(app_turn)
        if app_turn.id is not None:
            recovered_turn_ids.append(app_turn.id)
        touched_thread_ids.add(app_turn.app_thread_id)

    for app_thread_id in touched_thread_ids:
        app_thread = session.get(AppThread, app_thread_id)
        if app_thread is None:
            continue
        app_thread.status = APP_THREAD_RECOVER_REQUIRED
        app_thread.last_error = STALE_TURN_ERROR
        app_thread.updated_at = now
        session.add(app_thread)
    session.commit()
    return {"recovered_count": len(recovered_turn_ids), "recovered_turn_ids": recovered_turn_ids}


def get_app_turn_or_404(session: Session, app_turn_id: int) -> AppTurn:
    app_turn = session.get(AppTurn, app_turn_id)
    if app_turn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="app turn not found")
    return app_turn


def cancel_app_turn(session: Session, app_turn_id: int) -> AppTurn:
    app_turn = get_app_turn_or_404(session, app_turn_id)
    if app_turn.status in {APP_TURN_SUCCESS, APP_TURN_FAILED, APP_TURN_CANCELLED}:
        return app_turn
    if app_turn.command_id:
        agent_command_service.request_cancel_command(session, command_id=app_turn.command_id)

    now = utc_now()
    app_turn.status = APP_TURN_CANCELLED
    app_turn.error_message = "cancelled by user"
    app_turn.completed_at = now
    app_thread = session.get(AppThread, app_turn.app_thread_id)
    if app_thread is not None:
        app_thread.status = APP_THREAD_RECOVER_REQUIRED
        app_thread.last_error = "cancelled by user; reopen required before next turn"
        app_thread.updated_at = now
        session.add(app_thread)
        if app_thread.id is not None:
            workspace_lock_service.release_workspace_lock(session, owner_type="app_thread", owner_id=str(app_thread.id))
    session.add(app_turn)
    session.commit()
    session.refresh(app_turn)
    return app_turn


def get_app_thread_final(session: Session, app_thread_id: int) -> AppThreadFinalRead:
    get_app_thread_or_404(session, app_thread_id)
    latest_turn = _latest_success_turn(session, app_thread_id)
    return AppThreadFinalRead(app_thread_id=app_thread_id, assistant_final=latest_turn.assistant_final if latest_turn else None)


def get_app_thread_events(session: Session, app_thread_id: int) -> AppThreadEventsRead:
    get_app_thread_or_404(session, app_thread_id)
    latest_turn = session.exec(
        select(AppTurn)
        .where(AppTurn.app_thread_id == app_thread_id, AppTurn.event_summary_json.is_not(None))
        .order_by(AppTurn.id.desc())
    ).first()
    return AppThreadEventsRead(
        app_thread_id=app_thread_id,
        latest_turn_id=latest_turn.id if latest_turn else None,
        event_summary=_event_summary_from_json(latest_turn.event_summary_json) if latest_turn else None,
    )


def get_app_turn_stream_snapshot(session: Session, app_turn_id: int, since: int = 0) -> dict[str, Any]:
    app_turn = get_app_turn_or_404(session, app_turn_id)
    persisted_events = turn_event_service.list_turn_event_models(
        session,
        turn_id=app_turn_id,
        since=since,
        limit=100,
    )
    if persisted_events:
        events = [_stream_event_from_turn_event(event) for event in persisted_events]
        next_sequence = max(event.sequence for event in persisted_events)
        terminal = app_turn.status in {APP_TURN_SUCCESS, APP_TURN_FAILED, APP_TURN_CANCELLED}
        if terminal:
            terminal_event = _terminal_stream_event(app_turn, next_sequence + 1)
            if terminal_event is not None:
                events.append(terminal_event)
                next_sequence += 1
        return {"next_index": next_sequence, "events": events, "terminal": terminal}
    terminal_event = _terminal_stream_event(app_turn, since + 1)
    if terminal_event is not None:
        return {"next_index": since + 1, "events": [terminal_event], "terminal": True}
    return {
        "next_index": since,
        "events": [
            {
                "kind": "status",
                "turn_id": app_turn.id,
                "sequence": since,
                "status": app_turn.status,
            }
        ] if since == 0 else [],
        "terminal": False,
    }


def to_app_thread_read(session: Session, app_thread: AppThread) -> AppThreadRead:
    if app_thread.id is None:
        raise ValueError("app thread id is required")
    latest_turn = _latest_success_turn(session, app_thread.id)
    turn_count = len(session.exec(select(AppTurn).where(AppTurn.app_thread_id == app_thread.id)).all())
    return AppThreadRead(
        id=app_thread.id,
        project_id=app_thread.project_id,
        title=app_thread.title,
        device_id=app_thread.device_id,
        workspace_id=app_thread.workspace_id,
        agent_session_id=app_thread.agent_session_id,
        generation=app_thread.generation,
        sandbox=app_thread.sandbox,
        approval_policy=app_thread.approval_policy,
        network_access=app_thread.network_access,
        command_id=app_thread.command_id,
        codex_thread_id=app_thread.codex_thread_id,
        status=app_thread.status,
        last_error=app_thread.last_error,
        latest_assistant_final=latest_turn.assistant_final if latest_turn else None,
        turn_count=turn_count,
        created_at=app_thread.created_at,
        updated_at=app_thread.updated_at,
    )


def to_app_turn_read(app_turn: AppTurn) -> AppTurnRead:
    if app_turn.id is None:
        raise ValueError("app turn id is required")
    duration_seconds = None
    if app_turn.started_at and app_turn.completed_at:
        duration_seconds = (app_turn.completed_at - app_turn.started_at).total_seconds()
    return AppTurnRead(
        id=app_turn.id,
        app_thread_id=app_turn.app_thread_id,
        command_id=app_turn.command_id,
        user_message=app_turn.user_message,
        assistant_final=app_turn.assistant_final,
        status=app_turn.status,
        error_message=app_turn.error_message,
        codex_turn_id=app_turn.codex_turn_id,
        created_at=app_turn.created_at,
        started_at=app_turn.started_at,
        completed_at=app_turn.completed_at,
        duration_seconds=duration_seconds,
        event_summary=_event_summary_from_json(app_turn.event_summary_json),
    )


def normalize_event_summary(events_result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(events_result, dict) or not events_result:
        return None
    summary = events_result.get("summary")
    if not isinstance(summary, dict):
        summary = events_result
    if _looks_like_normalized_summary(summary):
        event_type_counts = _dict_or_empty(summary.get("event_type_counts"))
        errors = _list_or_empty(summary.get("errors"))
        assistant_preview = _string_or_default(summary.get("assistant_text_preview"))
        return {
            "total_events": _int_or_default(summary.get("total_events"), 0),
            "event_type_counts": event_type_counts,
            "has_error": _bool_or_default(summary.get("has_error"), bool(errors)),
            "errors": errors,
            "assistant_text_length": _int_or_default(summary.get("assistant_text_length"), len(assistant_preview)),
            "assistant_text_preview": assistant_preview,
            "raw": _dict_or_empty(summary.get("raw")),
        }
    event_type_counts = _dict_or_empty(
        summary.get("event_type_counts") or summary.get("event_counts") or summary.get("type_counts")
    )
    errors = _list_or_empty(summary.get("errors"))
    assistant_preview = _string_or_default(
        summary.get("assistant_text_preview")
        or summary.get("assistant_final_preview")
        or summary.get("assistant_preview")
        or _extract_text_preview(summary)
    )
    return {
        "total_events": _int_or_default(summary.get("total_events"), 0),
        "event_type_counts": event_type_counts,
        "has_error": _bool_or_default(summary.get("has_error"), bool(errors)),
        "errors": errors,
        "assistant_text_length": _int_or_default(summary.get("assistant_text_length"), len(assistant_preview)),
        "assistant_text_preview": assistant_preview,
        "raw": summary,
    }


def _get_usable_workspace(session: Session, workspace_id: int) -> Workspace:
    workspace = session.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="workspace not found")
    if not workspace.enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="workspace is disabled")
    return workspace


def _get_usable_device(session: Session, device_id: str) -> Device:
    device = session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device not found")
    if device.status == DeviceStatus.DISABLED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="device is disabled")
    if device.status != DeviceStatus.ONLINE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="device is offline")
    return device


def _get_aggregate_app_thread(session: Session, command: AgentCommand) -> AppThread | None:
    try:
        app_thread_id = int(command.aggregate_id or "0")
    except ValueError:
        return None
    return session.get(AppThread, app_thread_id)


def _get_aggregate_app_turn(session: Session, command: AgentCommand) -> AppTurn | None:
    try:
        app_turn_id = int(command.aggregate_id or "0")
    except ValueError:
        return None
    return session.get(AppTurn, app_turn_id)


def _stream_event_from_turn_event(event) -> dict[str, Any]:
    payload = turn_event_service.to_turn_event_read(event).payload
    stream_event = _stream_event_from_payload(
        turn_id=event.turn_id,
        sequence=event.sequence,
        kind=event.kind,
        payload=payload,
    )
    stream_event["sequence"] = event.sequence
    return stream_event


def _stream_event_from_payload(
    *,
    turn_id: int,
    sequence: int,
    kind: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if kind == "status":
        return {"kind": "status", "turn_id": turn_id, "sequence": sequence, "status": _string_or_none(payload.get("status")) or "RUNNING"}
    if kind == "final":
        return {
            "kind": "final",
            "turn_id": turn_id,
            "sequence": sequence,
            "assistant_final": _string_or_none(payload.get("assistant_final")) or _string_or_none(payload.get("assistant_final_preview")),
            "event": payload,
        }
    delta = _extract_persisted_assistant_delta(payload)
    if delta:
        return {"kind": "assistant_delta", "turn_id": turn_id, "sequence": sequence, "text": delta, "event": payload}
    if "error" in kind.lower() or payload.get("error"):
        return {
            "kind": "error",
            "turn_id": turn_id,
            "sequence": sequence,
            "message": _string_or_none(payload.get("message")) or _string_or_default(payload.get("error"), kind),
            "event": payload,
        }
    return {"kind": "event", "turn_id": turn_id, "sequence": sequence, "event_kind": kind, "event": payload}


def _terminal_stream_event(app_turn: AppTurn, sequence: int) -> dict[str, Any] | None:
    if app_turn.status == APP_TURN_SUCCESS:
        return {"kind": "final", "turn_id": app_turn.id, "sequence": sequence, "status": app_turn.status, "turn": to_app_turn_read(app_turn).model_dump(mode="json")}
    if app_turn.status in {APP_TURN_FAILED, APP_TURN_CANCELLED}:
        return {
            "kind": "error",
            "turn_id": app_turn.id,
            "sequence": sequence,
            "status": app_turn.status,
            "message": app_turn.error_message or app_turn.status,
            "turn": to_app_turn_read(app_turn).model_dump(mode="json"),
        }
    return None


def _extract_persisted_assistant_delta(payload: dict[str, Any]) -> str | None:
    for container in _persisted_event_containers(payload):
        delta = container.get("delta")
        if isinstance(delta, str) and delta:
            return delta
    return None


def _persisted_event_containers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    containers = [payload]
    event = payload.get("event")
    if isinstance(event, dict):
        containers.extend(_event_containers(event))
    return containers


def _ensure_app_thread_can_accept_turn(app_thread: AppThread) -> None:
    if app_thread.status == APP_THREAD_CLOSED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="app thread is closed")
    if app_thread.status != APP_THREAD_ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "app_thread_not_active", "message": "app thread is not active", "status": app_thread.status},
        )


def _latest_success_turn(session: Session, app_thread_id: int) -> AppTurn | None:
    return session.exec(
        select(AppTurn)
        .where(AppTurn.app_thread_id == app_thread_id, AppTurn.status == APP_TURN_SUCCESS)
        .order_by(AppTurn.id.desc())
    ).first()


def _create_active_app_turn(
    session: Session,
    *,
    app_thread_id: int,
    message: str,
    status_value: str,
    created_at,
    started_at=None,
    commit: bool = True,
) -> AppTurn:
    active_turn = _get_active_app_turn(session, app_thread_id)
    if active_turn is not None:
        _raise_app_turn_conflict(active_turn)
    app_turn = AppTurn(
        app_thread_id=app_thread_id,
        user_message=message,
        status=status_value,
        created_at=created_at,
        started_at=started_at,
    )
    session.add(app_turn)
    try:
        if commit:
            session.commit()
        else:
            session.flush()
    except IntegrityError:
        session.rollback()
        active_turn = _get_active_app_turn(session, app_thread_id)
        if active_turn is not None:
            _raise_app_turn_conflict(active_turn)
        raise
    session.refresh(app_turn)
    return app_turn


def _raise_app_turn_conflict(active_turn: AppTurn) -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "app_turn_conflict",
            "message": "app thread already has a pending or running app turn",
            "app_turn_id": active_turn.id,
        },
    )


def _get_active_app_turn(session: Session, app_thread_id: int) -> AppTurn | None:
    return session.exec(
        select(AppTurn)
        .where(AppTurn.app_thread_id == app_thread_id, AppTurn.status.in_([APP_TURN_PENDING, APP_TURN_RUNNING]))
        .order_by(AppTurn.id)
    ).first()


def _summary_json(events_result: dict[str, Any] | None) -> str | None:
    normalized = normalize_event_summary(events_result)
    if normalized is None:
        return None
    return json.dumps(normalized, ensure_ascii=False)


def _event_summary_from_json(raw_value: str | None) -> dict[str, Any] | None:
    if raw_value is None:
        return None
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return {"invalid_summary": raw_value}
    if not isinstance(parsed, dict):
        return {"invalid_summary": raw_value}
    normalized = normalize_event_summary(parsed)
    return normalized or parsed


def _looks_like_normalized_summary(value: dict[str, Any]) -> bool:
    return "raw" in value


def _normalize_status(value: str | None, allowed: set[str], field_name: str) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().upper()
    if not normalized:
        return None
    if normalized not in allowed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid {field_name}: {value}")
    return normalized


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _bool_or_default(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _int_or_default(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return default


def _string_or_default(value: Any, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _extract_text_preview(summary: dict[str, Any]) -> str:
    for key in ("text", "content", "output", "message"):
        value = summary.get(key)
        if isinstance(value, str):
            return value[:500]
    return ""


def _event_containers(event: dict[str, Any]) -> list[dict[str, Any]]:
    containers: list[dict[str, Any]] = [event]
    for key in ("params", "result", "item", "message", "delta", "content", "output"):
        value = event.get(key)
        if isinstance(value, dict):
            containers.append(value)
    params = event.get("params")
    result = event.get("result")
    for parent in (params, result):
        if isinstance(parent, dict):
            for key in ("item", "message", "delta", "content", "output"):
                value = parent.get(key)
                if isinstance(value, dict):
                    containers.append(value)
    return containers


def _clean_title(value: str | None) -> str:
    return str(value or "").strip()


def _default_title() -> str:
    timestamp = datetime.now().strftime("%H%M%S")
    return f"App Thread {timestamp}"


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _json_object(raw_value: str | None) -> dict[str, Any]:
    if not raw_value:
        return {}
    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}
