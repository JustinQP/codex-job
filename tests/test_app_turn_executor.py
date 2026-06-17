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
        self.send_calls = 0

    def send_turn(self, bridge_thread_id: str, message: str) -> dict[str, Any]:
        self.send_calls += 1
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
        monkeypatch.setattr(app_turn_executor, "_build_bridge_client", lambda: fake)
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
        monkeypatch.setattr(app_turn_executor, "_build_bridge_client", lambda: fake)
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


def test_execute_app_turn_once_cancelled_before_start_does_not_call_bridge(monkeypatch) -> None:
    for session, engine in make_session():
        fake = FakeBridgeClient()
        monkeypatch.setattr(app_turn_executor, "engine", engine)
        monkeypatch.setattr(app_turn_executor, "_build_bridge_client", lambda: fake)
        _app_thread, app_turn = add_thread_and_turn(session)
        app_turn.status = "CANCELLED"
        app_turn.error_message = "cancelled by user"
        session.add(app_turn)
        session.commit()

        app_turn_executor.execute_app_turn_once(app_turn.id)

        session.refresh(app_turn)
        assert fake.send_calls == 0
        assert app_turn.status == "CANCELLED"


def test_execute_app_turn_once_cancelled_after_send_does_not_overwrite_success(monkeypatch) -> None:
    for session, engine in make_session():
        fake = FakeBridgeClient()
        monkeypatch.setattr(app_turn_executor, "engine", engine)
        monkeypatch.setattr(app_turn_executor, "_build_bridge_client", lambda: fake)
        _app_thread, app_turn = add_thread_and_turn(session)

        original_send_turn = fake.send_turn

        def cancel_after_send(bridge_thread_id: str, message: str) -> dict[str, Any]:
            result = original_send_turn(bridge_thread_id, message)
            with Session(engine) as other_session:
                current_turn = other_session.get(AppTurn, app_turn.id)
                current_turn.status = "CANCELLED"
                current_turn.error_message = "cancelled by user"
                current_turn.completed_at = utc_now()
                other_session.add(current_turn)
                other_session.commit()
            return result

        fake.send_turn = cancel_after_send

        app_turn_executor.execute_app_turn_once(app_turn.id)

        session.refresh(app_turn)
        assert fake.send_calls == 1
        assert app_turn.status == "CANCELLED"
        assert app_turn.assistant_final is None


def test_execute_app_turn_once_cancelled_after_timeout_does_not_overwrite_cancelled(monkeypatch) -> None:
    for session, engine in make_session():
        fake = FakeBridgeClient()
        fake.fail_send = True
        monkeypatch.setattr(app_turn_executor, "engine", engine)
        monkeypatch.setattr(app_turn_executor, "_build_bridge_client", lambda: fake)
        _app_thread, app_turn = add_thread_and_turn(session)

        original_send_turn = fake.send_turn

        def cancel_then_timeout(bridge_thread_id: str, message: str) -> dict[str, Any]:
            with Session(engine) as other_session:
                current_turn = other_session.get(AppTurn, app_turn.id)
                current_turn.status = "CANCELLED"
                current_turn.error_message = "cancelled by user"
                current_turn.completed_at = utc_now()
                other_session.add(current_turn)
                other_session.commit()
            return original_send_turn(bridge_thread_id, message)

        fake.send_turn = cancel_then_timeout

        app_turn_executor.execute_app_turn_once(app_turn.id)

        session.refresh(app_turn)
        assert app_turn.status == "CANCELLED"
        assert app_turn.error_message == "cancelled by user"


def test_execute_app_turn_once_timeout_marks_failed(monkeypatch) -> None:
    for session, engine in make_session():
        fake = FakeBridgeClient()
        fake.fail_send = True
        monkeypatch.setattr(app_turn_executor, "engine", engine)
        monkeypatch.setattr(app_turn_executor, "_build_bridge_client", lambda: fake)
        app_thread, app_turn = add_thread_and_turn(session)

        app_turn_executor.execute_app_turn_once(app_turn.id)

        session.refresh(app_thread)
        session.refresh(app_turn)
        assert app_turn.status == "FAILED"
        assert "timeout" in app_turn.error_message
        assert app_thread.status == "ERROR"


def test_execution_timeout_seconds_invalid_falls_back(monkeypatch) -> None:
    monkeypatch.setenv("APP_TURN_EXECUTION_TIMEOUT_SECONDS", "invalid")

    assert app_turn_executor._execution_timeout_seconds() == 600.0


def test_build_bridge_client_uses_execution_timeout(monkeypatch) -> None:
    captured: dict[str, float] = {}

    class CapturingClient:
        def __init__(self, timeout_seconds: float) -> None:
            captured["timeout_seconds"] = timeout_seconds

    monkeypatch.setenv("APP_TURN_EXECUTION_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setattr(app_turn_executor, "AppServerBridgeClient", CapturingClient)

    app_turn_executor._build_bridge_client()

    assert captured["timeout_seconds"] == 12.5
