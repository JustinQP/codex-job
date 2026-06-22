from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlmodel import SQLModel, create_engine
from sqlmodel.pool import StaticPool

from backend import migrations
from backend.migrations import Migration, run_migrations


def make_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def table_columns(engine, table_name: str) -> set[str]:
    with engine.begin() as connection:
        return {
            row[1]
            for row in connection.exec_driver_sql(f"PRAGMA table_info({table_name})")
        }


def migration_rows(engine) -> list[tuple[str, str]]:
    with engine.begin() as connection:
        rows = connection.execute(
            text("SELECT version, name FROM schema_migrations ORDER BY version")
        )
        return [(str(row[0]), str(row[1])) for row in rows]


def create_legacy_schema(engine) -> None:
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
                    exit_code INTEGER,
                    error_message TEXT,
                    log_file TEXT,
                    result_file TEXT,
                    diff_file TEXT,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    started_at TIMESTAMP,
                    finished_at TIMESTAMP
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE runner_records (
                    runner_id TEXT PRIMARY KEY,
                    pid INTEGER NOT NULL,
                    hostname TEXT NOT NULL,
                    status TEXT NOT NULL,
                    registered_at TIMESTAMP NOT NULL,
                    last_heartbeat_at TIMESTAMP NOT NULL
                )
                """
            )
        )


def test_empty_database_initializes_to_latest_migration() -> None:
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    applied = run_migrations(engine, backup=False)

    assert applied == ["0001", "0002", "0003", "0004"]
    assert migration_rows(engine) == [
        ("0001", "legacy_sqlite_columns"),
        ("0002", "devices"),
        ("0003", "workspaces"),
        ("0004", "project_workspace_binding"),
    ]


def test_legacy_database_upgrades_missing_columns() -> None:
    engine = make_engine()
    create_legacy_schema(engine)

    applied = run_migrations(engine, backup=False)

    assert applied == ["0001", "0002", "0003", "0004"]
    assert "default_runner_id" in table_columns(engine, "projects")
    assert "task_type" in table_columns(engine, "tasks")
    assert "lease_expires_at" in table_columns(engine, "runner_records")
    assert "device_id" in table_columns(engine, "devices")
    assert "workspace_key" in table_columns(engine, "workspaces")
    assert "workspace_id" in table_columns(engine, "projects")
    assert "workspace_binding_status" in table_columns(engine, "projects")


def test_migrations_are_idempotent() -> None:
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    first = run_migrations(engine, backup=False)
    second = run_migrations(engine, backup=False)

    assert first == ["0001", "0002", "0003", "0004"]
    assert second == []
    assert migration_rows(engine) == [
        ("0001", "legacy_sqlite_columns"),
        ("0002", "devices"),
        ("0003", "workspaces"),
        ("0004", "project_workspace_binding"),
    ]


def test_failed_migration_is_not_marked_complete() -> None:
    engine = make_engine()

    def fail(_engine) -> None:
        raise RuntimeError("boom")

    broken = (Migration(version="9999", name="broken", apply=fail),)

    with pytest.raises(RuntimeError, match="boom"):
        run_migrations(engine, backup=False, migrations=broken)

    assert migration_rows(engine) == []


def test_sqlite_backup_created_once_for_pending_batch(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    db_path.write_text("sqlite bytes", encoding="utf-8")
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    run_migrations(engine, db_path=db_path, backup=True)

    backups = list(tmp_path.glob("app.db.bak-*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "sqlite bytes"
