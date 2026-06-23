from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from sqlalchemy import inspect, text
from sqlmodel import SQLModel, Session, create_engine

from backend.migrations import run_migrations


ROOT_DIR = Path(__file__).resolve().parents[1]


def _env_path(name: str, default: Path) -> Path:
    return Path(os.environ.get(name, str(default))).expanduser().resolve()


DATA_DIR = _env_path("CODEX_RUNNER_DATA_DIR", ROOT_DIR / "data")
JOBS_DIR = DATA_DIR / "jobs"
DB_PATH = _env_path("CODEX_RUNNER_DB_PATH", DATA_DIR / "app.db")
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
)


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Import models before metadata creation so SQLModel registers the tables.
    from backend import models  # noqa: F401

    _assert_v2_database_or_empty()
    SQLModel.metadata.create_all(engine)
    backup_enabled = os.environ.get("CODEX_RUNNER_DB_BACKUP", "true").lower() not in {
        "0",
        "false",
        "no",
    }
    run_migrations(engine, db_path=DB_PATH, backup=backup_enabled)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def _assert_v2_database_or_empty() -> None:
    if not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
        return
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if not tables:
        return
    legacy_tables = {"tasks", "runner_records"} & tables
    missing: list[str] = []
    expected_columns = {
        "runs": {"id", "command_id", "workspace_id", "device_id"},
        "agent_commands": {"id", "cancel_requested", "lease_token", "result_payload_json"},
        "app_threads": {"id", "codex_thread_id", "agent_session_id", "workspace_id"},
        "app_turns": {"id", "codex_turn_id", "command_id"},
    }
    for table, columns in expected_columns.items():
        if table not in tables:
            missing.append(table)
            continue
        existing_columns = {column["name"] for column in inspector.get_columns(table)}
        for column in columns - existing_columns:
            missing.append(f"{table}.{column}")
    if legacy_tables or missing:
        details = []
        if legacy_tables:
            details.append(f"legacy tables: {', '.join(sorted(legacy_tables))}")
        if missing:
            details.append(f"missing v2 columns/tables: {', '.join(sorted(missing))}")
        raise RuntimeError(
            "data/app.db is not compatible with v2.0 mainline. "
            + "; ".join(details)
            + ". Stop services and clean data/app.db or run scripts/verify_data_migration.py for reset guidance."
        )
