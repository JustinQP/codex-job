from __future__ import annotations

import subprocess
from threading import Lock


class ProcessRegistry:
    def __init__(self) -> None:
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._lock = Lock()

    def register(self, command_id: str, process: subprocess.Popen[str]) -> None:
        with self._lock:
            self._processes[command_id] = process

    def unregister(self, command_id: str) -> None:
        with self._lock:
            self._processes.pop(command_id, None)

    def get(self, command_id: str) -> subprocess.Popen[str] | None:
        with self._lock:
            return self._processes.get(command_id)

    def is_running(self, command_id: str) -> bool:
        process = self.get(command_id)
        return process is not None and process.poll() is None
