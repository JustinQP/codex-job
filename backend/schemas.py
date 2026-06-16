from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.models import TaskStatus, TaskType


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    path: str = Field(..., min_length=1)
    enabled: bool = True
    test_command: Optional[str] = None
    smoke_check_command: Optional[str] = None
    default_branch: Optional[str] = None
    require_clean_worktree: Optional[bool] = None


class ProjectRead(BaseModel):
    id: int
    name: str
    path_label: str
    enabled: bool
    test_command: Optional[str]
    smoke_check_command: Optional[str]
    default_branch: Optional[str]
    require_clean_worktree: Optional[bool]
    created_at: datetime
    updated_at: datetime


class TaskCreate(BaseModel):
    project_id: int
    prompt: str = Field(..., min_length=1)
    timeout_seconds: int = Field(default=7200, ge=30, le=21600)
    task_type: TaskType = TaskType.IMPLEMENT


class TaskRead(BaseModel):
    id: int
    project_id: int
    prompt: str
    task_type: TaskType
    status: TaskStatus
    timeout_seconds: int
    exit_code: Optional[int]
    error_message: Optional[str]
    cancel_requested: bool
    runner_pid: Optional[int]
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


class RunnerHeartbeat(BaseModel):
    runner_id: str = Field(..., min_length=1, max_length=100)
    pid: int = Field(..., ge=1)
    hostname: str = Field(..., min_length=1, max_length=200)


class RunnerRead(BaseModel):
    runner_id: str
    pid: int
    hostname: str
    status: str
    registered_at: datetime
    last_heartbeat_at: datetime

    model_config = ConfigDict(from_attributes=True)
