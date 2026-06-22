from __future__ import annotations

import os
from dataclasses import dataclass


TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off", ""}


@dataclass(frozen=True)
class Settings:
    agent_command_mode: bool = False

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


def get_settings() -> Settings:
    return Settings(agent_command_mode=parse_bool_env("AGENT_COMMAND_MODE"))
