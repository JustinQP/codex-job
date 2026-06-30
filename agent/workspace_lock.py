from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from threading import Lock
from typing import Iterator


DEFAULT_STALE_AFTER_SECONDS = 12 * 60 * 60


class LocalWorkspaceLock:
    def __init__(
        self,
        *,
        lock_dir: Path | None = None,
        stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS,
    ) -> None:
        self._guard = Lock()
        self._locks: dict[Path, str] = {}
        self._lock_files: dict[Path, Path] = {}
        self._lock_dir = lock_dir
        self._stale_after_seconds = stale_after_seconds

    @contextmanager
    def acquire(self, path: Path, owner: str, *, write: bool) -> Iterator[None]:
        if not write:
            yield
            return
        self.acquire_write(path, owner)
        try:
            yield
        finally:
            self.release(path, owner)

    def acquire_write(self, path: Path, owner: str) -> None:
        resolved = path.resolve()
        with self._guard:
            existing = self._locks.get(resolved)
            if existing is not None and existing != owner:
                raise RuntimeError(f"workspace busy: {resolved}")
            lock_file = self._acquire_file_lock(resolved, owner)
            self._locks[resolved] = owner
            if lock_file is not None:
                self._lock_files[resolved] = lock_file

    def release(self, path: Path, owner: str) -> None:
        resolved = path.resolve()
        with self._guard:
            if self._locks.get(resolved) == owner:
                self._locks.pop(resolved, None)
                lock_file = self._lock_files.pop(resolved, None)
                if lock_file is not None:
                    _release_file_lock(lock_file, owner)

    def _acquire_file_lock(self, path: Path, owner: str) -> Path | None:
        if self._lock_dir is None:
            return None
        self._lock_dir.mkdir(parents=True, exist_ok=True)
        lock_file = self._lock_dir / f"{_lock_key(path)}.lock"
        payload = {
            "owner": owner,
            "path": str(path),
            "pid": os.getpid(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        while True:
            try:
                fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError as exc:
                if _remove_stale_lock(lock_file, self._stale_after_seconds):
                    continue
                existing_owner = _read_lock_owner(lock_file)
                if existing_owner == owner:
                    return lock_file
                raise RuntimeError(f"workspace busy: {path}") from exc
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as file:
                file.write(body)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            return lock_file


def _lock_key(path: Path) -> str:
    return hashlib.sha256(str(path).casefold().encode("utf-8")).hexdigest()


def _remove_stale_lock(lock_file: Path, stale_after_seconds: float) -> bool:
    try:
        age_seconds = datetime.now(timezone.utc).timestamp() - lock_file.stat().st_mtime
    except FileNotFoundError:
        return True
    if age_seconds < stale_after_seconds:
        return False
    try:
        lock_file.unlink()
    except FileNotFoundError:
        return True
    return True


def _read_lock_owner(lock_file: Path) -> str | None:
    try:
        raw = json.loads(lock_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    owner = raw.get("owner") if isinstance(raw, dict) else None
    return owner if isinstance(owner, str) else None


def _release_file_lock(lock_file: Path, owner: str) -> None:
    existing_owner = _read_lock_owner(lock_file)
    if existing_owner not in {None, owner}:
        return
    try:
        lock_file.unlink()
    except FileNotFoundError:
        return


def is_write_sandbox(sandbox: str | None) -> bool:
    return (sandbox or "").replace("_", "-").lower() == "workspace-write"
