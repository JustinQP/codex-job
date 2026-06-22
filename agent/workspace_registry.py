from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


class WorkspaceRegistryError(RuntimeError):
    pass


@dataclass(frozen=True)
class LocalWorkspace:
    key: str
    name: str
    path: Path
    enabled: bool = True

    @property
    def path_label(self) -> str:
        return self.path.name or self.key


class WorkspaceRegistry:
    def __init__(self, workspaces: dict[str, LocalWorkspace]):
        self._workspaces = workspaces

    @classmethod
    def load(cls, config_path: Path) -> "WorkspaceRegistry":
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise WorkspaceRegistryError(f"workspace registry file not found: {config_path}") from exc
        except json.JSONDecodeError as exc:
            raise WorkspaceRegistryError("workspace registry file is not valid JSON") from exc

        workspaces_raw = raw.get("workspaces") if isinstance(raw, dict) else None
        allowed_roots_raw = raw.get("allowed_roots") if isinstance(raw, dict) else None
        if not isinstance(workspaces_raw, list):
            raise WorkspaceRegistryError("workspace registry field workspaces must be a list")
        if not isinstance(allowed_roots_raw, list) or not allowed_roots_raw:
            raise WorkspaceRegistryError("workspace registry field allowed_roots must be a non-empty list")

        allowed_roots = [_resolve_existing_directory(Path(str(root)), "allowed_root") for root in allowed_roots_raw]
        workspaces: dict[str, LocalWorkspace] = {}
        for item in workspaces_raw:
            workspace = _parse_workspace(item, allowed_roots)
            if workspace.key in workspaces:
                raise WorkspaceRegistryError(f"duplicate workspace key: {workspace.key}")
            workspaces[workspace.key] = workspace
        return cls(workspaces)

    def list(self, *, include_disabled: bool = True) -> list[LocalWorkspace]:
        values = list(self._workspaces.values())
        if include_disabled:
            return values
        return [workspace for workspace in values if workspace.enabled]

    def resolve(self, workspace_key: str) -> Path:
        workspace = self._workspaces.get(workspace_key)
        if workspace is None:
            raise WorkspaceRegistryError(f"workspace not found: {workspace_key}")
        if not workspace.enabled:
            raise WorkspaceRegistryError(f"workspace disabled: {workspace_key}")
        return workspace.path


def _parse_workspace(item: Any, allowed_roots: list[Path]) -> LocalWorkspace:
    if not isinstance(item, dict):
        raise WorkspaceRegistryError("workspace entry must be an object")
    key = _required_string(item, "key")
    name = _required_string(item, "name")
    enabled = bool(item.get("enabled", True))
    path = _resolve_existing_directory(Path(_required_string(item, "path")), key)
    if not _is_under_allowed_roots(path, allowed_roots):
        raise WorkspaceRegistryError(f"workspace path is outside allowed roots: {key}")
    return LocalWorkspace(key=key, name=name, path=path, enabled=enabled)


def _required_string(item: dict, key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise WorkspaceRegistryError(f"workspace field {key} is missing or invalid")
    return value


def _resolve_existing_directory(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise WorkspaceRegistryError(f"workspace path does not exist: {label}")
    if not resolved.is_dir():
        raise WorkspaceRegistryError(f"workspace path is not a directory: {label}")
    return resolved


def _is_under_allowed_roots(path: Path, allowed_roots: list[Path]) -> bool:
    normalized_path = _casefold_path(path)
    for root in allowed_roots:
        normalized_root = _casefold_path(root)
        try:
            normalized_path.relative_to(normalized_root)
            return True
        except ValueError:
            continue
    return False


def _casefold_path(path: Path) -> Path:
    if not _is_windows_path(path):
        return path
    return Path(str(path).casefold())


def _is_windows_path(path: Path) -> bool:
    return bool(path.drive) or "\\" in str(path)
