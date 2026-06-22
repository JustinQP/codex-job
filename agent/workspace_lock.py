from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import Iterator


class LocalWorkspaceLock:
    def __init__(self) -> None:
        self._guard = Lock()
        self._locks: dict[Path, str] = {}

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
            self._locks[resolved] = owner

    def release(self, path: Path, owner: str) -> None:
        resolved = path.resolve()
        with self._guard:
            if self._locks.get(resolved) == owner:
                self._locks.pop(resolved, None)


def is_write_sandbox(sandbox: str | None) -> bool:
    return (sandbox or "").replace("_", "-").lower() == "workspace-write"
