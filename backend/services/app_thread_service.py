from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlmodel import Session, select

from backend.models import AppThread, AppTurn, Project, utc_now
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


APP_THREAD_CREATED = "CREATED"
APP_THREAD_ACTIVE = "ACTIVE"
APP_THREAD_ERROR = "ERROR"
APP_THREAD_CLOSED = "CLOSED"

APP_TURN_RUNNING = "RUNNING"
APP_TURN_SUCCESS = "SUCCESS"
APP_TURN_FAILED = "FAILED"


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
    client = bridge_client or get_default_client()
    try:
        bridge_thread = client.create_thread(title)
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


def list_app_threads(
    session: Session,
    project_id: int | None = None,
    limit: int = 50,
) -> list[AppThread]:
    statement = select(AppThread)
    if project_id is not None:
        statement = statement.where(AppThread.project_id == project_id)
    statement = statement.order_by(AppThread.id.desc()).limit(limit)
    return list(session.exec(statement).all())


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


def list_app_turns(session: Session, app_thread_id: int) -> list[AppTurn]:
    get_app_thread_or_404(session, app_thread_id)
    return list(
        session.exec(
            select(AppTurn)
            .where(AppTurn.app_thread_id == app_thread_id)
            .order_by(AppTurn.id)
        ).all()
    )


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
        .where(AppTurn.app_thread_id == app_thread_id)
        .order_by(AppTurn.id.desc())
    ).first()
    event_summary = None
    if latest_turn and latest_turn.event_summary_json:
        try:
            event_summary = json.loads(latest_turn.event_summary_json)
        except json.JSONDecodeError:
            event_summary = {"invalid_summary": latest_turn.event_summary_json}
    return AppThreadEventsRead(
        app_thread_id=app_thread_id,
        latest_turn_id=latest_turn.id if latest_turn else None,
        event_summary=event_summary,
    )


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
    return AppTurnRead(
        id=app_turn.id,
        app_thread_id=app_turn.app_thread_id,
        user_message=app_turn.user_message,
        assistant_final=app_turn.assistant_final,
        status=app_turn.status,
        error_message=app_turn.error_message,
        bridge_turn_id=app_turn.bridge_turn_id,
        created_at=app_turn.created_at,
        started_at=app_turn.started_at,
        completed_at=app_turn.completed_at,
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
    if not events_result:
        return None
    summary = events_result.get("summary")
    if summary is None:
        summary = events_result
    return json.dumps(summary, ensure_ascii=False)


def _clean_title(value: str | None) -> str:
    return str(value or "").strip()


def _default_title() -> str:
    timestamp = datetime.now().strftime("%H%M%S")
    return f"App Thread {timestamp}"


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
