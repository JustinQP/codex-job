from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

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
