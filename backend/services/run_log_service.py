from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, status
from sqlmodel import Session

from backend.models import Run
from backend.schemas import RunLogChunkUpload, RunLogChunkUploadRead
from backend.services import run_service


MAX_LOG_CHUNK_BYTES = 64 * 1024
MAX_RUN_LOG_BYTES = 10 * 1024 * 1024


def upload_run_log_chunk(
    session: Session,
    run_id: int,
    payload: RunLogChunkUpload,
) -> RunLogChunkUploadRead:
    run = run_service.get_run_or_404(session, run_id)
    _ensure_run_binding(run, payload)
    content_bytes = payload.content.encode("utf-8")
    if len(content_bytes) > MAX_LOG_CHUNK_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail={
                "code": "run_log_chunk_too_large",
                "current_offset": _current_log_offset(run),
                "max_chunk_bytes": MAX_LOG_CHUNK_BYTES,
            },
        )

    log_path = _ensure_log_path(run)
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
    run.log_file = str(log_path)
    session.add(run)
    session.commit()
    return _read(
        accepted=True,
        duplicate=False,
        current_offset=current_offset + len(content_bytes),
    )


def _ensure_run_binding(run: Run, payload: RunLogChunkUpload) -> None:
    if run.device_id != payload.device_id or run.command_id != payload.command_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "run_log_binding_mismatch"},
        )


def _ensure_log_path(run: Run) -> Path:
    if run.log_file:
        return Path(run.log_file)
    if run.id is None:
        raise ValueError("run id is required")
    log_path, _, _ = run_service._artifact_paths(run.id)
    return log_path


def _current_log_offset(run: Run) -> int:
    log_path = _ensure_log_path(run)
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
