from __future__ import annotations

import os
import traceback
from concurrent.futures import ThreadPoolExecutor

from sqlmodel import Session

from backend.db import engine
from backend.models import AppThread, AppTurn, utc_now
from backend.services import app_thread_service
from backend.services.app_server_bridge_client import AppServerBridgeClient, AppServerBridgeError


def _max_workers() -> int:
    raw_value = os.environ.get("APP_TURN_EXECUTOR_MAX_WORKERS", "2")
    try:
        value = int(raw_value)
    except ValueError:
        return 2
    return max(1, value)


def _execution_timeout_seconds() -> float:
    raw_value = os.environ.get("APP_TURN_EXECUTION_TIMEOUT_SECONDS", "600")
    try:
        value = float(raw_value)
    except ValueError:
        return 600.0
    return max(0.1, value)


_executor = ThreadPoolExecutor(max_workers=_max_workers())


def submit_app_turn(app_turn_id: int) -> None:
    _executor.submit(execute_app_turn_once, app_turn_id)


def execute_app_turn_once(app_turn_id: int) -> None:
    try:
        with Session(engine) as session:
            _execute_with_session(session, app_turn_id)
    except Exception:
        # The executor must never let unhandled exceptions kill the worker
        # silently. If a DB session cannot be opened, stderr is the only
        # reliable fallback.
        traceback.print_exc()
        return


def _execute_with_session(session: Session, app_turn_id: int) -> None:
    app_turn = session.get(AppTurn, app_turn_id)
    if app_turn is None:
        return
    if app_turn.status == app_thread_service.APP_TURN_CANCELLED:
        return
    if app_turn.status not in {app_thread_service.APP_TURN_PENDING, app_thread_service.APP_TURN_RUNNING}:
        return

    app_thread = session.get(AppThread, app_turn.app_thread_id)
    if app_thread is None:
        _mark_failed(session, None, app_turn, "app thread not found")
        return
    if app_thread.status == app_thread_service.APP_THREAD_CLOSED:
        _mark_failed(session, app_thread, app_turn, "app thread is closed")
        return
    if not app_thread.bridge_thread_id:
        _mark_failed(session, app_thread, app_turn, "app thread has no bridge thread id")
        return

    now = utc_now()
    session.refresh(app_turn)
    if app_turn.status == app_thread_service.APP_TURN_CANCELLED:
        return
    app_turn.status = app_thread_service.APP_TURN_RUNNING
    if app_turn.started_at is None:
        app_turn.started_at = now
    session.add(app_turn)
    session.commit()
    session.refresh(app_turn)
    session.refresh(app_thread)

    client = _build_bridge_client()
    try:
        bridge_result = client.send_turn(app_thread.bridge_thread_id, app_turn.user_message)
        session.refresh(app_turn)
        if app_turn.status == app_thread_service.APP_TURN_CANCELLED:
            return
        events_result = _best_effort_events(client, app_thread.bridge_thread_id)
        full_final = _bridge_final(client, app_thread.bridge_thread_id)
        preview_final = _string_or_none(bridge_result.get("assistant_final_preview"))
    except AppServerBridgeError as exc:
        session.refresh(app_turn)
        if app_turn.status == app_thread_service.APP_TURN_CANCELLED:
            return
        _mark_failed(session, app_thread, app_turn, exc.message)
        return
    except Exception as exc:
        session.refresh(app_turn)
        if app_turn.status == app_thread_service.APP_TURN_CANCELLED:
            return
        _mark_failed(session, app_thread, app_turn, str(exc))
        return

    completed_at = utc_now()
    app_turn.status = app_thread_service.APP_TURN_SUCCESS
    app_turn.assistant_final = full_final or preview_final
    app_turn.bridge_turn_id = _string_or_none(bridge_result.get("turn_id"))
    app_turn.event_summary_json = _summary_json(events_result)
    app_turn.completed_at = completed_at
    app_thread.status = app_thread_service.APP_THREAD_ACTIVE
    app_thread.last_error = None
    app_thread.updated_at = completed_at
    session.add(app_thread)
    session.add(app_turn)
    session.commit()


def _mark_failed(
    session: Session,
    app_thread: AppThread | None,
    app_turn: AppTurn,
    message: str,
) -> None:
    now = utc_now()
    app_turn.status = app_thread_service.APP_TURN_FAILED
    app_turn.error_message = message
    if app_turn.started_at is None:
        app_turn.started_at = now
    app_turn.completed_at = now
    if app_thread is not None:
        app_thread.status = app_thread_service.APP_THREAD_ERROR
        app_thread.last_error = message
        app_thread.updated_at = now
        session.add(app_thread)
    session.add(app_turn)
    session.commit()


def _best_effort_events(client, bridge_thread_id: str) -> dict | None:
    try:
        return client.get_events(bridge_thread_id)
    except AppServerBridgeError:
        return None


def _build_bridge_client() -> AppServerBridgeClient:
    return AppServerBridgeClient(timeout_seconds=_execution_timeout_seconds())


def _bridge_final(client, bridge_thread_id: str) -> str | None:
    try:
        return _string_or_none(client.get_final(bridge_thread_id).get("assistant_final"))
    except AppServerBridgeError:
        return None


def _summary_json(events_result: dict | None) -> str | None:
    return app_thread_service._summary_json(events_result)


def _string_or_none(value) -> str | None:
    return value if isinstance(value, str) and value else None
