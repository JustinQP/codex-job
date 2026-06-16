from __future__ import annotations

from pathlib import Path
import os

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
    whitelist_error = _validate_project_whitelist(project_path)
    if whitelist_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=whitelist_error,
        )
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
        test_command=payload.test_command,
        smoke_check_command=payload.smoke_check_command,
        default_branch=payload.default_branch,
        require_clean_worktree=payload.require_clean_worktree,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def _validate_project_whitelist(project_path: Path) -> str | None:
    raw_roots = os.environ.get("PROJECT_PATH_WHITELIST")
    if not raw_roots:
        return None

    allowed_roots = [
        Path(raw_root).expanduser().resolve()
        for raw_root in raw_roots.split(os.pathsep)
        if raw_root.strip()
    ]
    if not allowed_roots:
        return None

    for allowed_root in allowed_roots:
        try:
            project_path.relative_to(allowed_root)
            return None
        except ValueError:
            continue
    return "project path is outside PROJECT_PATH_WHITELIST"


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


def to_project_read(project: Project):
    from backend.schemas import ProjectRead

    if project.id is None:
        raise ValueError("project id is required")
    return ProjectRead(
        id=project.id,
        name=project.name,
        path_label=Path(project.path).name or "project",
        enabled=project.enabled,
        test_command=project.test_command,
        smoke_check_command=project.smoke_check_command,
        default_branch=project.default_branch,
        require_clean_worktree=project.require_clean_worktree,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )
