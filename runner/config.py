from __future__ import annotations

import os
import socket
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def _env_path(name: str, default: Path) -> Path:
    return Path(os.environ.get(name, str(default))).expanduser().resolve()


def _env_int(name: str, default: int) -> int:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return int(raw_value)


def _env_float(name: str, default: float) -> float:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return float(raw_value)


DATA_DIR = _env_path("CODEX_RUNNER_DATA_DIR", ROOT_DIR / "data")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
RUNNER_ID = os.environ.get("RUNNER_ID", f"{socket.gethostname()}-{os.getpid()}")
RUNNER_TOKEN = os.environ.get("RUNNER_TOKEN") or os.environ.get("API_TOKEN")
JOBS_DIR = _env_path("RUNNER_JOBS_DIR", DATA_DIR / "runner-jobs" / RUNNER_ID)
POLL_INTERVAL_SECONDS = _env_float("RUNNER_POLL_INTERVAL_SECONDS", 5.0)
DEFAULT_TIMEOUT_SECONDS = _env_int("TASK_TIMEOUT_SECONDS", 7200)
GIT_DIFF_TIMEOUT_SECONDS = _env_int("GIT_DIFF_TIMEOUT_SECONDS", 60)
RUNNER_LOCK_FILE = DATA_DIR / "runner.lock"


def require_clean_worktree() -> bool:
    raw_value = os.environ.get("REQUIRE_CLEAN_WORKTREE", "true")
    return raw_value.strip().lower() not in {"0", "false", "no", "off"}
