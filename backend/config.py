from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    run_artifact_max_file_bytes: int = 2 * 1024 * 1024
    run_artifact_max_total_bytes: int = 8 * 1024 * 1024


def parse_int_env(name: str, *, default: int, minimum: int = 1) -> int:
    raw_value = os.environ.get(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum:
        raise ValueError(f"{name} must be greater than or equal to {minimum}")
    return value


def get_settings() -> Settings:
    return Settings(
        run_artifact_max_file_bytes=parse_int_env(
            "RUN_ARTIFACT_MAX_FILE_BYTES",
            default=Settings.run_artifact_max_file_bytes,
        ),
        run_artifact_max_total_bytes=parse_int_env(
            "RUN_ARTIFACT_MAX_TOTAL_BYTES",
            default=Settings.run_artifact_max_total_bytes,
        ),
    )
