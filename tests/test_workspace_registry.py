from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.workspace_registry import (
    WorkspaceRegistry,
    WorkspaceRegistryError,
    _is_under_allowed_roots,
)


def write_registry(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_valid_workspace_can_be_resolved(tmp_path) -> None:
    allowed = tmp_path / "allowed"
    workspace_dir = allowed / "repo"
    workspace_dir.mkdir(parents=True)
    config = write_registry(
        tmp_path / "workspaces.json",
        {
            "allowed_roots": [str(allowed)],
            "workspaces": [
                {
                    "key": "repo",
                    "name": "Repo",
                    "path": str(workspace_dir),
                    "enabled": True,
                }
            ],
        },
    )

    registry = WorkspaceRegistry.load(config)

    assert registry.resolve("repo") == workspace_dir.resolve()
    assert registry.list()[0].path_label == "repo"
    assert registry.to_sync_items()[0].workspace_key == "repo"
    assert registry.to_sync_items()[0].path_label == "repo"


def test_workspace_registry_syncs_default_execution_settings(tmp_path) -> None:
    allowed = tmp_path / "allowed"
    workspace_dir = allowed / "repo"
    workspace_dir.mkdir(parents=True)
    config = write_registry(
        tmp_path / "workspaces.json",
        {
            "allowed_roots": [str(allowed)],
            "workspaces": [
                {
                    "key": "repo",
                    "name": "Repo",
                    "path": str(workspace_dir),
                    "default_model": "gpt-5",
                    "default_reasoning_effort": "high",
                    "default_sandbox": "read-only",
                    "default_approval_policy": "never",
                    "require_clean_worktree": True,
                }
            ],
        },
    )

    item = WorkspaceRegistry.load(config).to_sync_items()[0]

    assert item.default_model == "gpt-5"
    assert item.default_reasoning_effort == "high"
    assert item.default_sandbox == "read-only"
    assert item.default_approval_policy == "never"
    assert item.require_clean_worktree is True


def test_missing_duplicate_and_disabled_workspaces_are_rejected(tmp_path) -> None:
    allowed = tmp_path / "allowed"
    workspace_dir = allowed / "repo"
    workspace_dir.mkdir(parents=True)
    duplicate_config = write_registry(
        tmp_path / "duplicate.json",
        {
            "allowed_roots": [str(allowed)],
            "workspaces": [
                {"key": "repo", "name": "Repo", "path": str(workspace_dir)},
                {"key": "repo", "name": "Repo 2", "path": str(workspace_dir)},
            ],
        },
    )
    disabled_config = write_registry(
        tmp_path / "disabled.json",
        {
            "allowed_roots": [str(allowed)],
            "workspaces": [
                {
                    "key": "repo",
                    "name": "Repo",
                    "path": str(workspace_dir),
                    "enabled": False,
                }
            ],
        },
    )

    with pytest.raises(WorkspaceRegistryError, match="duplicate workspace key: repo"):
        WorkspaceRegistry.load(duplicate_config)
    disabled = WorkspaceRegistry.load(disabled_config)
    with pytest.raises(WorkspaceRegistryError, match="workspace disabled: repo"):
        disabled.resolve("repo")
    with pytest.raises(WorkspaceRegistryError, match="workspace not found: missing"):
        disabled.resolve("missing")


def test_outside_workspace_is_rejected_without_exposing_full_path(tmp_path) -> None:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    config = write_registry(
        tmp_path / "workspaces.json",
        {
            "allowed_roots": [str(allowed)],
            "workspaces": [
                {
                    "key": "outside",
                    "name": "Outside",
                    "path": str(outside),
                }
            ],
        },
    )

    with pytest.raises(WorkspaceRegistryError) as exc:
        WorkspaceRegistry.load(config)

    assert "workspace path is outside allowed roots: outside" in str(exc.value)
    assert str(outside) not in str(exc.value)


def test_file_path_is_rejected(tmp_path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    file_path = allowed / "file.txt"
    file_path.write_text("not a dir", encoding="utf-8")
    config = write_registry(
        tmp_path / "workspaces.json",
        {
            "allowed_roots": [str(allowed)],
            "workspaces": [
                {
                    "key": "file",
                    "name": "File",
                    "path": str(file_path),
                }
            ],
        },
    )

    with pytest.raises(WorkspaceRegistryError, match="workspace path is not a directory: file"):
        WorkspaceRegistry.load(config)


def test_windows_path_casefold_helper_allows_case_differences() -> None:
    path = Path("C:/Users/Example/Repo")
    root = Path("c:/users/example")

    assert _is_under_allowed_roots(path, [root]) is True


def test_symlink_escape_is_rejected_when_supported(tmp_path) -> None:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    link = allowed / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation not available: {exc}")
    config = write_registry(
        tmp_path / "workspaces.json",
        {
            "allowed_roots": [str(allowed)],
            "workspaces": [
                {
                    "key": "escape",
                    "name": "Escape",
                    "path": str(link),
                }
            ],
        },
    )

    with pytest.raises(WorkspaceRegistryError, match="outside allowed roots: escape"):
        WorkspaceRegistry.load(config)
