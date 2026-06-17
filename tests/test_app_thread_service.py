from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from fastapi import HTTPException
from sqlmodel import SQLModel, Session, create_engine, select
from sqlmodel.pool import StaticPool

from backend.models import AppThread, AppTurn, Project, utc_now
from backend.schemas import AppThreadCreate, AppThreadUpdate, AppTurnCreate
from backend.services.app_server_bridge_client import AppServerBridgeError
from backend.services import app_thread_service


class FakeBridgeClient:
    def __init__(self) -> None:
        self.created_titles: list[str] = []
        self.renamed: list[tuple[str, str]] = []
        self.deleted: list[str] = []
        self.fail_send = False
        self.fail_create = False
        self.fail_rename = False

    def create_thread(self, title: str) -> dict[str, Any]:
        if self.fail_create:
            raise AppServerBridgeError(None, "network_error", "bridge down", "request")
        self.created_titles.append(title)
        return {
            "bridge_thread_id": "bridge-1",
            "app_thread_id": "app-1",
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
            "assistant_final_preview": f"assistant:{message}",
        }

    def get_events(self, bridge_thread_id: str) -> dict[str, Any]:
        return {"summary": {"total_events": 2, "bridge_thread_id": bridge_thread_id}}

    def get_final(self, bridge_thread_id: str) -> dict[str, Any]:
        return {"assistant_final": "final fallback"}


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
        assert app_turn.assistant_final == "assistant:hello"
        assert app_turn.bridge_turn_id == "turn-1"
        assert app_turn.completed_at is not None
        assert final.assistant_final == "assistant:hello"
        assert events.latest_turn_id == app_turn.id
        assert events.event_summary == {"total_events": 2, "bridge_thread_id": "bridge-1"}


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
