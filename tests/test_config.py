from __future__ import annotations

import pytest

from backend.config import get_settings, parse_bool_env, parse_int_env


def test_agent_command_mode_defaults_to_legacy(monkeypatch) -> None:
    monkeypatch.delenv("AGENT_COMMAND_MODE", raising=False)
    monkeypatch.delenv("RUN_ARTIFACT_MAX_FILE_BYTES", raising=False)
    monkeypatch.delenv("RUN_ARTIFACT_MAX_TOTAL_BYTES", raising=False)

    settings = get_settings()

    assert settings.agent_command_mode is False
    assert settings.execution_mode == "legacy_runner"
    assert settings.run_artifact_max_file_bytes == 2 * 1024 * 1024
    assert settings.run_artifact_max_total_bytes == 8 * 1024 * 1024


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


def test_run_artifact_size_limits_can_be_configured(monkeypatch) -> None:
    monkeypatch.setenv("RUN_ARTIFACT_MAX_FILE_BYTES", "1024")
    monkeypatch.setenv("RUN_ARTIFACT_MAX_TOTAL_BYTES", "2048")

    settings = get_settings()

    assert settings.run_artifact_max_file_bytes == 1024
    assert settings.run_artifact_max_total_bytes == 2048


def test_parse_int_env_rejects_invalid_values(monkeypatch) -> None:
    monkeypatch.setenv("LIMIT", "abc")
    with pytest.raises(ValueError, match="LIMIT"):
        parse_int_env("LIMIT", default=1)

    monkeypatch.setenv("LIMIT", "0")
    with pytest.raises(ValueError, match="greater than or equal"):
        parse_int_env("LIMIT", default=1)
