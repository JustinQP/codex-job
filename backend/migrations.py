from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from pathlib import Path
import shutil
from typing import Callable

from sqlalchemy import Engine, text

from backend.models import utc_now


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    apply: Callable[[Engine], None]


LEGACY_COLUMN_SPECS: dict[str, dict[str, str]] = {
    "projects": {
        "test_command": "TEXT",
        "smoke_check_command": "TEXT",
        "default_branch": "TEXT",
        "require_clean_worktree": "BOOLEAN",
        "default_runner_id": "TEXT",
        "default_model": "TEXT",
        "default_reasoning_effort": "TEXT",
        "default_sandbox": "TEXT",
    },
    "tasks": {
        "task_type": "VARCHAR DEFAULT 'IMPLEMENT'",
        "model": "TEXT",
        "reasoning_effort": "TEXT",
        "sandbox": "TEXT",
        "cancel_requested": "BOOLEAN DEFAULT 0",
        "assigned_runner_id": "TEXT",
        "runner_id": "TEXT",
        "runner_pid": "INTEGER",
        "lease_expires_at": "TIMESTAMP",
    },
    "runner_records": {
        "lease_expires_at": "TIMESTAMP",
        "supported_models": "TEXT",
    },
}


def _utc_iso() -> str:
    return utc_now().astimezone(timezone.utc).isoformat()


def ensure_schema_migrations_table(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                )
                """
            )
        )


def backup_sqlite_database(db_path: Path) -> Path | None:
    if not db_path.exists():
        return None
    backup_path = db_path.with_name(f"{db_path.name}.bak-{utc_now():%Y%m%d%H%M%S}")
    shutil.copy2(db_path, backup_path)
    return backup_path


def apply_legacy_sqlite_columns(engine: Engine) -> None:
    with engine.begin() as connection:
        for table_name, columns in LEGACY_COLUMN_SPECS.items():
            existing = {
                row[1]
                for row in connection.exec_driver_sql(
                    f"PRAGMA table_info({table_name})"
                )
            }
            if not existing:
                continue
            for column_name, column_type in columns.items():
                if column_name in existing:
                    continue
                connection.execute(
                    text(
                        f"ALTER TABLE {table_name} "
                        f"ADD COLUMN {column_name} {column_type}"
                    )
                )


def create_devices_table(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS devices (
                    device_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    hostname TEXT NOT NULL,
                    os_name TEXT NOT NULL,
                    agent_version TEXT NOT NULL,
                    capabilities_json TEXT,
                    status TEXT NOT NULL DEFAULT 'ONLINE',
                    last_heartbeat_at TIMESTAMP NOT NULL,
                    lease_expires_at TIMESTAMP,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_devices_status
                ON devices (status)
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_devices_last_heartbeat_at
                ON devices (last_heartbeat_at)
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_devices_lease_expires_at
                ON devices (lease_expires_at)
                """
            )
        )


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version="0001",
        name="legacy_sqlite_columns",
        apply=apply_legacy_sqlite_columns,
    ),
    Migration(
        version="0002",
        name="devices",
        apply=create_devices_table,
    ),
)


def applied_versions(engine: Engine) -> set[str]:
    ensure_schema_migrations_table(engine)
    with engine.begin() as connection:
        rows = connection.execute(text("SELECT version FROM schema_migrations"))
        return {str(row[0]) for row in rows}


def run_migrations(
    engine: Engine,
    *,
    db_path: Path | None = None,
    backup: bool = True,
    migrations: tuple[Migration, ...] = MIGRATIONS,
) -> list[str]:
    ensure_schema_migrations_table(engine)
    completed = applied_versions(engine)
    pending = [migration for migration in migrations if migration.version not in completed]
    if not pending:
        return []

    if backup and db_path is not None:
        backup_sqlite_database(db_path)

    applied: list[str] = []
    for migration in pending:
        migration.apply(engine)
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO schema_migrations (version, name, applied_at)
                    VALUES (:version, :name, :applied_at)
                    """
                ),
                {
                    "version": migration.version,
                    "name": migration.name,
                    "applied_at": _utc_iso(),
                },
            )
        applied.append(migration.version)
    return applied
