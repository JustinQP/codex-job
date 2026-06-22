from __future__ import annotations

from fastapi import HTTPException, status
from sqlmodel import Session, select

from backend.models import Device, Workspace, utc_now
from backend.schemas import (
    WorkspaceRead,
    WorkspaceSyncRead,
    WorkspaceSyncRequest,
    WorkspaceUpsert,
)


def upsert_workspace(session: Session, payload: WorkspaceUpsert) -> Workspace:
    device = session.get(Device, payload.device_id)
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="device not found",
        )

    workspace = session.exec(
        select(Workspace).where(
            Workspace.device_id == payload.device_id,
            Workspace.workspace_key == payload.workspace_key,
        )
    ).first()
    now = utc_now()
    if workspace is None:
        workspace = Workspace(
            workspace_key=payload.workspace_key,
            device_id=payload.device_id,
            name=payload.name,
            path_label=payload.path_label,
            enabled=payload.enabled,
            default_model=payload.default_model,
            default_reasoning_effort=payload.default_reasoning_effort,
            default_sandbox=payload.default_sandbox,
            default_approval_policy=payload.default_approval_policy,
            require_clean_worktree=payload.require_clean_worktree,
            created_at=now,
            updated_at=now,
        )
    else:
        workspace.name = payload.name
        workspace.path_label = payload.path_label
        workspace.enabled = payload.enabled
        workspace.default_model = payload.default_model
        workspace.default_reasoning_effort = payload.default_reasoning_effort
        workspace.default_sandbox = payload.default_sandbox
        workspace.default_approval_policy = payload.default_approval_policy
        workspace.require_clean_worktree = payload.require_clean_worktree
        workspace.updated_at = now
    session.add(workspace)
    session.commit()
    session.refresh(workspace)
    return workspace


def list_workspaces(
    session: Session,
    *,
    device_id: str | None = None,
    include_disabled: bool = True,
) -> list[Workspace]:
    statement = select(Workspace)
    if device_id is not None:
        statement = statement.where(Workspace.device_id == device_id)
    if not include_disabled:
        statement = statement.where(Workspace.enabled == True)  # noqa: E712
    statement = statement.order_by(Workspace.device_id, Workspace.name)
    return list(session.exec(statement).all())


def get_workspace_or_404(session: Session, workspace_id: int) -> Workspace:
    workspace = session.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="workspace not found",
        )
    return workspace


def ensure_workspace_enabled(session: Session, workspace_id: int) -> Workspace:
    workspace = get_workspace_or_404(session, workspace_id)
    if not workspace.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="workspace is disabled",
        )
    return workspace


def sync_device_workspaces(session: Session, payload: WorkspaceSyncRequest) -> WorkspaceSyncRead:
    if session.get(Device, payload.device_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="device not found",
        )

    seen_keys = set()
    synced: list[Workspace] = []
    for item in payload.workspaces:
        if item.workspace_key in seen_keys:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"duplicate workspace key: {item.workspace_key}",
            )
        seen_keys.add(item.workspace_key)
        synced.append(
            upsert_workspace(
                session,
                WorkspaceUpsert(
                    device_id=payload.device_id,
                    workspace_key=item.workspace_key,
                    name=item.name,
                    path_label=item.path_label,
                    enabled=item.enabled,
                    default_model=item.default_model,
                    default_reasoning_effort=item.default_reasoning_effort,
                    default_sandbox=item.default_sandbox,
                    default_approval_policy=item.default_approval_policy,
                    require_clean_worktree=item.require_clean_worktree,
                ),
            )
        )

    disabled_count = 0
    now = utc_now()
    existing = session.exec(
        select(Workspace).where(Workspace.device_id == payload.device_id)
    ).all()
    for workspace in existing:
        if workspace.workspace_key in seen_keys or not workspace.enabled:
            continue
        workspace.enabled = False
        workspace.updated_at = now
        session.add(workspace)
        disabled_count += 1
    if disabled_count:
        session.commit()

    return WorkspaceSyncRead(
        synced_count=len(synced),
        disabled_count=disabled_count,
        workspaces=[
            WorkspaceRead.model_validate(workspace)
            for workspace in list_workspaces(session, device_id=payload.device_id)
        ],
    )
