from __future__ import annotations

import os
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
JOBS_DIR = DATA_DIR / "jobs"
POLL_INTERVAL_SECONDS = _env_float("RUNNER_POLL_INTERVAL_SECONDS", 5.0)
DEFAULT_TIMEOUT_SECONDS = _env_int("TASK_TIMEOUT_SECONDS", 7200)
GIT_DIFF_TIMEOUT_SECONDS = _env_int("GIT_DIFF_TIMEOUT_SECONDS", 60)
