from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.models import DeviceStatus, TaskStatus, TaskType


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    path: str = Field(..., min_length=1)
    enabled: bool = True
    test_command: Optional[str] = None
    smoke_check_command: Optional[str] = None
    default_branch: Optional[str] = None
    require_clean_worktree: Optional[bool] = None
    default_runner_id: Optional[str] = None
    default_model: Optional[str] = None
    default_reasoning_effort: Optional[str] = None
    default_sandbox: Optional[str] = None


class ProjectRead(BaseModel):
    id: int
    name: str
    path_label: str
    enabled: bool
    test_command: Optional[str]
    smoke_check_command: Optional[str]
    default_branch: Optional[str]
    require_clean_worktree: Optional[bool]
    default_runner_id: Optional[str]
    default_model: Optional[str]
    default_reasoning_effort: Optional[str]
    default_sandbox: Optional[str]
    created_at: datetime
    updated_at: datetime


class TaskCreate(BaseModel):
    project_id: int
    prompt: str = Field(..., min_length=1)
    timeout_seconds: int = Field(default=7200, ge=30, le=21600)
    task_type: TaskType = TaskType.IMPLEMENT
    assigned_runner_id: Optional[str] = None
    model: Optional[str] = None
    reasoning_effort: Optional[str] = None
    sandbox: Optional[str] = None


class TaskRead(BaseModel):
    id: int
    project_id: int
    prompt: str
    task_type: TaskType
    status: TaskStatus
    timeout_seconds: int
    model: Optional[str]
    reasoning_effort: Optional[str]
    sandbox: Optional[str]
    exit_code: Optional[int]
    error_message: Optional[str]
    cancel_requested: bool
    assigned_runner_id: Optional[str]
    runner_id: Optional[str]
    runner_pid: Optional[int]
    lease_expires_at: Optional[datetime]
    log_url: str
    result_url: str
    diff_url: str
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]


class TaskArtifactsRead(BaseModel):
    log_url: str
    result_url: str
    diff_url: str
    git_status_url: str
    report_url: str


class TaskTemplateRead(BaseModel):
    task_type: TaskType
    title: str
    template: str


class RunnerRegister(BaseModel):
    runner_id: str = Field(..., min_length=1, max_length=100)
    pid: int = Field(..., ge=1)
    hostname: str = Field(..., min_length=1, max_length=200)
    supported_models: Optional[str] = None


class RunnerHeartbeat(BaseModel):
    runner_id: str = Field(..., min_length=1, max_length=100)
    pid: int = Field(..., ge=1)
    hostname: str = Field(..., min_length=1, max_length=200)
    supported_models: Optional[str] = None


class RunnerRead(BaseModel):
    runner_id: str
    pid: int
    hostname: str
    supported_models: Optional[str]
    status: str
    registered_at: datetime
    last_heartbeat_at: datetime
    lease_expires_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class RunnerTaskClaimRequest(BaseModel):
    runner_id: str = Field(..., min_length=1, max_length=100)


class RunnerTaskClaimResponse(BaseModel):
    task_id: int
    project_id: int
    project_path: str
    prompt: str
    timeout_seconds: int
    task_type: TaskType
    model: Optional[str]
    reasoning_effort: Optional[str]
    sandbox: str
    require_clean_worktree: Optional[bool]
    test_command: Optional[str]
    smoke_check_command: Optional[str]
    default_branch: Optional[str]


class RunnerTaskLogUpload(BaseModel):
    runner_id: str = Field(..., min_length=1, max_length=100)
    content: str
    append: bool = True


class RunnerTaskArtifactsUpload(BaseModel):
    runner_id: str = Field(..., min_length=1, max_length=100)
    result: Optional[str] = None
    diff: Optional[str] = None
    git_status: Optional[str] = None
    diff_unstaged: Optional[str] = None
    diff_staged: Optional[str] = None
    untracked_files: Optional[str] = None
    test_output: Optional[str] = None
    task_report: Optional[str] = None


class RunnerTaskFinishRequest(BaseModel):
    runner_id: str = Field(..., min_length=1, max_length=100)
    status: TaskStatus
    exit_code: Optional[int] = None
    error_message: Optional[str] = None


class RunnerTaskCancelState(BaseModel):
    task_id: int
    cancel_requested: bool
    status: TaskStatus


class DeviceRegister(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=200)
    hostname: str = Field(..., min_length=1, max_length=200)
    os_name: str = Field(..., min_length=1, max_length=100)
    agent_version: str = Field(..., min_length=1, max_length=100)
    capabilities_json: Optional[str] = None


class DeviceHeartbeat(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=100)
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    hostname: Optional[str] = Field(default=None, min_length=1, max_length=200)
    os_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    agent_version: Optional[str] = Field(default=None, min_length=1, max_length=100)
    capabilities_json: Optional[str] = None


class DeviceRead(BaseModel):
    device_id: str
    display_name: str
    hostname: str
    os_name: str
    agent_version: str
    capabilities_json: Optional[str]
    status: DeviceStatus
    last_heartbeat_at: datetime
    lease_expires_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkspaceUpsert(BaseModel):
    workspace_key: str = Field(..., min_length=1, max_length=120)
    device_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    path_label: str = Field(..., min_length=1, max_length=300)
    enabled: bool = True
    default_model: Optional[str] = None
    default_reasoning_effort: Optional[str] = None
    default_sandbox: Optional[str] = None
    default_approval_policy: Optional[str] = None
    require_clean_worktree: Optional[bool] = None


class WorkspaceRead(BaseModel):
    id: int
    workspace_key: str
    device_id: str
    name: str
    path_label: str
    enabled: bool
    default_model: Optional[str]
    default_reasoning_effort: Optional[str]
    default_sandbox: Optional[str]
    default_approval_policy: Optional[str]
    require_clean_worktree: Optional[bool]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AppThreadCreate(BaseModel):
    project_id: int
    title: Optional[str] = None


class AppThreadUpdate(BaseModel):
    title: str = Field(..., min_length=1)


class AppThreadRead(BaseModel):
    id: int
    project_id: int
    title: str
    bridge_thread_id: Optional[str]
    app_thread_id: Optional[str]
    status: str
    last_error: Optional[str]
    latest_assistant_final: Optional[str] = None
    turn_count: int = 0
    created_at: datetime
    updated_at: datetime


class AppTurnCreate(BaseModel):
    message: str = Field(..., min_length=1)


class AppTurnRead(BaseModel):
    id: int
    app_thread_id: int
    user_message: str
    assistant_final: Optional[str]
    status: str
    error_message: Optional[str]
    bridge_turn_id: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[float] = None
    event_summary: Optional[dict] = None


class AppTurnRecoveryRead(BaseModel):
    recovered_count: int
    recovered_turn_ids: list[int]


class AppThreadCleanupRequest(BaseModel):
    status: str
    limit: int = Field(default=50, ge=1, le=200)


class AppThreadCleanupRead(BaseModel):
    archived_count: int
    archived_thread_ids: list[int]


class AppThreadFinalRead(BaseModel):
    app_thread_id: int
    assistant_final: Optional[str]


class AppThreadEventsRead(BaseModel):
    app_thread_id: int
    latest_turn_id: Optional[int]
    event_summary: Optional[dict]
