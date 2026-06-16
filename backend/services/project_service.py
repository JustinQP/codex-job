from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, status
from sqlmodel import Session, select

from backend.models import Project, utc_now
from backend.schemas import ProjectCreate


def create_project(session: Session, payload: ProjectCreate) -> Project:
    project_name = payload.name.strip()
    if not project_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project name cannot be empty",
        )

    project_path = Path(payload.path).expanduser().resolve()
    if not project_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project path does not exist",
        )
    if not project_path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project path must be a directory",
        )

    project = Project(
        name=project_name,
        path=str(project_path),
        enabled=payload.enabled,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def list_projects(session: Session) -> list[Project]:
    return list(session.exec(select(Project).order_by(Project.id)).all())


def get_project_or_404(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="project not found",
        )
    return project
