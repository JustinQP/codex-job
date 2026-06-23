from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import HTTPException, status
from sqlmodel import Session

from backend.config import get_settings
from backend.models import Run
from backend.schemas import RunArtifactUpload, RunArtifactUploadRead
from backend.services import run_service


MAX_RUN_ARTIFACT_FILE_BYTES = 2 * 1024 * 1024
MAX_RUN_ARTIFACT_TOTAL_BYTES = 8 * 1024 * 1024

ALLOWED_RUN_ARTIFACTS = {
    "result": "result.md",
    "diff": "diff.patch",
    "git_status": "git-status.txt",
    "diff_unstaged": "diff-unstaged.patch",
    "diff_staged": "diff-staged.patch",
    "untracked_files": "untracked-files.txt",
    "test_output": "test-output.txt",
    "run_report": "run-report.md",
}


def upload_run_artifact(
    session: Session,
    run_id: int,
    payload: RunArtifactUpload,
) -> RunArtifactUploadRead:
    run = run_service.get_run_or_404(session, run_id)
    _ensure_run_binding(run, payload)
    filename = _expected_filename(payload)
    content_bytes = payload.content.encode("utf-8")
    _validate_manifest(payload, content_bytes)

    artifact_path = _artifact_path(run.id, filename)
    max_total_bytes = _max_total_bytes()
    existing_bytes = artifact_path.read_bytes() if artifact_path.exists() else None
    if existing_bytes is not None:
        existing_hash = hashlib.sha256(existing_bytes).hexdigest()
        if existing_hash == payload.sha256:
            _assign_run_paths(run, artifact_path, payload.artifact_type)
            session.add(run)
            session.commit()
            return _read(payload, filename, duplicate=True)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "run_artifact_hash_conflict"},
        )

    total_bytes = _current_total_bytes(run.id) + len(content_bytes)
    if total_bytes > max_total_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail={
                "code": "run_artifacts_total_too_large",
                "max_total_bytes": max_total_bytes,
            },
        )

    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_bytes(content_bytes)
    _assign_run_paths(run, artifact_path, payload.artifact_type)
    session.add(run)
    session.commit()
    return _read(payload, filename, duplicate=False)


def _ensure_run_binding(run: Run, payload: RunArtifactUpload) -> None:
    if run.device_id != payload.device_id or run.command_id != payload.command_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "run_artifact_binding_mismatch"},
        )


def _expected_filename(payload: RunArtifactUpload) -> str:
    filename = ALLOWED_RUN_ARTIFACTS.get(payload.artifact_type)
    if filename is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "run_artifact_type_not_allowed"},
        )
    if payload.filename != filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "run_artifact_filename_not_allowed",
                "expected_filename": filename,
            },
        )
    return filename


def _validate_manifest(payload: RunArtifactUpload, content_bytes: bytes) -> None:
    actual_size = len(content_bytes)
    max_file_bytes = _max_file_bytes()
    if payload.size_bytes != actual_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "run_artifact_size_mismatch",
                "actual_size": actual_size,
            },
        )
    if actual_size > max_file_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail={
                "code": "run_artifact_file_too_large",
                "max_file_bytes": max_file_bytes,
            },
        )
    actual_hash = hashlib.sha256(content_bytes).hexdigest()
    if payload.sha256.lower() != actual_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "run_artifact_hash_mismatch"},
        )


def _artifact_path(run_id: int | None, filename: str) -> Path:
    if run_id is None:
        raise ValueError("run id is required")
    return run_service._artifact_paths(run_id)[0].parent / filename


def _current_total_bytes(run_id: int | None) -> int:
    if run_id is None:
        raise ValueError("run id is required")
    job_dir = run_service._artifact_paths(run_id)[0].parent
    if not job_dir.exists():
        return 0
    return sum(path.stat().st_size for path in job_dir.iterdir() if path.is_file())


def _assign_run_paths(run: Run, artifact_path: Path, artifact_type: str) -> None:
    if artifact_type == "result":
        run.result_file = str(artifact_path)
    elif artifact_type == "diff":
        run.diff_file = str(artifact_path)


def _max_file_bytes() -> int:
    return get_settings().run_artifact_max_file_bytes


def _max_total_bytes() -> int:
    return get_settings().run_artifact_max_total_bytes


def _read(payload: RunArtifactUpload, filename: str, *, duplicate: bool) -> RunArtifactUploadRead:
    return RunArtifactUploadRead(
        accepted=True,
        duplicate=duplicate,
        artifact_type=payload.artifact_type,
        filename=filename,
        sequence=payload.sequence,
        size_bytes=payload.size_bytes,
        sha256=payload.sha256.lower(),
        max_file_bytes=_max_file_bytes(),
        max_total_bytes=_max_total_bytes(),
    )
