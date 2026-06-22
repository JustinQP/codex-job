from __future__ import annotations

import pytest

from backend.config import get_settings, parse_bool_env


def test_agent_command_mode_defaults_to_legacy(monkeypatch) -> None:
    monkeypatch.delenv("AGENT_COMMAND_MODE", raising=False)

    settings = get_settings()

    assert settings.agent_command_mode is False
    assert settings.execution_mode == "legacy_runner"


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_parse_bool_env_accepts_truthy_values(monkeypatch, value: str) -> None:
    monkeypatch.setenv("AGENT_COMMAND_MODE", value)

    assert parse_bool_env("AGENT_COMMAND_MODE") is True


@pytest.mark.parametrize("value", ["0", "false", "FALSE", "no", "off", ""])
def test_parse_bool_env_accepts_falsey_values(monkeypatch, value: str) -> None:
    monkeypatch.setenv("AGENT_COMMAND_MODE", value)

    assert parse_bool_env("AGENT_COMMAND_MODE", default=True) is False


def test_parse_bool_env_rejects_invalid_value(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_COMMAND_MODE", "maybe")

    with pytest.raises(ValueError, match="AGENT_COMMAND_MODE"):
        parse_bool_env("AGENT_COMMAND_MODE")
