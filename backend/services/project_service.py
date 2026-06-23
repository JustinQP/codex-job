from __future__ import annotations

from pathlib import Path
import os

from fastapi import HTTPException, status
from sqlmodel import Session, select

from backend.models import Project, WorkspaceBindingStatus, utc_now
from backend.schemas import ProjectCreate


def create_project(session: Session, payload: ProjectCreate) -> Project:
    project_name = payload.name.strip()
    if not project_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project name cannot be empty",
        )

    workspace = None
    if payload.workspace_id is not None:
        from backend.models import Workspace

        workspace = session.get(Workspace, payload.workspace_id)
        if workspace is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="workspace not found",
            )
        project_path_value = payload.path.strip()
        binding_status = WorkspaceBindingStatus.BOUND
    else:
        project_path = Path(payload.path).expanduser().resolve()
        whitelist_error = validate_project_whitelist(project_path)
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
        project_path_value = str(project_path)
        binding_status = WorkspaceBindingStatus.UNBOUND
    project = Project(
        name=project_name,
        path=project_path_value,
        enabled=payload.enabled,
        test_command=payload.test_command,
        smoke_check_command=payload.smoke_check_command,
        default_branch=payload.default_branch,
        require_clean_worktree=payload.require_clean_worktree,
        default_model=payload.default_model,
        default_reasoning_effort=payload.default_reasoning_effort,
        default_sandbox=payload.default_sandbox,
        workspace_id=payload.workspace_id,
        workspace_binding_status=binding_status,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def validate_project_whitelist(project_path: Path) -> str | None:
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


def list_unbound_projects(session: Session) -> list[Project]:
    return list(
        session.exec(
            select(Project)
            .where(Project.workspace_binding_status == WorkspaceBindingStatus.UNBOUND)
            .order_by(Project.id)
        ).all()
    )


def bind_project_workspace(session: Session, project_id: int, workspace_id: int) -> Project:
    from backend.models import Workspace

    project = get_project_or_404(session, project_id)
    if session.get(Workspace, workspace_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="workspace not found",
        )
    project.workspace_id = workspace_id
    project.workspace_binding_status = WorkspaceBindingStatus.BOUND
    project.updated_at = utc_now()
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def ensure_project_workspace(
    session: Session,
    project: Project,
    workspace_id: int,
) -> Project:
    from backend.models import Workspace

    if session.get(Workspace, workspace_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="workspace not found",
        )
    if project.workspace_id is None:
        project.workspace_id = workspace_id
        project.workspace_binding_status = WorkspaceBindingStatus.BOUND
        project.updated_at = utc_now()
        session.add(project)
        session.flush()
        return project
    if project.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "project_workspace_mismatch",
                "message": "project is bound to a different workspace",
                "project_id": project.id,
                "project_workspace_id": project.workspace_id,
                "requested_workspace_id": workspace_id,
            },
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
        workspace_id=project.workspace_id,
        workspace_binding_status=project.workspace_binding_status,
        default_model=project.default_model,
        default_reasoning_effort=project.default_reasoning_effort,
        default_sandbox=project.default_sandbox,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )
