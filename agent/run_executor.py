from __future__ import annotations

from pathlib import Path
import json
import os
from typing import Any

from agent.api_client import AgentApiClient, AgentApiError
from agent.command_handlers import CommandResult
from agent.process_registry import ProcessRegistry
from agent.workspace_lock import LocalWorkspaceLock, is_write_sandbox
from agent.workspace_registry import WorkspaceRegistry, WorkspaceRegistryError
from backend.models import AgentCommandStatus
from backend.schemas import AgentCommandLeaseRequest, AgentReconcileRequest
from agent.codex_executor import check_clean_worktree, collect_git_artifacts, execute_codex


class RunExecutor:
    def __init__(
        self,
        workspace_registry: WorkspaceRegistry,
        *,
        client: AgentApiClient | None = None,
        device_id: str | None = None,
        process_registry: ProcessRegistry | None = None,
        workspace_lock: LocalWorkspaceLock | None = None,
    ) -> None:
        self.workspace_registry = workspace_registry
        self.client = client
        self.device_id = device_id
        self.process_registry = process_registry or ProcessRegistry()
        self.workspace_lock = workspace_lock or LocalWorkspaceLock()

    def handle(self, command: dict[str, Any]) -> CommandResult:
        try:
            payload = json.loads(command.get("payload_json") or "{}")
            workspace_key = str(payload["workspace_key"])
            project_path = self.workspace_registry.resolve(workspace_key)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, WorkspaceRegistryError) as exc:
            return CommandResult(False, f"invalid run command payload: {exc}")

        if payload.get("cwd") or payload.get("project_path"):
            return CommandResult(False, "run command payload must not specify cwd")

        command_id = str(command.get("id") or "")
        lease_token = str(command.get("lease_token") or "")

        sandbox = str(payload.get("sandbox") or "workspace-write")
        run_id = payload.get("run_id")
        owner = command_id or str(run_id or "run")
        try:
            with self.workspace_lock.acquire(project_path, owner=f"run:{owner}", write=is_write_sandbox(sandbox)):
                if os.environ.get("CODEX_AGENT_FAKE_RUN") == "1":
                    return self._fake_execute(project_path, payload)

                require_clean = bool(payload.get("require_clean_worktree"))
                if require_clean:
                    clean_error = check_clean_worktree(project_path)
                    if clean_error:
                        return CommandResult(False, clean_error)

                job_dir = Path("data") / "agent-runs" / str(run_id or command.get("id"))
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
                    sandbox=sandbox,
                    should_cancel=lambda: self._should_cancel(command_id, lease_token),
                    on_process_started=lambda process: self.process_registry.register(command_id, process),
                    on_process_finished=lambda: self.process_registry.unregister(command_id),
                )
                artifacts = collect_git_artifacts(project_path, job_dir)
        except RuntimeError as exc:
            return CommandResult(False, str(exc))
        if execution.error_message:
            return CommandResult(False, execution.error_message)
        if artifacts.error_message:
            return CommandResult(False, artifacts.error_message)
        return CommandResult(True, f"run executed in {project_path}")

    def _fake_execute(self, project_path: Path, payload: dict[str, Any]) -> CommandResult:
        return CommandResult(
            True,
            f"fake run executed in {project_path} for run {payload.get('run_id')}",
        )

    def _should_cancel(self, command_id: str, lease_token: str) -> bool:
        if self.client is None or not self.device_id or not command_id or not lease_token:
            return False
        lease = AgentCommandLeaseRequest(
            device_id=self.device_id,
            lease_token=lease_token,
        )
        try:
            self.client.renew_command(command_id, lease)
            reconciliation = self.client.reconcile(
                AgentReconcileRequest(
                    device_id=self.device_id,
                    command_id=command_id,
                    process_status="RUNNING",
                )
            )
        except AgentApiError:
            return False
        if reconciliation.get("server_status") == AgentCommandStatus.CANCELLED.value:
            return True
        return reconciliation.get("action") == "STOP"
