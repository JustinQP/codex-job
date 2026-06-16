from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskType(str, Enum):
    PLAN = "PLAN"
    IMPLEMENT = "IMPLEMENT"
    REVIEW = "REVIEW"
    TEST_FIX = "TEST_FIX"
    DOCS = "DOCS"
    COMMIT = "COMMIT"


class Project(SQLModel, table=True):
    __tablename__ = "projects"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    path: str
    enabled: bool = Field(default=True, index=True)
    test_command: Optional[str] = None
    smoke_check_command: Optional[str] = None
    default_branch: Optional[str] = None
    require_clean_worktree: Optional[bool] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Task(SQLModel, table=True):
    __tablename__ = "tasks"

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id", index=True)
    prompt: str
    task_type: TaskType = Field(default=TaskType.IMPLEMENT, index=True)
    status: TaskStatus = Field(default=TaskStatus.PENDING, index=True)
    timeout_seconds: int = Field(default=7200)
    exit_code: Optional[int] = None
    error_message: Optional[str] = None
    cancel_requested: bool = Field(default=False, index=True)
    runner_id: Optional[str] = Field(default=None, index=True)
    runner_pid: Optional[int] = None
    log_file: Optional[str] = None
    result_file: Optional[str] = None
    diff_file: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class RunnerRecord(SQLModel, table=True):
    __tablename__ = "runner_records"

    runner_id: str = Field(primary_key=True)
    pid: int
    hostname: str
    status: str = Field(default="ONLINE", index=True)
    registered_at: datetime = Field(default_factory=utc_now)
    last_heartbeat_at: datetime = Field(default_factory=utc_now, index=True)
