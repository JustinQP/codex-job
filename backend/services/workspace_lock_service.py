from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from backend.models import WorkspaceExecutionLock, utc_now


WORKSPACE_LOCK_LEASE_SECONDS = 6 * 60 * 60
LOCK_TYPE_WRITE = "write"


def acquire_workspace_lock(
    session: Session,
    *,
    workspace_id: int,
    owner_type: str,
    owner_id: str,
    lock_type: str = LOCK_TYPE_WRITE,
    sandbox: str | None = None,
) -> WorkspaceExecutionLock | None:
    if not _requires_write_lock(sandbox):
        return None
    _recover_expired_locks(session)
    existing = _active_lock_for_workspace(session, workspace_id)
    if existing is not None:
        if existing.owner_type == owner_type and existing.owner_id == owner_id:
            return existing
        _raise_workspace_busy(existing)

    now = utc_now()
    lock = WorkspaceExecutionLock(
        workspace_id=workspace_id,
        owner_type=owner_type,
        owner_id=owner_id,
        lock_type=lock_type,
        lease_expires_at=now + timedelta(seconds=WORKSPACE_LOCK_LEASE_SECONDS),
        created_at=now,
        updated_at=now,
    )
    session.add(lock)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        existing = _active_lock_for_workspace(session, workspace_id)
        if existing is not None:
            _raise_workspace_busy(existing)
        raise
    return lock


def ensure_workspace_available(
    session: Session,
    *,
    workspace_id: int,
    sandbox: str | None,
) -> None:
    if not _requires_write_lock(sandbox):
        return
    _recover_expired_locks(session)
    existing = _active_lock_for_workspace(session, workspace_id)
    if existing is not None:
        _raise_workspace_busy(existing)


def release_workspace_lock(
    session: Session,
    *,
    owner_type: str,
    owner_id: str,
) -> bool:
    locks = list(
        session.exec(
            select(WorkspaceExecutionLock).where(
                WorkspaceExecutionLock.owner_type == owner_type,
                WorkspaceExecutionLock.owner_id == owner_id,
            )
        ).all()
    )
    if not locks:
        return False
    for lock in locks:
        session.delete(lock)
    session.commit()
    return True


def _recover_expired_locks(session: Session) -> None:
    expired = list(
        session.exec(
            select(WorkspaceExecutionLock).where(
                WorkspaceExecutionLock.lease_expires_at < utc_now(),
            )
        ).all()
    )
    if not expired:
        return
    for lock in expired:
        session.delete(lock)
    session.flush()


def _active_lock_for_workspace(session: Session, workspace_id: int) -> WorkspaceExecutionLock | None:
    return session.exec(
        select(WorkspaceExecutionLock).where(
            WorkspaceExecutionLock.workspace_id == workspace_id,
            WorkspaceExecutionLock.lease_expires_at >= utc_now(),
        )
    ).first()


def _requires_write_lock(sandbox: str | None) -> bool:
    normalized = (sandbox or "").replace("_", "-").lower()
    return normalized == "workspace-write"


def _raise_workspace_busy(lock: WorkspaceExecutionLock) -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "workspace_busy",
            "message": "workspace is already locked by an active write execution",
            "workspace_id": lock.workspace_id,
            "owner_type": lock.owner_type,
            "owner_id": lock.owner_id,
            "lock_type": lock.lock_type,
            "lease_expires_at": lock.lease_expires_at.isoformat(),
        },
    )


def lock_to_dict(lock: WorkspaceExecutionLock) -> dict[str, Any]:
    return {
        "workspace_id": lock.workspace_id,
        "owner_type": lock.owner_type,
        "owner_id": lock.owner_id,
        "lock_type": lock.lock_type,
        "lease_expires_at": lock.lease_expires_at.isoformat(),
    }
