from __future__ import annotations

from collections.abc import Generator

from sqlmodel import SQLModel, Session, create_engine, select
from sqlmodel.pool import StaticPool

from backend.models import AppThread, AppTurn, Project, utc_now
from backend.services import app_thread_service


def make_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()


def add_thread(session: Session) -> AppThread:
    project = Project(
        name="demo",
        path="E:\\demo",
        enabled=True,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    app_thread = AppThread(
        project_id=project.id,
        title="Chat",
        bridge_thread_id="bridge-1",
        app_thread_id="app-1",
        status="ACTIVE",
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(app_thread)
    session.commit()
    session.refresh(app_thread)
    return app_thread


def add_turn(session: Session, app_thread_id: int, status: str) -> AppTurn:
    app_turn = AppTurn(
        app_thread_id=app_thread_id,
        user_message=f"{status.lower()} message",
        status=status,
        created_at=utc_now(),
        started_at=utc_now() if status == "RUNNING" else None,
        completed_at=utc_now() if status in {"SUCCESS", "FAILED", "CANCELLED"} else None,
    )
    session.add(app_turn)
    session.commit()
    session.refresh(app_turn)
    return app_turn


def test_recover_stale_app_turns_marks_pending_and_running_failed() -> None:
    for session in make_session():
        pending_thread = add_thread(session)
        running_thread = add_thread(session)
        pending = add_turn(session, pending_thread.id, "PENDING")
        running = add_turn(session, running_thread.id, "RUNNING")

        result = app_thread_service.recover_stale_app_turns(session)

        session.refresh(pending_thread)
        session.refresh(running_thread)
        session.refresh(pending)
        session.refresh(running)
        assert result["recovered_count"] == 2
        assert result["recovered_turn_ids"] == [pending.id, running.id]
        assert pending.status == "FAILED"
        assert pending.started_at is None
        assert pending.error_message == app_thread_service.STALE_TURN_ERROR
        assert pending.completed_at is not None
        assert running.status == "FAILED"
        assert running.started_at is not None
        assert running.error_message == app_thread_service.STALE_TURN_ERROR
        assert pending_thread.status == "ERROR"
        assert pending_thread.last_error == app_thread_service.STALE_TURN_ERROR
        assert running_thread.status == "ERROR"
        assert running_thread.last_error == app_thread_service.STALE_TURN_ERROR


def test_recover_stale_app_turns_ignores_terminal_turns_and_is_idempotent() -> None:
    for session in make_session():
        app_thread = add_thread(session)
        terminal_turns = [
            add_turn(session, app_thread.id, "SUCCESS"),
            add_turn(session, app_thread.id, "FAILED"),
            add_turn(session, app_thread.id, "CANCELLED"),
        ]

        first = app_thread_service.recover_stale_app_turns(session)
        second = app_thread_service.recover_stale_app_turns(session)

        assert first == {"recovered_count": 0, "recovered_turn_ids": []}
        assert second == {"recovered_count": 0, "recovered_turn_ids": []}
        assert [turn.status for turn in session.exec(select(AppTurn)).all()] == [
            turn.status for turn in terminal_turns
        ]
