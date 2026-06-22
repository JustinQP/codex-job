from __future__ import annotations

import json
import time

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from backend.db import get_session
from backend.dependencies import require_api_token
from backend.schemas import (
    AppThreadCleanupRead,
    AppThreadCleanupRequest,
    AppThreadCreate,
    AppThreadEventsRead,
    AppThreadFinalRead,
    AppThreadRead,
    AppThreadUpdate,
    AppTurnCreate,
    AppTurnRead,
    AppTurnRecoveryRead,
)
from backend.services import app_thread_service


router = APIRouter()


@router.get("/app-threads", response_model=list[AppThreadRead])
def list_app_threads(
    project_id: int | None = None,
    status: str | None = None,
    include_archived: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return [
        app_thread_service.to_app_thread_read(session, app_thread)
        for app_thread in app_thread_service.list_app_threads(
            session,
            project_id=project_id,
            status_filter=status,
            limit=limit,
            include_archived=include_archived,
        )
    ]


@router.post("/app-threads", response_model=AppThreadRead)
def create_app_thread(
    payload: AppThreadCreate,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    app_thread = app_thread_service.create_app_thread(session, payload)
    return app_thread_service.to_app_thread_read(session, app_thread)


@router.post("/app-threads/cleanup", response_model=AppThreadCleanupRead)
def cleanup_app_threads(
    payload: AppThreadCleanupRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return app_thread_service.cleanup_app_threads(
        session,
        status_filter=payload.status,
        limit=payload.limit,
    )


@router.get("/app-threads/{app_thread_id}", response_model=AppThreadRead)
def get_app_thread(
    app_thread_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    app_thread = app_thread_service.get_app_thread_or_404(session, app_thread_id)
    return app_thread_service.to_app_thread_read(session, app_thread)


@router.patch("/app-threads/{app_thread_id}", response_model=AppThreadRead)
def rename_app_thread(
    app_thread_id: int,
    payload: AppThreadUpdate,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    app_thread = app_thread_service.rename_app_thread(session, app_thread_id, payload)
    return app_thread_service.to_app_thread_read(session, app_thread)


@router.delete("/app-threads/{app_thread_id}", response_model=AppThreadRead)
def close_app_thread(
    app_thread_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    app_thread = app_thread_service.close_app_thread(session, app_thread_id)
    return app_thread_service.to_app_thread_read(session, app_thread)


@router.post("/app-threads/{app_thread_id}/reopen", response_model=AppThreadRead)
def reopen_app_thread(
    app_thread_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    app_thread = app_thread_service.reopen_app_thread(session, app_thread_id)
    return app_thread_service.to_app_thread_read(session, app_thread)


@router.post("/app-threads/{app_thread_id}/turns", response_model=AppTurnRead)
def send_app_turn(
    app_thread_id: int,
    payload: AppTurnCreate,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    app_turn = app_thread_service.send_app_turn(session, app_thread_id, payload)
    return app_thread_service.to_app_turn_read(app_turn)


@router.post("/app-threads/{app_thread_id}/turns/async", response_model=AppTurnRead)
def create_async_app_turn(
    app_thread_id: int,
    payload: AppTurnCreate,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    app_turn = app_thread_service.create_async_app_turn(session, app_thread_id, payload)
    return app_thread_service.to_app_turn_read(app_turn)


@router.post("/app-turns/recover-stale", response_model=AppTurnRecoveryRead)
def recover_stale_app_turns(
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return app_thread_service.recover_stale_app_turns(session)


@router.get("/app-turns/{app_turn_id}", response_model=AppTurnRead)
def get_app_turn(
    app_turn_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    app_turn = app_thread_service.get_app_turn_or_404(session, app_turn_id)
    return app_thread_service.to_app_turn_read(app_turn)


@router.get("/app-turns/{app_turn_id}/stream")
def stream_app_turn(
    app_turn_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    app_thread_service.get_app_turn_or_404(session, app_turn_id)

    def event_generator():
        since = 0
        while True:
            session.expire_all()
            snapshot = app_thread_service.get_app_turn_stream_snapshot(
                session,
                app_turn_id,
                since=since,
            )
            since = int(snapshot.get("next_index") or since)
            for event in snapshot.get("events", []):
                yield _sse_event(event)
            if snapshot.get("terminal"):
                break
            time.sleep(0.8)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/app-turns/{app_turn_id}/cancel", response_model=AppTurnRead)
def cancel_app_turn(
    app_turn_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    app_turn = app_thread_service.cancel_app_turn(session, app_turn_id)
    return app_thread_service.to_app_turn_read(app_turn)


@router.get("/app-threads/{app_thread_id}/turns", response_model=list[AppTurnRead])
def list_app_turns(
    app_thread_id: int,
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return [
        app_thread_service.to_app_turn_read(app_turn)
        for app_turn in app_thread_service.list_app_turns(
            session,
            app_thread_id,
            status_filter=status,
            limit=limit,
        )
    ]


@router.get("/app-threads/{app_thread_id}/final", response_model=AppThreadFinalRead)
def get_app_thread_final(
    app_thread_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return app_thread_service.get_app_thread_final(session, app_thread_id)


@router.get("/app-threads/{app_thread_id}/events", response_model=AppThreadEventsRead)
def get_app_thread_events(
    app_thread_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return app_thread_service.get_app_thread_events(session, app_thread_id)


def _sse_event(payload: dict) -> str:
    event_name = str(payload.get("kind") or "message")
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event_name}\ndata: {data}\n\n"
