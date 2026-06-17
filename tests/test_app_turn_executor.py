from __future__ import annotations

from collections.abc import Generator
from typing import Any

from sqlmodel import SQLModel, Session, create_engine, select
from sqlmodel.pool import StaticPool

from backend.models import AppThread, AppTurn, Project, utc_now
from backend.services import app_turn_executor
from backend.services.app_server_bridge_client import AppServerBridgeError


class FakeBridgeClient:
    def __init__(self) -> None:
        self.fail_send = False

    def send_turn(self, bridge_thread_id: str, message: str) -> dict[str, Any]:
        if self.fail_send:
            raise AppServerBridgeError(504, "turn_timeout", "timeout", "turn/completed")
        return {
            "turn_id": "turn-1",
            "assistant_final_preview": f"preview:{message}:{bridge_thread_id}",
        }

    def get_events(self, bridge_thread_id: str) -> dict[str, Any]:
        return {"summary": {"total_events": 2, "bridge_thread_id": bridge_thread_id}}

    def get_final(self, bridge_thread_id: str) -> dict[str, Any]:
        return {"assistant_final": "full assistant final"}


def make_session() -> Generator[tuple[Session, Any], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    try:
        yield session, engine
    finally:
        session.close()


def add_thread_and_turn(session: Session, *, thread_status: str = "ACTIVE") -> tuple[AppThread, AppTurn]:
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
        status=thread_status,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(app_thread)
    session.commit()
    session.refresh(app_thread)
    app_turn = AppTurn(
        app_thread_id=app_thread.id,
        user_message="hello",
        status="PENDING",
        created_at=utc_now(),
    )
    session.add(app_turn)
    session.commit()
    session.refresh(app_turn)
    return app_thread, app_turn


def test_execute_app_turn_once_success(monkeypatch) -> None:
    for session, engine in make_session():
        fake = FakeBridgeClient()
        monkeypatch.setattr(app_turn_executor, "engine", engine)
        monkeypatch.setattr(app_turn_executor, "get_default_client", lambda: fake)
        app_thread, app_turn = add_thread_and_turn(session)

        app_turn_executor.execute_app_turn_once(app_turn.id)

        session.refresh(app_thread)
        session.refresh(app_turn)
        assert app_turn.status == "SUCCESS"
        assert app_turn.assistant_final == "full assistant final"
        assert app_turn.bridge_turn_id == "turn-1"
        assert app_turn.event_summary_json is not None
        assert app_turn.started_at is not None
        assert app_turn.completed_at is not None
        assert app_thread.status == "ACTIVE"
        assert app_thread.last_error is None


def test_execute_app_turn_once_send_failure_marks_error(monkeypatch) -> None:
    for session, engine in make_session():
        fake = FakeBridgeClient()
        fake.fail_send = True
        monkeypatch.setattr(app_turn_executor, "engine", engine)
        monkeypatch.setattr(app_turn_executor, "get_default_client", lambda: fake)
        app_thread, app_turn = add_thread_and_turn(session)

        app_turn_executor.execute_app_turn_once(app_turn.id)

        session.refresh(app_thread)
        session.refresh(app_turn)
        assert app_turn.status == "FAILED"
        assert app_turn.error_message == "timeout"
        assert app_turn.completed_at is not None
        assert app_thread.status == "ERROR"
        assert app_thread.last_error == "timeout"


def test_execute_app_turn_once_closed_thread_marks_failed(monkeypatch) -> None:
    for session, engine in make_session():
        monkeypatch.setattr(app_turn_executor, "engine", engine)
        app_thread, app_turn = add_thread_and_turn(session, thread_status="CLOSED")

        app_turn_executor.execute_app_turn_once(app_turn.id)

        session.refresh(app_thread)
        session.refresh(app_turn)
        assert app_turn.status == "FAILED"
        assert app_turn.error_message == "app thread is closed"
        assert app_thread.status == "ERROR"


def test_execute_app_turn_once_missing_turn_does_not_crash(monkeypatch) -> None:
    for session, engine in make_session():
        monkeypatch.setattr(app_turn_executor, "engine", engine)

        app_turn_executor.execute_app_turn_once(404)

        assert session.exec(select(AppTurn)).all() == []
