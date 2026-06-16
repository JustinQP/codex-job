from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from sqlalchemy import text
from sqlmodel import SQLModel, Session, create_engine


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

    SQLModel.metadata.create_all(engine)
    _ensure_sqlite_columns()


def _ensure_sqlite_columns() -> None:
    column_specs = {
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

    with engine.begin() as connection:
        for table_name, columns in column_specs.items():
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


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
