from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.models import TaskStatus


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    path: str = Field(..., min_length=1)
    enabled: bool = True


class ProjectRead(BaseModel):
    id: int
    name: str
    path: str
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskCreate(BaseModel):
    project_id: int
    prompt: str = Field(..., min_length=1)
    timeout_seconds: int = Field(default=7200, ge=30, le=21600)


class TaskRead(BaseModel):
    id: int
    project_id: int
    prompt: str
    status: TaskStatus
    timeout_seconds: int
    exit_code: Optional[int]
    error_message: Optional[str]
    log_url: str
    result_url: str
    diff_url: str
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
