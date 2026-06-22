from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import UniqueConstraint
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


class DeviceStatus(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    DISABLED = "DISABLED"


class WorkspaceBindingStatus(str, Enum):
    UNBOUND = "UNBOUND"
    BOUND = "BOUND"


class AgentCommandStatus(str, Enum):
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


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
    default_runner_id: Optional[str] = Field(default=None, index=True)
    workspace_id: Optional[int] = Field(default=None, foreign_key="workspaces.id", index=True)
    workspace_binding_status: WorkspaceBindingStatus = Field(
        default=WorkspaceBindingStatus.UNBOUND,
        index=True,
    )
    default_model: Optional[str] = None
    default_reasoning_effort: Optional[str] = None
    default_sandbox: Optional[str] = None
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
    model: Optional[str] = None
    reasoning_effort: Optional[str] = None
    sandbox: Optional[str] = None
    exit_code: Optional[int] = None
    error_message: Optional[str] = None
    cancel_requested: bool = Field(default=False, index=True)
    assigned_runner_id: Optional[str] = Field(default=None, index=True)
    runner_id: Optional[str] = Field(default=None, index=True)
    runner_pid: Optional[int] = None
    lease_expires_at: Optional[datetime] = Field(default=None, index=True)
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
    supported_models: Optional[str] = None
    status: str = Field(default="ONLINE", index=True)
    registered_at: datetime = Field(default_factory=utc_now)
    last_heartbeat_at: datetime = Field(default_factory=utc_now, index=True)
    lease_expires_at: Optional[datetime] = Field(default=None, index=True)


class Device(SQLModel, table=True):
    __tablename__ = "devices"

    device_id: str = Field(primary_key=True)
    display_name: str
    hostname: str
    os_name: str
    agent_version: str
    capabilities_json: Optional[str] = None
    status: DeviceStatus = Field(default=DeviceStatus.ONLINE, index=True)
    last_heartbeat_at: datetime = Field(default_factory=utc_now, index=True)
    lease_expires_at: Optional[datetime] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Workspace(SQLModel, table=True):
    __tablename__ = "workspaces"
    __table_args__ = (
        UniqueConstraint("device_id", "workspace_key", name="ux_workspaces_device_key"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_key: str = Field(index=True)
    device_id: str = Field(foreign_key="devices.device_id", index=True)
    name: str
    path_label: str
    enabled: bool = Field(default=True, index=True)
    default_model: Optional[str] = None
    default_reasoning_effort: Optional[str] = None
    default_sandbox: Optional[str] = None
    default_approval_policy: Optional[str] = None
    require_clean_worktree: Optional[bool] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AgentCommand(SQLModel, table=True):
    __tablename__ = "agent_commands"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="ux_agent_commands_idempotency_key"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    device_id: str = Field(foreign_key="devices.device_id", index=True)
    command_type: str = Field(index=True)
    aggregate_type: Optional[str] = Field(default=None, index=True)
    aggregate_id: Optional[str] = Field(default=None, index=True)
    idempotency_key: str
    payload_json: str = "{}"
    status: AgentCommandStatus = Field(default=AgentCommandStatus.PENDING, index=True)
    claim_request_id: Optional[str] = Field(default=None, index=True)
    lease_token: Optional[str] = Field(default=None, index=True)
    lease_expires_at: Optional[datetime] = Field(default=None, index=True)
    attempt_count: int = Field(default=0)
    max_attempts: int = Field(default=3)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    claimed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_error: Optional[str] = None


class AppThread(SQLModel, table=True):
    __tablename__ = "app_threads"

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id", index=True)
    title: str
    bridge_thread_id: Optional[str] = Field(default=None, index=True)
    app_thread_id: Optional[str] = None
    status: str = Field(default="CREATED", index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    last_error: Optional[str] = None


class AppTurn(SQLModel, table=True):
    __tablename__ = "app_turns"

    id: Optional[int] = Field(default=None, primary_key=True)
    app_thread_id: int = Field(foreign_key="app_threads.id", index=True)
    user_message: str
    assistant_final: Optional[str] = None
    status: str = Field(default="PENDING", index=True)
    error_message: Optional[str] = None
    bridge_turn_id: Optional[str] = None
    event_summary_json: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
