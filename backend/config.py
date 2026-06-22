from __future__ import annotations

import os
from dataclasses import dataclass


TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off", ""}


@dataclass(frozen=True)
class Settings:
    agent_command_mode: bool = False
    run_artifact_max_file_bytes: int = 2 * 1024 * 1024
    run_artifact_max_total_bytes: int = 8 * 1024 * 1024

    @property
    def execution_mode(self) -> str:
        return "agent_command" if self.agent_command_mode else "legacy_runner"


def parse_bool_env(name: str, *, default: bool = False) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    value = raw_value.strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    raise ValueError(
        f"{name} must be one of: "
        f"{', '.join(sorted((TRUE_VALUES | FALSE_VALUES) - {''}))}"
    )


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
        agent_command_mode=parse_bool_env("AGENT_COMMAND_MODE"),
        run_artifact_max_file_bytes=parse_int_env(
            "RUN_ARTIFACT_MAX_FILE_BYTES",
            default=Settings.run_artifact_max_file_bytes,
        ),
        run_artifact_max_total_bytes=parse_int_env(
            "RUN_ARTIFACT_MAX_TOTAL_BYTES",
            default=Settings.run_artifact_max_total_bytes,
        ),
    )
