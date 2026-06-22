from __future__ import annotations

from pathlib import Path
import json
import os
from typing import Any

from agent.command_handlers import CommandResult
from agent.workspace_registry import WorkspaceRegistry, WorkspaceRegistryError
from runner.codex_executor import check_clean_worktree, collect_git_artifacts, execute_codex


class RunExecutor:
    def __init__(self, workspace_registry: WorkspaceRegistry) -> None:
        self.workspace_registry = workspace_registry

    def handle(self, command: dict[str, Any]) -> CommandResult:
        try:
            payload = json.loads(command.get("payload_json") or "{}")
            workspace_key = str(payload["workspace_key"])
            project_path = self.workspace_registry.resolve(workspace_key)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, WorkspaceRegistryError) as exc:
            return CommandResult(False, f"invalid run command payload: {exc}")

        if payload.get("cwd") or payload.get("project_path"):
            return CommandResult(False, "run command payload must not specify cwd")

        if os.environ.get("CODEX_AGENT_FAKE_RUN") == "1":
            return self._fake_execute(project_path, payload)

        require_clean = bool(payload.get("require_clean_worktree"))
        if require_clean:
            clean_error = check_clean_worktree(project_path)
            if clean_error:
                return CommandResult(False, clean_error)

        job_dir = Path("data") / "agent-runs" / str(payload.get("task_id", command.get("id")))
        log_file = job_dir / "run.log"
        result_file = job_dir / "result.md"
        execution = execute_codex(
            project_path=project_path,
            prompt=str(payload.get("prompt") or ""),
            log_file=log_file,
            result_file=result_file,
            timeout_seconds=int(payload.get("timeout_seconds") or 7200),
            model=payload.get("model"),
            reasoning_effort=payload.get("reasoning_effort"),
            sandbox=str(payload.get("sandbox") or "workspace-write"),
        )
        artifacts = collect_git_artifacts(project_path, job_dir)
        if execution.error_message:
            return CommandResult(False, execution.error_message)
        if artifacts.error_message:
            return CommandResult(False, artifacts.error_message)
        return CommandResult(True, f"run executed in {project_path}")

    def _fake_execute(self, project_path: Path, payload: dict[str, Any]) -> CommandResult:
        return CommandResult(
            True,
            f"fake run executed in {project_path} for task {payload.get('task_id')}",
        )
