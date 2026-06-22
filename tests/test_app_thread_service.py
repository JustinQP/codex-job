from __future__ import annotations

from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Lock
from typing import Any

import pytest
from fastapi import HTTPException
from sqlmodel import SQLModel, Session, create_engine, select
from sqlmodel.pool import StaticPool

from backend.models import AgentCommand, AppThread, AppTurn, Project, utc_now
from backend.schemas import AppThreadCreate, AppThreadUpdate, AppTurnCreate
from backend.services.app_server_bridge_client import AppServerBridgeError
from backend.services import app_thread_service


class FakeBridgeClient:
    def __init__(self) -> None:
        self.created_titles: list[str] = []
        self.created_cwds: list[str | None] = []
        self.create_count = 0
        self.renamed: list[tuple[str, str]] = []
        self.deleted: list[str] = []
        self.fail_send = False
        self.fail_create = False
        self.fail_rename = False
        self.fail_final = False
        self.missing_bridge_thread_id = False
        self.preview_final = "short preview"
        self.full_final = "full assistant final"

    def create_thread(self, title: str, cwd: str | None = None) -> dict[str, Any]:
        if self.fail_create:
            raise AppServerBridgeError(None, "network_error", "bridge down", "request")
        self.created_titles.append(title)
        self.created_cwds.append(cwd)
        self.create_count += 1
        if self.missing_bridge_thread_id:
            return {
                "app_thread_id": "app-1",
                "title": title,
            }
        return {
            "bridge_thread_id": f"bridge-{self.create_count}",
            "app_thread_id": f"app-{self.create_count}",
            "title": title,
        }

    def rename_thread(self, bridge_thread_id: str, title: str) -> dict[str, Any]:
        if self.fail_rename:
            raise AppServerBridgeError(502, "rename_failed", "rename failed", "thread/patch")
        self.renamed.append((bridge_thread_id, title))
        return {"title": title}

    def delete_thread(self, bridge_thread_id: str) -> dict[str, Any]:
        self.deleted.append(bridge_thread_id)
        return {"closed": True}

    def send_turn(self, bridge_thread_id: str, message: str) -> dict[str, Any]:
        if self.fail_send:
            raise AppServerBridgeError(504, "turn_timeout", "timeout", "turn/completed")
        return {
            "turn_id": "turn-1",
            "assistant_final_preview": self.preview_final,
        }

    def get_events(self, bridge_thread_id: str) -> dict[str, Any]:
        return {"summary": {"total_events": 2, "bridge_thread_id": bridge_thread_id}}

    def get_live_events(self, bridge_thread_id: str, since: int = 0) -> dict[str, Any]:
        return {
            "next_index": since + 2,
            "active_turn_id": "turn-active",
            "events": [
                {
                    "method": "agent/message_delta",
                    "params": {"turnId": "turn-old", "delta": "old"},
                },
                {
                    "method": "agent/message_delta",
                    "params": {"turnId": "turn-active", "delta": "live"},
                },
            ],
        }

    def get_final(self, bridge_thread_id: str) -> dict[str, Any]:
        if self.fail_final:
            raise AppServerBridgeError(502, "final_failed", "final unavailable", "final")
        return {"assistant_final": self.full_final}


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


def add_project(session: Session, *, enabled: bool = True) -> Project:
    project = Project(
        name="demo",
        path="E:\\demo",
        enabled=enabled,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def test_create_app_thread_success() -> None:
    for session in make_session():
        project = add_project(session)
        fake = FakeBridgeClient()

        app_thread = app_thread_service.create_app_thread(
            session,
            AppThreadCreate(project_id=project.id, title="Chat"),
            fake,
        )

        assert app_thread.id is not None
        assert app_thread.title == "Chat"
        assert app_thread.status == "ACTIVE"
        assert app_thread.bridge_thread_id == "bridge-1"
        assert fake.created_titles == ["Chat"]
        assert fake.created_cwds == [project.path]


def test_create_app_thread_rejects_missing_or_disabled_project() -> None:
    for session in make_session():
        disabled = add_project(session, enabled=False)
        fake = FakeBridgeClient()

        with pytest.raises(HTTPException) as missing:
            app_thread_service.create_app_thread(session, AppThreadCreate(project_id=404), fake)
        with pytest.raises(HTTPException) as disabled_error:
            app_thread_service.create_app_thread(session, AppThreadCreate(project_id=disabled.id), fake)

        assert missing.value.status_code == 404
        assert disabled_error.value.status_code == 400


def test_create_app_thread_bridge_failure_does_not_persist_thread() -> None:
    for session in make_session():
        project = add_project(session)
        fake = FakeBridgeClient()
        fake.fail_create = True

        with pytest.raises(HTTPException) as exc:
            app_thread_service.create_app_thread(session, AppThreadCreate(project_id=project.id), fake)

        assert exc.value.status_code == 503
        assert session.exec(select(AppThread)).all() == []


def test_create_app_thread_rejects_missing_bridge_thread_id() -> None:
    for session in make_session():
        project = add_project(session)
        fake = FakeBridgeClient()
        fake.missing_bridge_thread_id = True

        with pytest.raises(HTTPException) as exc:
            app_thread_service.create_app_thread(
                session,
                AppThreadCreate(project_id=project.id, title="Chat"),
                fake,
            )

        assert exc.value.status_code == 502
        assert exc.value.detail["code"] == "invalid_bridge_response"
        assert exc.value.detail["message"] == "Bridge response missing bridge_thread_id"
        assert exc.value.detail["step"] == "create_thread"
        assert session.exec(select(AppThread)).all() == []


def test_send_app_turn_success_persists_turn_and_summary() -> None:
    for session in make_session():
        project = add_project(session)
        fake = FakeBridgeClient()
        app_thread = app_thread_service.create_app_thread(
            session,
            AppThreadCreate(project_id=project.id, title="Chat"),
            fake,
        )

        app_turn = app_thread_service.send_app_turn(
            session,
            app_thread.id,
            AppTurnCreate(message="hello"),
            fake,
        )
        final = app_thread_service.get_app_thread_final(session, app_thread.id)
        events = app_thread_service.get_app_thread_events(session, app_thread.id)

        assert app_turn.status == "SUCCESS"
        assert app_turn.assistant_final == "full assistant final"
        assert app_turn.bridge_turn_id == "turn-1"
        assert app_turn.completed_at is not None
        assert final.assistant_final == "full assistant final"
        assert events.latest_turn_id == app_turn.id
        assert events.event_summary["total_events"] == 2
        assert events.event_summary["event_type_counts"] == {}
        assert events.event_summary["has_error"] is False
        assert events.event_summary["raw"]["bridge_thread_id"] == "bridge-1"


def test_to_app_thread_read_returns_latest_final_and_turn_count() -> None:
    for session in make_session():
        project = add_project(session)
        fake = FakeBridgeClient()
        app_thread = app_thread_service.create_app_thread(
            session,
            AppThreadCreate(project_id=project.id, title="Chat"),
            fake,
        )

        initial_read = app_thread_service.to_app_thread_read(session, app_thread)
        app_thread_service.send_app_turn(
            session,
            app_thread.id,
            AppTurnCreate(message="hello"),
            fake,
        )
        updated_read = app_thread_service.to_app_thread_read(session, app_thread)

        assert initial_read.turn_count == 0
        assert initial_read.latest_assistant_final is None
        assert updated_read.turn_count == 1
        assert updated_read.latest_assistant_final == "full assistant final"


def test_send_app_turn_prefers_full_final_over_preview() -> None:
    for session in make_session():
        project = add_project(session)
        fake = FakeBridgeClient()
        fake.preview_final = "short preview"
        fake.full_final = "full assistant final"
        app_thread = app_thread_service.create_app_thread(
            session,
            AppThreadCreate(project_id=project.id),
            fake,
        )

        app_turn = app_thread_service.send_app_turn(
            session,
            app_thread.id,
            AppTurnCreate(message="hello"),
            fake,
        )
        final = app_thread_service.get_app_thread_final(session, app_thread.id)

        assert app_turn.assistant_final == "full assistant final"
        assert final.assistant_final == "full assistant final"


def test_send_app_turn_falls_back_to_preview_when_final_unavailable() -> None:
    for session in make_session():
        project = add_project(session)
        fake = FakeBridgeClient()
        fake.preview_final = "short preview"
        fake.fail_final = True
        app_thread = app_thread_service.create_app_thread(
            session,
            AppThreadCreate(project_id=project.id),
            fake,
        )

        app_turn = app_thread_service.send_app_turn(
            session,
            app_thread.id,
            AppTurnCreate(message="hello"),
            fake,
        )

        assert app_turn.status == "SUCCESS"
        assert app_turn.assistant_final == "short preview"


def test_send_app_turn_failure_marks_turn_failed_and_thread_error() -> None:
    for session in make_session():
        project = add_project(session)
        fake = FakeBridgeClient()
        app_thread = app_thread_service.create_app_thread(
            session,
            AppThreadCreate(project_id=project.id),
            fake,
        )
        fake.fail_send = True

        with pytest.raises(HTTPException) as exc:
            app_thread_service.send_app_turn(
                session,
                app_thread.id,
                AppTurnCreate(message="hello"),
                fake,
            )

        session.refresh(app_thread)
        failed_turn = session.exec(select(AppTurn)).one()
        assert exc.value.status_code == 504
        assert failed_turn.status == "FAILED"
        assert failed_turn.error_message == "timeout"
        assert app_thread.status == "ERROR"
        assert app_thread.last_error == "timeout"


def test_close_app_thread_marks_closed() -> None:
    for session in make_session():
        project = add_project(session)
        fake = FakeBridgeClient()
        app_thread = app_thread_service.create_app_thread(
            session,
            AppThreadCreate(project_id=project.id),
            fake,
        )

        closed = app_thread_service.close_app_thread(session, app_thread.id, fake)

        assert closed.status == "CLOSED"
        assert fake.deleted == ["bridge-1"]


def test_rename_app_thread_syncs_bridge_title() -> None:
    for session in make_session():
        project = add_project(session)
        fake = FakeBridgeClient()
        app_thread = app_thread_service.create_app_thread(
            session,
            AppThreadCreate(project_id=project.id, title="Old"),
            fake,
        )

        renamed = app_thread_service.rename_app_thread(
            session,
            app_thread.id,
            AppThreadUpdate(title="New"),
            fake,
        )

        assert renamed.title == "New"
        assert fake.renamed == [("bridge-1", "New")]


def test_reopen_app_thread_updates_bridge_ids_and_keeps_turn_history() -> None:
    for session in make_session():
        project = add_project(session)
        fake = FakeBridgeClient()
        app_thread = app_thread_service.create_app_thread(
            session,
            AppThreadCreate(project_id=project.id, title="Chat"),
            fake,
        )
        app_turn = app_thread_service.send_app_turn(
            session,
            app_thread.id,
            AppTurnCreate(message="hello"),
            fake,
        )
        app_thread.status = "ERROR"
        app_thread.last_error = "thread_not_found"
        session.add(app_thread)
        session.commit()

        reopened = app_thread_service.reopen_app_thread(session, app_thread.id, fake)
        turns = app_thread_service.list_app_turns(session, app_thread.id)

        assert reopened.bridge_thread_id == "bridge-2"
        assert reopened.app_thread_id == "app-2"
        assert reopened.generation == 2
        assert reopened.status == "ACTIVE"
        assert reopened.last_error is None
        assert [turn.id for turn in turns] == [app_turn.id]
        assert fake.created_cwds == [project.path, project.path]


def test_reopen_app_thread_not_found() -> None:
    for session in make_session():
        fake = FakeBridgeClient()

        with pytest.raises(HTTPException) as exc:
            app_thread_service.reopen_app_thread(session, 404, fake)

        assert exc.value.status_code == 404


def test_reopen_app_thread_rejects_missing_bridge_thread_id() -> None:
    for session in make_session():
        project = add_project(session)
        fake = FakeBridgeClient()
        app_thread = app_thread_service.create_app_thread(
            session,
            AppThreadCreate(project_id=project.id, title="Chat"),
            fake,
        )
        fake.missing_bridge_thread_id = True

        with pytest.raises(HTTPException) as exc:
            app_thread_service.reopen_app_thread(session, app_thread.id, fake)

        assert exc.value.status_code == 502
        assert exc.value.detail["code"] == "invalid_bridge_response"


def test_create_async_app_turn_creates_pending_turn(monkeypatch) -> None:
    submitted: list[int] = []
    monkeypatch.setattr(
        "backend.services.app_turn_executor.submit_app_turn",
        lambda app_turn_id: submitted.append(app_turn_id),
    )
    for session in make_session():
        project = add_project(session)
        fake = FakeBridgeClient()
        app_thread = app_thread_service.create_app_thread(
            session,
            AppThreadCreate(project_id=project.id),
            fake,
        )

        app_turn = app_thread_service.create_async_app_turn(
            session,
            app_thread.id,
            AppTurnCreate(message="hello"),
        )

        assert app_turn.status == "PENDING"
        assert app_turn.started_at is None
        assert app_turn.completed_at is None
        assert submitted == [app_turn.id]


def test_app_turn_stream_snapshot_filters_active_bridge_turn_events(monkeypatch) -> None:
    monkeypatch.setattr("backend.services.app_turn_executor.submit_app_turn", lambda app_turn_id: None)
    for session in make_session():
        project = add_project(session)
        fake = FakeBridgeClient()
        app_thread = app_thread_service.create_app_thread(
            session,
            AppThreadCreate(project_id=project.id),
            fake,
        )
        app_turn = app_thread_service.create_async_app_turn(
            session,
            app_thread.id,
            AppTurnCreate(message="hello"),
        )

        snapshot = app_thread_service.get_app_turn_stream_snapshot(session, app_turn.id, bridge_client=fake)

        assert snapshot["next_index"] == 2
        assert {"kind": "assistant_delta", "turn_id": app_turn.id, "text": "live"} in snapshot["events"]
        assert all(event.get("text") != "old" for event in snapshot["events"])


def test_create_async_app_turn_rejects_closed_thread(monkeypatch) -> None:
    monkeypatch.setattr("backend.services.app_turn_executor.submit_app_turn", lambda app_turn_id: None)
    for session in make_session():
        project = add_project(session)
        fake = FakeBridgeClient()
        app_thread = app_thread_service.create_app_thread(
            session,
            AppThreadCreate(project_id=project.id),
            fake,
        )
        app_thread.status = "CLOSED"
        session.add(app_thread)
        session.commit()

        with pytest.raises(HTTPException) as exc:
            app_thread_service.create_async_app_turn(
                session,
                app_thread.id,
                AppTurnCreate(message="hello"),
            )

        assert exc.value.status_code == 400


def test_create_async_app_turn_conflicts_with_pending_or_running_turn(monkeypatch) -> None:
    monkeypatch.setattr("backend.services.app_turn_executor.submit_app_turn", lambda app_turn_id: None)
    for status in ("PENDING", "RUNNING"):
        for session in make_session():
            project = add_project(session)
            fake = FakeBridgeClient()
            app_thread = app_thread_service.create_app_thread(
                session,
                AppThreadCreate(project_id=project.id),
                fake,
            )
            active_turn = AppTurn(
                app_thread_id=app_thread.id,
                user_message="active",
                status=status,
                created_at=utc_now(),
            )
            session.add(active_turn)
            session.commit()
            session.refresh(active_turn)

            with pytest.raises(HTTPException) as exc:
                app_thread_service.create_async_app_turn(
                    session,
                    app_thread.id,
                    AppTurnCreate(message="hello"),
                )

            assert exc.value.status_code == 409
            assert exc.value.detail["code"] == "app_turn_conflict"
            assert exc.value.detail["app_turn_id"] == active_turn.id


def test_create_async_app_turn_database_constraint_returns_active_turn(monkeypatch) -> None:
    monkeypatch.setattr("backend.services.app_turn_executor.submit_app_turn", lambda app_turn_id: None)
    for session in make_session():
        project = add_project(session)
        fake = FakeBridgeClient()
        app_thread = app_thread_service.create_app_thread(
            session,
            AppThreadCreate(project_id=project.id),
            fake,
        )
        active_turn = AppTurn(
            app_thread_id=app_thread.id,
            user_message="active",
            status="PENDING",
            created_at=utc_now(),
        )
        session.add(active_turn)
        session.commit()
        session.refresh(active_turn)
        real_get_active = app_thread_service._get_active_app_turn
        calls = 0

        def hide_active_once(_session, _app_thread_id):
            nonlocal calls
            calls += 1
            if calls == 1:
                return None
            return real_get_active(_session, _app_thread_id)

        monkeypatch.setattr(app_thread_service, "_get_active_app_turn", hide_active_once)

        with pytest.raises(HTTPException) as exc:
            app_thread_service.create_async_app_turn(
                session,
                app_thread.id,
                AppTurnCreate(message="hello"),
            )

        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "app_turn_conflict"
        assert exc.value.detail["app_turn_id"] == active_turn.id


def test_send_app_turn_conflicts_with_active_turn(monkeypatch) -> None:
    for session in make_session():
        project = add_project(session)
        fake = FakeBridgeClient()
        app_thread = app_thread_service.create_app_thread(
            session,
            AppThreadCreate(project_id=project.id),
            fake,
        )
        active_turn = AppTurn(
            app_thread_id=app_thread.id,
            user_message="active",
            status="RUNNING",
            created_at=utc_now(),
            started_at=utc_now(),
        )
        session.add(active_turn)
        session.commit()
        session.refresh(active_turn)

        with pytest.raises(HTTPException) as exc:
            app_thread_service.send_app_turn(
                session,
                app_thread.id,
                AppTurnCreate(message="hello"),
                fake,
            )

        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "app_turn_conflict"
        assert exc.value.detail["app_turn_id"] == active_turn.id


def test_concurrent_async_app_turn_allows_only_one_active_turn(monkeypatch, tmp_path: Path) -> None:
    submitted: list[int] = []
    submitted_lock = Lock()

    def record_submission(app_turn_id: int) -> None:
        with submitted_lock:
            submitted.append(app_turn_id)

    monkeypatch.setattr("backend.services.app_turn_executor.submit_app_turn", record_submission)
    db_path = tmp_path / "app-turns.db"
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        project = add_project(session)
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
        app_thread_id = app_thread.id

    barrier = Barrier(2)
    calls_lock = Lock()
    precheck_calls = 0
    real_get_active = app_thread_service._get_active_app_turn

    def race_past_precheck(session: Session, checked_thread_id: int) -> AppTurn | None:
        nonlocal precheck_calls
        with calls_lock:
            precheck_calls += 1
            call_number = precheck_calls
        if checked_thread_id == app_thread_id and call_number <= 2:
            barrier.wait(timeout=5)
            return None
        return real_get_active(session, checked_thread_id)

    monkeypatch.setattr(app_thread_service, "_get_active_app_turn", race_past_precheck)

    def create_turn(message: str) -> dict[str, Any]:
        with Session(engine) as thread_session:
            try:
                app_turn = app_thread_service.create_async_app_turn(
                    thread_session,
                    app_thread_id,
                    AppTurnCreate(message=message),
                )
                return {"status_code": 200, "app_turn_id": app_turn.id}
            except HTTPException as exc:
                return {"status_code": exc.status_code, "detail": exc.detail}

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(create_turn, ["first", "second"]))

    success = [result for result in results if result["status_code"] == 200]
    conflicts = [result for result in results if result["status_code"] == 409]
    with Session(engine) as session:
        active_turns = session.exec(
            select(AppTurn).where(AppTurn.app_thread_id == app_thread_id, AppTurn.status.in_(["PENDING", "RUNNING"]))
        ).all()

    assert len(success) == 1
    assert len(conflicts) == 1
    assert len(active_turns) == 1
    assert conflicts[0]["detail"]["code"] == "app_turn_conflict"
    assert conflicts[0]["detail"]["app_turn_id"] == active_turns[0].id


def test_create_async_app_turn_allows_terminal_history(monkeypatch) -> None:
    submitted: list[int] = []
    monkeypatch.setattr(
        "backend.services.app_turn_executor.submit_app_turn",
        lambda app_turn_id: submitted.append(app_turn_id),
    )
    for terminal_status in ("SUCCESS", "FAILED", "CANCELLED"):
        for session in make_session():
            project = add_project(session)
            fake = FakeBridgeClient()
            app_thread = app_thread_service.create_app_thread(
                session,
                AppThreadCreate(project_id=project.id),
                fake,
            )
            historical_turn = AppTurn(
                app_thread_id=app_thread.id,
                user_message="old",
                status=terminal_status,
                created_at=utc_now(),
            )
            session.add(historical_turn)
            session.commit()

            app_turn = app_thread_service.create_async_app_turn(
                session,
                app_thread.id,
                AppTurnCreate(message="new"),
            )

            assert app_turn.status == "PENDING"
            assert submitted[-1] == app_turn.id


def test_get_app_turn_or_404_not_found() -> None:
    for session in make_session():
        with pytest.raises(HTTPException) as exc:
            app_thread_service.get_app_turn_or_404(session, 404)

        assert exc.value.status_code == 404


def test_to_app_turn_read_returns_duration_seconds() -> None:
    for session in make_session():
        project = add_project(session)
        fake = FakeBridgeClient()
        app_thread = app_thread_service.create_app_thread(
            session,
            AppThreadCreate(project_id=project.id),
            fake,
        )
        app_turn = app_thread_service.send_app_turn(
            session,
            app_thread.id,
            AppTurnCreate(message="hello"),
            fake,
        )

        app_turn_read = app_thread_service.to_app_turn_read(app_turn)

        assert app_turn_read.duration_seconds is not None
        assert app_turn_read.duration_seconds >= 0
        assert app_turn_read.event_summary["total_events"] == 2


def test_normalize_event_summary_standardizes_bridge_summary() -> None:
    normalized = app_thread_service.normalize_event_summary(
        {
            "summary": {
                "total_events": 3,
                "event_counts": {"turn/started": 1, "turn/completed": 1},
                "has_error": True,
                "errors": [{"message": "boom"}],
                "assistant_text_preview": "hello",
                "assistant_text_length": 5,
            }
        }
    )

    assert normalized == {
        "total_events": 3,
        "event_type_counts": {"turn/started": 1, "turn/completed": 1},
        "has_error": True,
        "errors": [{"message": "boom"}],
        "assistant_text_length": 5,
        "assistant_text_preview": "hello",
        "raw": {
            "total_events": 3,
            "event_counts": {"turn/started": 1, "turn/completed": 1},
            "has_error": True,
            "errors": [{"message": "boom"}],
            "assistant_text_preview": "hello",
            "assistant_text_length": 5,
        },
    }


def test_to_app_turn_read_compatible_with_partial_and_invalid_summary() -> None:
    for session in make_session():
        project = add_project(session)
        fake = FakeBridgeClient()
        app_thread = app_thread_service.create_app_thread(
            session,
            AppThreadCreate(project_id=project.id),
            fake,
        )
        partial = AppTurn(
            app_thread_id=app_thread.id,
            user_message="partial",
            status="SUCCESS",
            event_summary_json='{"total_events": 4}',
            created_at=utc_now(),
        )
        invalid = AppTurn(
            app_thread_id=app_thread.id,
            user_message="invalid",
            status="SUCCESS",
            event_summary_json="not-json",
            created_at=utc_now(),
        )
        session.add(partial)
        session.add(invalid)
        session.commit()
        session.refresh(partial)
        session.refresh(invalid)

        partial_read = app_thread_service.to_app_turn_read(partial)
        invalid_read = app_thread_service.to_app_turn_read(invalid)

        assert partial_read.event_summary["total_events"] == 4
        assert partial_read.event_summary["event_type_counts"] == {}
        assert invalid_read.event_summary == {"invalid_summary": "not-json"}


def test_get_app_thread_events_returns_latest_turn_with_summary() -> None:
    for session in make_session():
        project = add_project(session)
        fake = FakeBridgeClient()
        app_thread = app_thread_service.create_app_thread(
            session,
            AppThreadCreate(project_id=project.id),
            fake,
        )
        with_summary = AppTurn(
            app_thread_id=app_thread.id,
            user_message="with summary",
            status="SUCCESS",
            event_summary_json='{"summary":{"total_events": 7}}',
            created_at=utc_now(),
        )
        without_summary = AppTurn(
            app_thread_id=app_thread.id,
            user_message="without summary",
            status="SUCCESS",
            created_at=utc_now(),
        )
        session.add(with_summary)
        session.add(without_summary)
        session.commit()
        session.refresh(with_summary)

        events = app_thread_service.get_app_thread_events(session, app_thread.id)

        assert events.latest_turn_id == with_summary.id
        assert events.event_summary["total_events"] == 7


def test_list_app_threads_filters_status_and_hides_archived_by_default() -> None:
    for session in make_session():
        project = add_project(session)
        active = AppThread(
            project_id=project.id,
            title="Active",
            status="ACTIVE",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        error = AppThread(
            project_id=project.id,
            title="Error",
            status="ERROR",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        archived = AppThread(
            project_id=project.id,
            title="[archived] Closed",
            status="CLOSED",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(active)
        session.add(error)
        session.add(archived)
        session.commit()

        active_threads = app_thread_service.list_app_threads(session, status_filter="ACTIVE")
        default_threads = app_thread_service.list_app_threads(session)
        all_threads = app_thread_service.list_app_threads(session, include_archived=True)

        assert [thread.status for thread in active_threads] == ["ACTIVE"]
        assert all(not thread.title.startswith("[archived]") for thread in default_threads)
        assert any(thread.title.startswith("[archived]") for thread in all_threads)


def test_list_app_threads_rejects_invalid_status() -> None:
    for session in make_session():
        with pytest.raises(HTTPException) as exc:
            app_thread_service.list_app_threads(session, status_filter="BAD")

        assert exc.value.status_code == 400


def test_list_app_turns_filters_status_and_rejects_invalid_status() -> None:
    for session in make_session():
        project = add_project(session)
        fake = FakeBridgeClient()
        app_thread = app_thread_service.create_app_thread(
            session,
            AppThreadCreate(project_id=project.id),
            fake,
        )
        for turn_status in ("SUCCESS", "FAILED"):
            session.add(
                AppTurn(
                    app_thread_id=app_thread.id,
                    user_message=turn_status,
                    status=turn_status,
                    created_at=utc_now(),
                )
            )
        session.commit()

        success_turns = app_thread_service.list_app_turns(session, app_thread.id, status_filter="SUCCESS")
        assert [turn.status for turn in success_turns] == ["SUCCESS"]
        with pytest.raises(HTTPException) as exc:
            app_thread_service.list_app_turns(session, app_thread.id, status_filter="BAD")
        assert exc.value.status_code == 400


def test_cleanup_app_threads_archives_closed_and_error_only() -> None:
    for session in make_session():
        project = add_project(session)
        closed = AppThread(
            project_id=project.id,
            title="Closed",
            status="CLOSED",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        already_archived = AppThread(
            project_id=project.id,
            title="[archived] Old",
            status="CLOSED",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        active = AppThread(
            project_id=project.id,
            title="Active",
            status="ACTIVE",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(closed)
        session.add(already_archived)
        session.add(active)
        session.commit()
        session.refresh(closed)
        session.refresh(already_archived)

        result = app_thread_service.cleanup_app_threads(session, "CLOSED", limit=50)
        session.refresh(closed)
        session.refresh(already_archived)

        assert result == {"archived_count": 1, "archived_thread_ids": [closed.id]}
        assert closed.title == "[archived] Closed"
        assert already_archived.title == "[archived] Old"
        with pytest.raises(HTTPException) as exc:
            app_thread_service.cleanup_app_threads(session, "ACTIVE")
        assert exc.value.status_code == 400


def test_cancel_app_turn_pending_and_running_marks_cancelled(monkeypatch) -> None:
    monkeypatch.setattr("backend.services.app_turn_executor.submit_app_turn", lambda app_turn_id: None)
    for initial_status in ("PENDING", "RUNNING"):
        for session in make_session():
            project = add_project(session)
            fake = FakeBridgeClient()
            app_thread = app_thread_service.create_app_thread(
                session,
                AppThreadCreate(project_id=project.id),
                fake,
            )
            app_turn = AppTurn(
                app_thread_id=app_thread.id,
                user_message="hello",
                status=initial_status,
                created_at=utc_now(),
                started_at=utc_now() if initial_status == "RUNNING" else None,
            )
            session.add(app_turn)
            session.commit()
            session.refresh(app_turn)

            cancelled = app_thread_service.cancel_app_turn(session, app_turn.id)
            session.refresh(app_thread)

            assert cancelled.status == "CANCELLED"
            assert cancelled.error_message == "cancelled by user"
            assert cancelled.completed_at is not None
            assert app_thread.status == "RECOVER_REQUIRED"
            assert app_thread.last_error == "cancelled by user; reopen required before next turn"


def test_cancel_app_turn_terminal_status_is_idempotent() -> None:
    for terminal_status in ("SUCCESS", "FAILED", "CANCELLED"):
        for session in make_session():
            project = add_project(session)
            fake = FakeBridgeClient()
            app_thread = app_thread_service.create_app_thread(
                session,
                AppThreadCreate(project_id=project.id),
                fake,
            )
            app_turn = AppTurn(
                app_thread_id=app_thread.id,
                user_message="hello",
                status=terminal_status,
                error_message="existing",
                created_at=utc_now(),
                completed_at=utc_now(),
            )
            session.add(app_turn)
            session.commit()
            session.refresh(app_turn)

            returned = app_thread_service.cancel_app_turn(session, app_turn.id)

            assert returned.status == terminal_status
            assert returned.error_message == "existing"


def test_cancel_agent_app_turn_cancels_command_and_blocks_next_turn(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_COMMAND_MODE", "true")
    for session in make_session():
        from tests.test_runs_api import add_device, add_workspace

        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")
        app_thread = AppThread(
            project_id=project.id,
            title="Agent chat",
            device_id="device-a",
            workspace_id=workspace.id,
            agent_session_id="agent-session-1",
            app_thread_id="codex-thread-1",
            status="ACTIVE",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(app_thread)
        session.commit()
        session.refresh(app_thread)
        app_turn = app_thread_service.create_async_app_turn(
            session,
            app_thread.id,
            AppTurnCreate(message="hello"),
        )

        cancelled = app_thread_service.cancel_app_turn(session, app_turn.id)
        session.refresh(app_thread)

        assert cancelled.status == "CANCELLED"
        assert app_turn.command_id is not None
        command = session.get(AgentCommand, app_turn.command_id)
        assert command is not None
        assert command.status.value == "CANCELLED"
        assert app_thread.status == "RECOVER_REQUIRED"
        with pytest.raises(HTTPException) as exc:
            app_thread_service.create_async_app_turn(
                session,
                app_thread.id,
                AppTurnCreate(message="after cancel"),
            )
        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "app_thread_not_active"
        assert exc.value.detail["status"] == "RECOVER_REQUIRED"


def test_cancelled_agent_turn_ignores_late_success_complete(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_COMMAND_MODE", "true")
    for session in make_session():
        from tests.test_runs_api import add_device, add_workspace

        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")
        app_thread = AppThread(
            project_id=project.id,
            title="Agent chat",
            device_id="device-a",
            workspace_id=workspace.id,
            agent_session_id="agent-session-1",
            app_thread_id="codex-thread-1",
            status="ACTIVE",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(app_thread)
        session.commit()
        session.refresh(app_thread)
        app_turn = app_thread_service.create_async_app_turn(session, app_thread.id, AppTurnCreate(message="hello"))
        app_thread_service.cancel_app_turn(session, app_turn.id)

        completed = app_thread_service.complete_agent_turn_start(
            session,
            command_id=app_turn.command_id,
            result_payload={"assistant_final": "late success", "codex_turn_id": "late-turn"},
        )
        session.refresh(app_thread)

        assert completed is not None
        assert completed.status == "CANCELLED"
        assert completed.assistant_final is None
        assert app_thread.status == "RECOVER_REQUIRED"


def test_agent_turn_complete_ignores_stale_generation(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_COMMAND_MODE", "true")
    for session in make_session():
        from tests.test_runs_api import add_device, add_workspace

        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")
        app_thread = AppThread(
            project_id=project.id,
            title="Agent chat",
            device_id="device-a",
            workspace_id=workspace.id,
            agent_session_id="agent-session-1",
            app_thread_id="codex-thread-1",
            generation=1,
            status="ACTIVE",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(app_thread)
        session.commit()
        session.refresh(app_thread)
        app_turn = app_thread_service.create_async_app_turn(session, app_thread.id, AppTurnCreate(message="hello"))
        app_thread.generation = 2
        app_thread.agent_session_id = "agent-session-2"
        app_thread.app_thread_id = "codex-thread-2"
        app_thread.status = "ACTIVE"
        session.add(app_thread)
        session.commit()

        completed = app_thread_service.complete_agent_turn_start(
            session,
            command_id=app_turn.command_id,
            result_payload={"assistant_final": "stale final", "codex_turn_id": "stale-turn"},
        )
        session.refresh(app_thread)

        assert completed is not None
        assert completed.status == "PENDING"
        assert completed.assistant_final is None
        assert app_thread.generation == 2
        assert app_thread.agent_session_id == "agent-session-2"


def test_cancel_app_turn_not_found() -> None:
    for session in make_session():
        with pytest.raises(HTTPException) as exc:
            app_thread_service.cancel_app_turn(session, 404)

        assert exc.value.status_code == 404
