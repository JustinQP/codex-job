from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from backend.db import get_session
from backend.dependencies import require_api_token
from backend.schemas import WorkspaceRead, WorkspaceUpdate
from backend.services import workspace_service


router = APIRouter()


@router.get("/workspaces", response_model=list[WorkspaceRead])
def list_workspaces(
    device_id: str | None = None,
    include_disabled: bool = True,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return workspace_service.list_workspaces(
        session,
        device_id=device_id,
        include_disabled=include_disabled,
    )


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceRead)
def get_workspace(
    workspace_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return workspace_service.get_workspace_or_404(session, workspace_id)


@router.patch("/workspaces/{workspace_id}", response_model=WorkspaceRead)
def update_workspace(
    workspace_id: int,
    payload: WorkspaceUpdate,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return workspace_service.update_workspace(session, workspace_id, payload)
