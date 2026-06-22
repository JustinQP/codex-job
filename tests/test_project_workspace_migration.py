from __future__ import annotations

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from backend.migrations import run_migrations
from backend.models import (
    AppThread,
    Device,
    Project,
    Task,
    TaskStatus,
    Workspace,
    WorkspaceBindingStatus,
    utc_now,
)
from backend.schemas import TaskCreate
from backend.services import project_service, task_service


def make_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def create_legacy_project_task_thread(engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE projects (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL,
                    enabled BOOLEAN NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE tasks (
                    id INTEGER PRIMARY KEY,
                    project_id INTEGER NOT NULL,
                    prompt TEXT NOT NULL,
                    status TEXT NOT NULL,
                    timeout_seconds INTEGER NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE app_threads (
                    id INTEGER PRIMARY KEY,
                    project_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO projects (id, name, path, enabled, created_at, updated_at)
                VALUES (1, 'Demo', 'F:/demo', 1, '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO tasks (id, project_id, prompt, status, timeout_seconds, created_at, updated_at)
                VALUES (1, 1, 'old task', 'SUCCESS', 120, '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO app_threads (id, project_id, title, status, created_at, updated_at)
                VALUES (1, 1, 'Old thread', 'ACTIVE', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')
                """
            )
        )


def test_legacy_project_records_survive_workspace_migration() -> None:
    engine = make_engine()
    create_legacy_project_task_thread(engine)

    run_migrations(engine, backup=False)

    with Session(engine) as session:
        projects = session.exec(select(Project)).all()
        task_count = session.exec(text("SELECT COUNT(*) FROM tasks")).one()[0]
        app_thread_count = session.exec(text("SELECT COUNT(*) FROM app_threads")).one()[0]

        assert len(projects) == 1
        assert task_count == 1
        assert app_thread_count == 1
        assert projects[0].workspace_id is None
        assert projects[0].workspace_binding_status == WorkspaceBindingStatus.UNBOUND


def test_project_can_be_bound_to_workspace_explicitly() -> None:
    engine = make_engine()
    SQLModel.metadata.create_all(engine)
    now = utc_now()
    with Session(engine) as session:
        project = Project(
            name="Demo",
            path="F:/demo",
            enabled=True,
            created_at=now,
            updated_at=now,
        )
        device = Device(
            device_id="device-a",
            display_name="Device",
            hostname="host",
            os_name="Windows",
            agent_version="0.1.0",
            last_heartbeat_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(project)
        session.add(device)
        session.commit()
        workspace = Workspace(
            device_id="device-a",
            workspace_key="repo",
            name="Repo",
            path_label="repo",
            created_at=now,
            updated_at=now,
        )
        session.add(workspace)
        session.commit()
        session.refresh(project)
        session.refresh(workspace)

        bound = project_service.bind_project_workspace(session, project.id, workspace.id)

        assert bound.workspace_id == workspace.id
        assert bound.workspace_binding_status == WorkspaceBindingStatus.BOUND


def test_unbound_project_still_uses_legacy_task_create() -> None:
    engine = make_engine()
    SQLModel.metadata.create_all(engine)
    now = utc_now()
    with Session(engine) as session:
        project = Project(
            name="Demo",
            path="F:/demo",
            enabled=True,
            created_at=now,
            updated_at=now,
        )
        session.add(project)
        session.commit()
        session.refresh(project)

        task = task_service.create_task(
            session,
            TaskCreate(project_id=project.id, prompt="legacy run"),
        )

        assert task.status == TaskStatus.PENDING
        assert project.workspace_binding_status == WorkspaceBindingStatus.UNBOUND
