from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlmodel import Session, select

from backend.config import get_settings
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
from backend.services.app_server_bridge_client import (
    AppServerBridgeClient,
    AppServerBridgeError,
    get_default_client,
)
from backend.services import agent_command_service
from backend.services import turn_event_service


APP_THREAD_CREATED = "CREATED"
APP_THREAD_OPENING = "OPENING"
APP_THREAD_ACTIVE = "ACTIVE"
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


def create_app_thread(
    session: Session,
    payload: AppThreadCreate,
    bridge_client: AppServerBridgeClient | None = None,
) -> AppThread:
    project = session.get(Project, payload.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    if not project.enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="project is disabled")

    title = _clean_title(payload.title) or _default_title()
    if get_settings().agent_command_mode:
        return create_agent_app_thread(session, project, payload, title)

    client = bridge_client or get_default_client()
    try:
        bridge_thread = client.create_thread(title, cwd=project.path)
    except AppServerBridgeError as exc:
        raise _bridge_http_exception(exc) from exc
    bridge_thread_id = _require_bridge_thread_id(bridge_thread)

    now = utc_now()
    app_thread = AppThread(
        project_id=payload.project_id,
        title=title,
        bridge_thread_id=bridge_thread_id,
        app_thread_id=_string_or_none(bridge_thread.get("app_thread_id")),
        status=APP_THREAD_ACTIVE,
        created_at=now,
        updated_at=now,
    )
    session.add(app_thread)
    session.commit()
    session.refresh(app_thread)
    return app_thread


def create_agent_app_thread(
    session: Session,
    project: Project,
    payload: AppThreadCreate,
    title: str,
) -> AppThread:
    workspace_id = payload.workspace_id or project.workspace_id
    if workspace_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="workspace is required")
    workspace = session.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="workspace not found")
    if not workspace.enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="workspace is disabled")
    device = session.get(Device, workspace.device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device not found")
    if device.status == DeviceStatus.DISABLED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="device is disabled")
    if device.status != DeviceStatus.ONLINE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="device is offline")

    sandbox = payload.sandbox or workspace.default_sandbox or project.default_sandbox or "read-only"
    approval_policy = payload.approval_policy or workspace.default_approval_policy or "never"
    app_thread = AppThread(
        project_id=project.id,
        title=title,
        device_id=workspace.device_id,
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
    session.commit()
    session.refresh(app_thread)
    command = agent_command_service.create_command(
        session,
        device_id=workspace.device_id,
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
    )
    app_thread.command_id = command.id
    session.add(app_thread)
    session.commit()
    session.refresh(app_thread)
    return app_thread


def complete_agent_session_open(
    session: Session,
    *,
    command_id: str,
    result_payload: dict[str, Any],
) -> AppThread | None:
    command = session.get(AgentCommand, command_id)
    if command is None or command.aggregate_type != "app_thread":
        return None
    try:
        app_thread_id = int(command.aggregate_id or "0")
    except ValueError:
        return None
    app_thread = session.get(AppThread, app_thread_id)
    if app_thread is None:
        return None
    agent_session_id = _string_or_none(result_payload.get("agent_session_id"))
    codex_thread_id = _string_or_none(result_payload.get("codex_thread_id"))
    if command.status == AgentCommandStatus.SUCCESS and agent_session_id and codex_thread_id:
        app_thread.agent_session_id = agent_session_id
        app_thread.app_thread_id = codex_thread_id
        app_thread.status = APP_THREAD_ACTIVE
        app_thread.last_error = None
    elif command.status in {AgentCommandStatus.FAILED, AgentCommandStatus.CANCELLED, AgentCommandStatus.EXPIRED}:
        app_thread.status = APP_THREAD_ERROR
        app_thread.last_error = command.last_error or f"SESSION_OPEN ended with {command.status}"
    app_thread.updated_at = utc_now()
    session.add(app_thread)
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
    try:
        app_turn_id = int(command.aggregate_id or "0")
    except ValueError:
        return None
    app_turn = session.get(AppTurn, app_turn_id)
    if app_turn is None:
        return None
    app_thread = session.get(AppThread, app_turn.app_thread_id)
    now = utc_now()
    payload = result_payload or {}

    if command.status == AgentCommandStatus.SUCCESS:
        app_turn.status = APP_TURN_SUCCESS
        app_turn.error_message = None
        app_turn.assistant_final = _string_or_none(payload.get("assistant_final"))
        app_turn.bridge_turn_id = _string_or_none(payload.get("codex_turn_id")) or _string_or_none(payload.get("turn_id"))
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
        if command.status == AgentCommandStatus.CANCELLED:
            app_turn.status = APP_TURN_CANCELLED
        else:
            app_turn.status = APP_TURN_FAILED
        app_turn.error_message = command.last_error or _string_or_none(payload.get("error")) or f"TURN_START ended with {command.status}"
        if app_turn.started_at is None:
            app_turn.started_at = command.claimed_at
        app_turn.completed_at = now
        if app_thread is not None:
            app_thread.status = APP_THREAD_ERROR if app_turn.status == APP_TURN_FAILED else APP_THREAD_ACTIVE
            app_thread.last_error = app_turn.error_message if app_turn.status == APP_TURN_FAILED else None
            app_thread.updated_at = now
            session.add(app_thread)

    session.add(app_turn)
    session.commit()
    session.refresh(app_turn)
    return app_turn


def mark_agent_turn_running(
    session: Session,
    *,
    command_id: str,
) -> AppTurn | None:
    command = session.get(AgentCommand, command_id)
    if command is None or command.aggregate_type != "app_turn":
        return None
    try:
        app_turn_id = int(command.aggregate_id or "0")
    except ValueError:
        return None
    app_turn = session.get(AppTurn, app_turn_id)
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
    normalized_status = _normalize_status(status_filter, {APP_THREAD_CLOSED, APP_THREAD_ERROR}, "cleanup status")
    if normalized_status is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cleanup status is required")

    app_threads = list(
        session.exec(
            select(AppThread)
            .where(
                AppThread.status == normalized_status,
                AppThread.title.not_like(f"{ARCHIVED_PREFIX}%"),
            )
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
    return {
        "archived_count": len(archived_ids),
        "archived_thread_ids": archived_ids,
    }


def get_app_thread_or_404(session: Session, app_thread_id: int) -> AppThread:
    app_thread = session.get(AppThread, app_thread_id)
    if app_thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="app thread not found")
    return app_thread


def rename_app_thread(
    session: Session,
    app_thread_id: int,
    payload: AppThreadUpdate,
    bridge_client: AppServerBridgeClient | None = None,
) -> AppThread:
    title = _clean_title(payload.title)
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="title cannot be empty")
    app_thread = get_app_thread_or_404(session, app_thread_id)
    if app_thread.bridge_thread_id:
        client = bridge_client or get_default_client()
        try:
            client.rename_thread(app_thread.bridge_thread_id, title)
        except AppServerBridgeError as exc:
            app_thread.status = APP_THREAD_ERROR
            app_thread.last_error = exc.message
            app_thread.updated_at = utc_now()
            session.add(app_thread)
            session.commit()
            raise _bridge_http_exception(exc) from exc

    app_thread.title = title
    app_thread.updated_at = utc_now()
    session.add(app_thread)
    session.commit()
    session.refresh(app_thread)
    return app_thread


def close_app_thread(
    session: Session,
    app_thread_id: int,
    bridge_client: AppServerBridgeClient | None = None,
) -> AppThread:
    app_thread = get_app_thread_or_404(session, app_thread_id)
    if app_thread.bridge_thread_id:
        client = bridge_client or get_default_client()
        try:
            client.delete_thread(app_thread.bridge_thread_id)
        except AppServerBridgeError as exc:
            if exc.status_code != status.HTTP_404_NOT_FOUND:
                app_thread.status = APP_THREAD_ERROR
                app_thread.last_error = exc.message
                app_thread.updated_at = utc_now()
                session.add(app_thread)
                session.commit()
                raise _bridge_http_exception(exc) from exc

    app_thread.status = APP_THREAD_CLOSED
    app_thread.updated_at = utc_now()
    session.add(app_thread)
    session.commit()
    session.refresh(app_thread)
    return app_thread


def reopen_app_thread(
    session: Session,
    app_thread_id: int,
    bridge_client: AppServerBridgeClient | None = None,
) -> AppThread:
    app_thread = get_app_thread_or_404(session, app_thread_id)
    project = session.get(Project, app_thread.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    if not project.enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="project is disabled")
    client = bridge_client or get_default_client()
    try:
        bridge_thread = client.create_thread(app_thread.title, cwd=project.path)
    except AppServerBridgeError as exc:
        app_thread.status = APP_THREAD_ERROR
        app_thread.last_error = exc.message
        app_thread.updated_at = utc_now()
        session.add(app_thread)
        session.commit()
        raise _bridge_http_exception(exc) from exc

    bridge_thread_id = _require_bridge_thread_id(bridge_thread)
    app_thread.bridge_thread_id = bridge_thread_id
    app_thread.app_thread_id = _string_or_none(bridge_thread.get("app_thread_id"))
    app_thread.status = APP_THREAD_ACTIVE
    app_thread.last_error = None
    app_thread.updated_at = utc_now()
    session.add(app_thread)
    session.commit()
    session.refresh(app_thread)
    return app_thread


def send_app_turn(
    session: Session,
    app_thread_id: int,
    payload: AppTurnCreate,
    bridge_client: AppServerBridgeClient | None = None,
) -> AppTurn:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="message cannot be empty")

    app_thread = get_app_thread_or_404(session, app_thread_id)
    if app_thread.status == APP_THREAD_CLOSED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="app thread is closed")
    if not app_thread.bridge_thread_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="app thread has no bridge thread id")

    now = utc_now()
    app_turn = AppTurn(
        app_thread_id=app_thread.id,
        user_message=message,
        status=APP_TURN_RUNNING,
        created_at=now,
        started_at=now,
    )
    session.add(app_turn)
    session.commit()
    session.refresh(app_turn)

    client = bridge_client or get_default_client()
    try:
        bridge_result = client.send_turn(app_thread.bridge_thread_id, message)
        events_result = _best_effort_events(client, app_thread.bridge_thread_id)
    except AppServerBridgeError as exc:
        _mark_turn_failed(session, app_thread, app_turn, exc.message)
        raise _bridge_http_exception(exc) from exc

    completed_at = utc_now()
    full_final = _bridge_final(client, app_thread.bridge_thread_id)
    preview_final = _string_or_none(bridge_result.get("assistant_final_preview"))
    app_turn.status = APP_TURN_SUCCESS
    app_turn.assistant_final = full_final or preview_final
    app_turn.bridge_turn_id = _string_or_none(bridge_result.get("turn_id"))
    app_turn.event_summary_json = _summary_json(events_result)
    app_turn.completed_at = completed_at
    app_thread.status = APP_THREAD_ACTIVE
    app_thread.last_error = None
    app_thread.updated_at = completed_at
    session.add(app_thread)
    session.add(app_turn)
    session.commit()
    session.refresh(app_turn)
    return app_turn


def create_async_app_turn(
    session: Session,
    app_thread_id: int,
    payload: AppTurnCreate,
) -> AppTurn:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="message cannot be empty")

    app_thread = get_app_thread_or_404(session, app_thread_id)
    if app_thread.status == APP_THREAD_CLOSED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="app thread is closed")
    if get_settings().agent_command_mode:
        return create_agent_async_app_turn(session, app_thread, message, payload)
    if not app_thread.bridge_thread_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="app thread has no bridge thread id")
    active_turn = _get_active_app_turn(session, app_thread.id)
    if active_turn is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "app_turn_conflict",
                "message": "app thread already has a pending or running app turn",
                "app_turn_id": active_turn.id,
            },
        )

    app_turn = AppTurn(
        app_thread_id=app_thread.id,
        user_message=message,
        status=APP_TURN_PENDING,
        created_at=utc_now(),
    )
    session.add(app_turn)
    session.commit()
    session.refresh(app_turn)

    if app_turn.id is None:
        raise ValueError("app turn id is required")
    from backend.services.app_turn_executor import submit_app_turn

    submit_app_turn(app_turn.id)
    return app_turn


def create_agent_async_app_turn(
    session: Session,
    app_thread: AppThread,
    message: str,
    payload: AppTurnCreate,
) -> AppTurn:
    if app_thread.id is None:
        raise ValueError("app thread id is required")
    if app_thread.status != APP_THREAD_ACTIVE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="app thread is not active")
    if not app_thread.device_id or app_thread.workspace_id is None or not app_thread.agent_session_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="app thread is not bound to an agent session")
    workspace = session.get(Workspace, app_thread.workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="workspace not found")
    if not workspace.enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="workspace is disabled")
    if workspace.device_id != app_thread.device_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="workspace device mismatch")
    device = session.get(Device, app_thread.device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="device not found")
    if device.status == DeviceStatus.DISABLED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="device is disabled")
    if device.status != DeviceStatus.ONLINE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="device is offline")
    active_turn = _get_active_app_turn(session, app_thread.id)
    if active_turn is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "app_turn_conflict",
                "message": "app thread already has a pending or running app turn",
                "app_turn_id": active_turn.id,
            },
        )

    app_turn = AppTurn(
        app_thread_id=app_thread.id,
        user_message=message,
        status=APP_TURN_PENDING,
        created_at=utc_now(),
    )
    session.add(app_turn)
    session.commit()
    session.refresh(app_turn)
    if app_turn.id is None:
        raise ValueError("app turn id is required")

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
            "codex_thread_id": app_thread.app_thread_id,
            "workspace_id": workspace.id,
            "workspace_key": workspace.workspace_key,
            "generation": app_thread.generation,
            "message": message,
            "sandbox": app_thread.sandbox,
            "approval_policy": app_thread.approval_policy,
            "network_access": app_thread.network_access,
        },
    )
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
    statement = (
        select(AppTurn)
        .where(AppTurn.app_thread_id == app_thread_id)
        .order_by(AppTurn.id)
        .limit(limit)
    )
    if normalized_status is not None:
        statement = (
            select(AppTurn)
            .where(AppTurn.app_thread_id == app_thread_id, AppTurn.status == normalized_status)
            .order_by(AppTurn.id)
            .limit(limit)
        )
    return list(session.exec(statement).all())


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
        app_thread.status = APP_THREAD_ERROR
        app_thread.last_error = STALE_TURN_ERROR
        app_thread.updated_at = now
        session.add(app_thread)
    session.commit()
    return {
        "recovered_count": len(recovered_turn_ids),
        "recovered_turn_ids": recovered_turn_ids,
    }


def get_app_turn_or_404(session: Session, app_turn_id: int) -> AppTurn:
    app_turn = session.get(AppTurn, app_turn_id)
    if app_turn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="app turn not found")
    return app_turn


def cancel_app_turn(session: Session, app_turn_id: int) -> AppTurn:
    app_turn = get_app_turn_or_404(session, app_turn_id)
    if app_turn.status in {APP_TURN_SUCCESS, APP_TURN_FAILED, APP_TURN_CANCELLED}:
        return app_turn

    # Local cancellation only: this marks backend state and does not guarantee
    # interruption of an already-running Codex App Server turn.
    app_turn.status = APP_TURN_CANCELLED
    app_turn.error_message = "cancelled by user"
    app_turn.completed_at = utc_now()

    app_thread = session.get(AppThread, app_turn.app_thread_id)
    if app_thread is not None:
        latest_active_turn = _get_active_app_turn(session, app_thread.id)
        if latest_active_turn is None or latest_active_turn.id == app_turn.id:
            app_thread.status = APP_THREAD_ACTIVE
            app_thread.last_error = None
            app_thread.updated_at = app_turn.completed_at
            session.add(app_thread)

    session.add(app_turn)
    session.commit()
    session.refresh(app_turn)
    return app_turn


def get_app_thread_final(session: Session, app_thread_id: int) -> AppThreadFinalRead:
    get_app_thread_or_404(session, app_thread_id)
    latest_turn = _latest_success_turn(session, app_thread_id)
    return AppThreadFinalRead(
        app_thread_id=app_thread_id,
        assistant_final=latest_turn.assistant_final if latest_turn else None,
    )


def get_app_thread_events(session: Session, app_thread_id: int) -> AppThreadEventsRead:
    get_app_thread_or_404(session, app_thread_id)
    latest_turn = session.exec(
        select(AppTurn)
        .where(
            AppTurn.app_thread_id == app_thread_id,
            AppTurn.event_summary_json.is_not(None),
        )
        .order_by(AppTurn.id.desc())
    ).first()
    return AppThreadEventsRead(
        app_thread_id=app_thread_id,
        latest_turn_id=latest_turn.id if latest_turn else None,
        event_summary=_event_summary_from_json(latest_turn.event_summary_json) if latest_turn else None,
    )


def get_app_turn_stream_snapshot(
    session: Session,
    app_turn_id: int,
    since: int = 0,
    bridge_client: AppServerBridgeClient | None = None,
) -> dict[str, Any]:
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
        return {
            "next_index": next_sequence,
            "events": events,
            "terminal": terminal,
        }
    if since > 0:
        terminal_event = _terminal_stream_event(app_turn, since + 1)
        if terminal_event is not None:
            return {
                "next_index": since + 1,
                "events": [terminal_event],
                "terminal": True,
            }
        return {
            "next_index": since,
            "events": [],
            "terminal": False,
        }

    app_thread = get_app_thread_or_404(session, app_turn.app_thread_id)
    if not app_thread.bridge_thread_id:
        return {
            "next_index": since,
            "events": [
                {
                    "kind": "error",
                    "turn_id": app_turn.id,
                    "message": "app thread has no bridge thread id",
                }
            ],
            "terminal": True,
        }

    events: list[dict[str, Any]] = [
        {
            "kind": "status",
            "turn_id": app_turn.id,
            "status": app_turn.status,
        }
    ]
    next_index = since

    if app_turn.status in {APP_TURN_PENDING, APP_TURN_RUNNING}:
        client = bridge_client or get_default_client()
        try:
            live_payload = client.get_live_events(app_thread.bridge_thread_id, since=since)
            next_index = _int_or_default(live_payload.get("next_index"), since)
            active_bridge_turn_id = _string_or_none(live_payload.get("active_turn_id"))
            if active_bridge_turn_id:
                events.extend(
                    _stream_events_from_bridge_events(
                        app_turn.id,
                        _list_or_empty(live_payload.get("events")),
                        active_bridge_turn_id,
                    )
                )
        except AppServerBridgeError as exc:
            events.append(
                {
                    "kind": "error",
                    "turn_id": app_turn.id,
                    "message": exc.message,
                }
            )

    if app_turn.status == APP_TURN_SUCCESS:
        events.append(
            {
                "kind": "final",
                "turn_id": app_turn.id,
                "status": app_turn.status,
                "turn": to_app_turn_read(app_turn).model_dump(mode="json"),
            }
        )
    elif app_turn.status in {APP_TURN_FAILED, APP_TURN_CANCELLED}:
        events.append(
            {
                "kind": "error",
                "turn_id": app_turn.id,
                "status": app_turn.status,
                "message": app_turn.error_message or app_turn.status,
                "turn": to_app_turn_read(app_turn).model_dump(mode="json"),
            }
        )

    return {
        "next_index": next_index,
        "events": events,
        "terminal": app_turn.status in {APP_TURN_SUCCESS, APP_TURN_FAILED, APP_TURN_CANCELLED},
    }


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
        return {
            "kind": "status",
            "turn_id": turn_id,
            "sequence": sequence,
            "status": _string_or_none(payload.get("status")) or "RUNNING",
        }
    if kind == "final":
        return {
            "kind": "final",
            "turn_id": turn_id,
            "sequence": sequence,
            "assistant_final": _string_or_none(payload.get("assistant_final"))
            or _string_or_none(payload.get("assistant_final_preview")),
            "event": payload,
        }

    delta = _extract_persisted_assistant_delta(payload)
    if delta:
        return {
            "kind": "assistant_delta",
            "turn_id": turn_id,
            "sequence": sequence,
            "text": delta,
            "event": payload,
        }
    if "error" in kind.lower() or payload.get("error"):
        return {
            "kind": "error",
            "turn_id": turn_id,
            "sequence": sequence,
            "message": _string_or_none(payload.get("message")) or _string_or_default(payload.get("error"), kind),
            "event": payload,
        }
    return {
        "kind": "event",
        "turn_id": turn_id,
        "sequence": sequence,
        "event_kind": kind,
        "event": payload,
    }


def _terminal_stream_event(app_turn: AppTurn, sequence: int) -> dict[str, Any] | None:
    if app_turn.status == APP_TURN_SUCCESS:
        return {
            "kind": "final",
            "turn_id": app_turn.id,
            "sequence": sequence,
            "status": app_turn.status,
            "turn": to_app_turn_read(app_turn).model_dump(mode="json"),
        }
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


def to_app_thread_read(session: Session, app_thread: AppThread) -> AppThreadRead:
    if app_thread.id is None:
        raise ValueError("app thread id is required")
    latest_turn = _latest_success_turn(session, app_thread.id)
    turn_count = len(
        session.exec(
            select(AppTurn).where(AppTurn.app_thread_id == app_thread.id)
        ).all()
    )
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
        bridge_thread_id=app_thread.bridge_thread_id,
        app_thread_id=app_thread.app_thread_id,
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
        bridge_turn_id=app_turn.bridge_turn_id,
        created_at=app_turn.created_at,
        started_at=app_turn.started_at,
        completed_at=app_turn.completed_at,
        duration_seconds=duration_seconds,
        event_summary=_event_summary_from_json(app_turn.event_summary_json),
    )


def _bridge_http_exception(exc: AppServerBridgeError) -> HTTPException:
    if exc.code == "timeout":
        status_code = status.HTTP_504_GATEWAY_TIMEOUT
    elif exc.status_code == status.HTTP_504_GATEWAY_TIMEOUT:
        status_code = status.HTTP_504_GATEWAY_TIMEOUT
    elif exc.status_code in {status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND, status.HTTP_409_CONFLICT}:
        status_code = exc.status_code
    elif exc.status_code is None:
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        status_code = status.HTTP_502_BAD_GATEWAY
    return HTTPException(
        status_code=status_code,
        detail={
            "code": exc.code,
            "message": exc.message,
            "step": exc.step,
        },
    )


def _require_bridge_thread_id(payload: dict[str, Any]) -> str:
    bridge_thread_id = _string_or_none(payload.get("bridge_thread_id"))
    if bridge_thread_id:
        return bridge_thread_id
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail={
            "code": "invalid_bridge_response",
            "message": "Bridge response missing bridge_thread_id",
            "step": "create_thread",
        },
    )


def _mark_turn_failed(
    session: Session,
    app_thread: AppThread,
    app_turn: AppTurn,
    message: str,
) -> None:
    now = utc_now()
    app_turn.status = APP_TURN_FAILED
    app_turn.error_message = message
    app_turn.completed_at = now
    app_thread.status = APP_THREAD_ERROR
    app_thread.last_error = message
    app_thread.updated_at = now
    session.add(app_thread)
    session.add(app_turn)
    session.commit()


def _latest_success_turn(session: Session, app_thread_id: int) -> AppTurn | None:
    return session.exec(
        select(AppTurn)
        .where(AppTurn.app_thread_id == app_thread_id, AppTurn.status == APP_TURN_SUCCESS)
        .order_by(AppTurn.id.desc())
    ).first()


def _get_active_app_turn(session: Session, app_thread_id: int) -> AppTurn | None:
    return session.exec(
        select(AppTurn)
        .where(
            AppTurn.app_thread_id == app_thread_id,
            AppTurn.status.in_([APP_TURN_PENDING, APP_TURN_RUNNING]),
        )
        .order_by(AppTurn.id)
    ).first()


def _best_effort_events(client: AppServerBridgeClient, bridge_thread_id: str) -> dict[str, Any] | None:
    try:
        return client.get_events(bridge_thread_id)
    except AppServerBridgeError:
        return None


def _bridge_final(client: AppServerBridgeClient, bridge_thread_id: str) -> str | None:
    try:
        return _string_or_none(client.get_final(bridge_thread_id).get("assistant_final"))
    except AppServerBridgeError:
        return None


def _summary_json(events_result: dict[str, Any] | None) -> str | None:
    normalized = normalize_event_summary(events_result)
    if normalized is None:
        return None
    return json.dumps(normalized, ensure_ascii=False)


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
        summary.get("event_type_counts")
        or summary.get("event_counts")
        or summary.get("type_counts")
    )
    errors = _list_or_empty(summary.get("errors"))
    has_error = _bool_or_default(summary.get("has_error"), bool(errors))
    assistant_preview = _string_or_default(
        summary.get("assistant_text_preview")
        or summary.get("assistant_final_preview")
        or summary.get("assistant_preview")
        or _extract_text_preview(summary)
    )
    assistant_length = _int_or_default(summary.get("assistant_text_length"), len(assistant_preview))
    return {
        "total_events": _int_or_default(summary.get("total_events"), 0),
        "event_type_counts": event_type_counts,
        "has_error": has_error,
        "errors": errors,
        "assistant_text_length": assistant_length,
        "assistant_text_preview": assistant_preview,
        "raw": summary,
    }


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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid {field_name}: {value}",
        )
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


def _stream_events_from_bridge_events(
    app_turn_id: int,
    bridge_events: list[Any],
    bridge_turn_id: str,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for bridge_event in bridge_events:
        if not isinstance(bridge_event, dict):
            continue
        if _bridge_event_turn_id(bridge_event) != bridge_turn_id:
            continue
        for delta in _extract_assistant_deltas(bridge_event):
            events.append(
                {
                    "kind": "assistant_delta",
                    "turn_id": app_turn_id,
                    "text": delta,
                }
            )
    return events


def _extract_assistant_deltas(event: dict[str, Any]) -> list[str]:
    event_name = _event_name(event)
    deltas: list[str] = []
    if not _looks_like_assistant_event(event_name):
        return deltas
    for container in _event_containers(event):
        delta = container.get("delta")
        if isinstance(delta, str) and delta:
            deltas.append(delta)
    return deltas


def _event_name(event: dict[str, Any]) -> str:
    for key in ("method", "type", "event"):
        value = event.get(key)
        if isinstance(value, str):
            return value
    if "id" in event and ("result" in event or "error" in event):
        return "response"
    return "unknown"


def _looks_like_assistant_event(event_name: str) -> bool:
    normalized = event_name.replace("-", "_").replace("/", "_").lower()
    return "assistant" in normalized or "agent_message" in normalized or "agentmessage" in normalized


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


def _bridge_event_turn_id(event: dict[str, Any]) -> str | None:
    result = event.get("result")
    if isinstance(result, dict):
        turn = result.get("turn")
        if isinstance(turn, dict) and isinstance(turn.get("id"), str):
            return turn["id"]
        if isinstance(result.get("turnId"), str):
            return result["turnId"]

    params = event.get("params")
    if isinstance(params, dict):
        if isinstance(params.get("turnId"), str):
            return params["turnId"]
        turn = params.get("turn")
        if isinstance(turn, dict) and isinstance(turn.get("id"), str):
            return turn["id"]
    return None


def _clean_title(value: str | None) -> str:
    return str(value or "").strip()


def _default_title() -> str:
    timestamp = datetime.now().strftime("%H%M%S")
    return f"App Thread {timestamp}"


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
