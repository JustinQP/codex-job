from __future__ import annotations

import pytest

from backend.config import get_settings, parse_int_env


def test_settings_only_exposes_run_artifact_limits(monkeypatch) -> None:
    monkeypatch.setenv("RUN_ARTIFACT_MAX_FILE_BYTES", "123")
    monkeypatch.setenv("RUN_ARTIFACT_MAX_TOTAL_BYTES", "456")

    settings = get_settings()

    assert settings.run_artifact_max_file_bytes == 123
    assert settings.run_artifact_max_total_bytes == 456
    assert not hasattr(settings, "agent_command_mode")
    assert not hasattr(settings, "execution_mode")


def test_parse_int_env_rejects_invalid_values(monkeypatch) -> None:
    monkeypatch.setenv("RUN_ARTIFACT_MAX_FILE_BYTES", "abc")

    with pytest.raises(ValueError, match="RUN_ARTIFACT_MAX_FILE_BYTES"):
        parse_int_env("RUN_ARTIFACT_MAX_FILE_BYTES", default=1)
