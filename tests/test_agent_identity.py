from __future__ import annotations

import json

import pytest

from agent.config import load_agent_config
from agent.identity import AgentIdentityError, load_or_create_identity


def test_same_data_dir_reuses_device_id(tmp_path) -> None:
    identity_path = tmp_path / "agent" / "identity.json"

    first = load_or_create_identity(identity_path, display_name="Desk")
    second = load_or_create_identity(identity_path, display_name="Ignored")

    assert first.device_id == second.device_id
    assert second.display_name == "Desk"
    assert json.loads(identity_path.read_text(encoding="utf-8"))["device_id"] == first.device_id


def test_different_data_dirs_get_different_device_ids(tmp_path) -> None:
    first = load_or_create_identity(
        tmp_path / "a" / "identity.json",
        display_name="Desk A",
    )
    second = load_or_create_identity(
        tmp_path / "b" / "identity.json",
        display_name="Desk B",
    )

    assert first.device_id != second.device_id
    assert first.display_name == "Desk A"
    assert second.display_name == "Desk B"


def test_corrupt_identity_reports_clear_error(tmp_path) -> None:
    identity_path = tmp_path / "identity.json"
    identity_path.write_text("{bad json", encoding="utf-8")

    with pytest.raises(AgentIdentityError, match="not valid JSON"):
        load_or_create_identity(identity_path, display_name="Desk")


def test_identity_file_with_utf8_bom_is_supported(tmp_path) -> None:
    identity_path = tmp_path / "identity.json"
    payload = {
        "device_id": "device-a",
        "display_name": "Desk",
        "created_at": "2026-06-23T00:00:00+00:00",
    }
    identity_path.write_text(json.dumps(payload), encoding="utf-8-sig")

    identity = load_or_create_identity(identity_path, display_name="Ignored")

    assert identity.device_id == "device-a"
    assert identity.display_name == "Desk"
    assert identity.created_at == "2026-06-23T00:00:00+00:00"


@pytest.mark.parametrize(
    "payload, message",
    [
        ({}, "device_id"),
        ({"device_id": "device-a", "display_name": "Desk", "created_at": "bad"}, "created_at"),
        ([], "JSON object"),
    ],
)
def test_invalid_identity_shape_reports_clear_error(tmp_path, payload, message: str) -> None:
    identity_path = tmp_path / "identity.json"
    identity_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(AgentIdentityError, match=message):
        load_or_create_identity(identity_path, display_name="Desk")


def test_config_uses_display_name_env_without_overriding_device_id(monkeypatch, tmp_path) -> None:
    data_dir = tmp_path / "agent-data"
    monkeypatch.setenv("CODEX_AGENT_DATA_DIR", str(data_dir))
    monkeypatch.setenv("CODEX_AGENT_DISPLAY_NAME", "Env Desk")
    config = load_agent_config()
    first = load_or_create_identity(
        config.identity_path,
        display_name=config.display_name,
    )

    monkeypatch.setenv("CODEX_AGENT_DISPLAY_NAME", "Changed Desk")
    changed_config = load_agent_config()
    second = load_or_create_identity(
        changed_config.identity_path,
        display_name=changed_config.display_name,
    )

    assert first.device_id == second.device_id
    assert first.display_name == "Env Desk"
    assert second.display_name == "Env Desk"


def test_config_derives_run_data_dir_from_agent_data_dir(monkeypatch, tmp_path) -> None:
    data_dir = tmp_path / "agent-data"
    monkeypatch.setenv("CODEX_AGENT_DATA_DIR", str(data_dir))

    config = load_agent_config()

    assert config.run_data_dir == data_dir.resolve() / "runs"
    assert config.lock_data_dir == data_dir.resolve() / "locks"
