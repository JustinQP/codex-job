from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from backend.db import get_session
from backend.dependencies import require_api_token
from backend.schemas import ProjectCreate, ProjectRead, ProjectUpdate
from backend.services import project_service


router = APIRouter()


@router.post("/projects", response_model=ProjectRead)
def create_project(
    payload: ProjectCreate,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    project = project_service.create_project(session, payload)
    return project_service.to_project_read(project)


@router.get("/projects", response_model=list[ProjectRead])
def list_projects(
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return [
        project_service.to_project_read(project)
        for project in project_service.list_projects(session)
    ]


@router.patch("/projects/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    project = project_service.update_project(session, project_id, payload)
    return project_service.to_project_read(project)
