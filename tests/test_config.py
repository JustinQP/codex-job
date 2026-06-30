from __future__ import annotations

from pathlib import Path

import pytest

from backend.config import get_settings, parse_int_env


ROOT = Path(__file__).resolve().parents[1]


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


def test_db_init_fails_fast_for_legacy_task_tables(monkeypatch, tmp_path) -> None:
    import importlib
    import sqlite3

    db_path = tmp_path / "app.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY)")

    monkeypatch.setenv("CODEX_RUNNER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CODEX_RUNNER_DB_PATH", str(db_path))

    import backend.db as db_module

    db_module = importlib.reload(db_module)
    with pytest.raises(RuntimeError, match="not compatible with v2.0 mainline"):
        db_module.init_db()


def test_requirements_use_expected_httpx_dependency() -> None:
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()

    assert any(line.startswith("httpx>=") for line in requirements)
    assert not any(line.startswith("httpx2") for line in requirements)


def test_ci_runs_local_e2e_smoke_script() -> None:
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "python scripts/smoke_local_e2e.py" in ci
    assert 'cache: "npm"' in ci
    assert "cache-dependency-path: frontend/package-lock.json" in ci
