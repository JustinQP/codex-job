from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, status
from sqlmodel import Session

from backend.models import Task
from backend.schemas import RunLogChunkUpload, RunLogChunkUploadRead
from backend.services import task_service


MAX_LOG_CHUNK_BYTES = 64 * 1024
MAX_RUN_LOG_BYTES = 10 * 1024 * 1024


def upload_run_log_chunk(
    session: Session,
    task_id: int,
    payload: RunLogChunkUpload,
) -> RunLogChunkUploadRead:
    task = task_service.get_task_or_404(session, task_id)
    _ensure_task_binding(task, payload)
    content_bytes = payload.content.encode("utf-8")
    if len(content_bytes) > MAX_LOG_CHUNK_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail={
                "code": "run_log_chunk_too_large",
                "current_offset": _current_log_offset(task),
                "max_chunk_bytes": MAX_LOG_CHUNK_BYTES,
            },
        )

    log_path = _ensure_log_path(task)
    current_offset = log_path.stat().st_size if log_path.exists() else 0
    if payload.offset < current_offset:
        existing = log_path.read_bytes()[payload.offset:payload.offset + len(content_bytes)]
        if existing == content_bytes:
            return _read(accepted=True, duplicate=True, current_offset=current_offset)
        raise _offset_error(current_offset)
    if payload.offset > current_offset:
        raise _offset_error(current_offset)
    if current_offset + len(content_bytes) > MAX_RUN_LOG_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail={
                "code": "run_log_too_large",
                "current_offset": current_offset,
                "max_log_bytes": MAX_RUN_LOG_BYTES,
            },
        )

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log_file:
        log_file.write(content_bytes)
    task.log_file = str(log_path)
    session.add(task)
    session.commit()
    return _read(
        accepted=True,
        duplicate=False,
        current_offset=current_offset + len(content_bytes),
    )


def _ensure_task_binding(task: Task, payload: RunLogChunkUpload) -> None:
    if task.device_id != payload.device_id or task.command_id != payload.command_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "run_log_binding_mismatch"},
        )


def _ensure_log_path(task: Task) -> Path:
    if task.log_file:
        return Path(task.log_file)
    if task.id is None:
        raise ValueError("task id is required")
    log_path, _, _ = task_service._artifact_paths(task.id)
    return log_path


def _current_log_offset(task: Task) -> int:
    log_path = _ensure_log_path(task)
    return log_path.stat().st_size if log_path.exists() else 0


def _offset_error(current_offset: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "run_log_offset_mismatch",
            "current_offset": current_offset,
        },
    )


def _read(*, accepted: bool, duplicate: bool, current_offset: int) -> RunLogChunkUploadRead:
    return RunLogChunkUploadRead(
        accepted=accepted,
        duplicate=duplicate,
        current_offset=current_offset,
        max_chunk_bytes=MAX_LOG_CHUNK_BYTES,
        max_log_bytes=MAX_RUN_LOG_BYTES,
    )
