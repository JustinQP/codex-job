from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import Session

from agent.api_client import AgentApiError
from agent.command_handlers import CommandHandlerRegistry
from agent.run_executor import RunExecutor
from agent.session_handlers import SessionOpenHandler
from agent.workspace_lock import LocalWorkspaceLock
from agent.workspace_registry import WorkspaceRegistry
from backend.models import Device, DeviceStatus, Project, Workspace, utc_now
from backend.services import agent_command_service
from tests.test_runs_api import make_client


def add_project(session: Session) -> Project:
    project = Project(name="demo", path="E:\\demo", enabled=True, created_at=utc_now(), updated_at=utc_now())
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def add_device(session: Session, device_id: str) -> Device:
    device = Device(
        device_id=device_id,
        display_name=device_id,
        hostname=device_id,
        os_name="Windows",
        agent_version="0.1.0",
        status=DeviceStatus.ONLINE,
        last_heartbeat_at=utc_now(),
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(device)
    session.commit()
    session.refresh(device)
    return device


def add_workspace(session: Session, device_id: str) -> Workspace:
    workspace = Workspace(
        device_id=device_id,
        workspace_key=f"repo-{device_id}",
        name="Repo",
        path_label="codex-job",
        enabled=True,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(workspace)
    session.commit()
    session.refresh(workspace)
    return workspace


def test_run_creation_generates_device_scoped_agent_command() -> None:
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        add_device(session, "device-b")
        workspace = add_workspace(session, "device-a")

        response = client.post(
            "/runs",
            json={
                "project_id": project.id,
                "workspace_id": workspace.id,
                "device_id": "device-b",
                "prompt": "execute through agent",
                "client_request_id": "run-client-1",
            },
        )

        assert response.status_code == 200
        body = response.json()
        commands = agent_command_service.list_commands_for_device(session, "device-a")
        assert len(commands) == 1
        assert body["command_id"] == commands[0].id
        assert commands[0].command_type == "RUN_EXECUTE"
        assert commands[0].device_id == "device-a"
        payload = json.loads(commands[0].payload_json)
        assert payload["workspace_key"] == workspace.workspace_key
        assert "cwd" not in payload
        assert "project_path" not in payload
        assert agent_command_service.list_commands_for_device(session, "device-b") == []


def test_run_executor_uses_workspace_registry_path_in_fake_mode(monkeypatch, tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    registry = WorkspaceRegistry.load(
        _write_registry(tmp_path, repo)
    )
    executor = RunExecutor(registry)
    monkeypatch.setenv("CODEX_AGENT_FAKE_RUN", "1")

    result = executor.handle(
        {
            "id": "cmd-1",
            "command_type": "RUN_EXECUTE",
            "payload_json": json.dumps(
                {
                    "run_id": 1,
                    "workspace_key": "repo",
                    "prompt": "hello",
                }
            ),
        }
    )

    assert result.success is True
    assert str(repo) in (result.message or "")


def test_command_registry_completes_run_execute_with_fake_handler(monkeypatch, tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    registry = WorkspaceRegistry.load(_write_registry(tmp_path, repo))
    handlers = CommandHandlerRegistry(registry)
    monkeypatch.setenv("CODEX_AGENT_FAKE_RUN", "1")

    result = handlers.handle(
        {"id": "cmd-1", "command_type": "RUN_EXECUTE", "payload_json": json.dumps({"run_id": 1, "workspace_key": "repo"})}
    )

    assert result.success is True


class FakeStdout:
    def __iter__(self):
        return iter(())


class FakeProcess:
    def __init__(self) -> None:
        self.stdout = FakeStdout()
        self.pid = 123
        self.terminated = False
        self._polls = 0

    def poll(self):
        self._polls += 1
        return None if self._polls == 1 else -1

    def wait(self, timeout=None):
        return -1

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.terminated = True


class CancelClient:
    def __init__(self) -> None:
        self.renewed = 0
        self.reconciled = 0

    def renew_command(self, command_id, payload):
        self.renewed += 1
        return {"id": command_id}

    def reconcile(self, payload):
        self.reconciled += 1
        return {
            "action": "STOP",
            "server_status": "CANCELLED",
            "reason": "server command is cancelled",
        }


def test_run_executor_stops_process_when_command_is_cancelled(monkeypatch, tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    registry = WorkspaceRegistry.load(_write_registry(tmp_path, repo))
    process = FakeProcess()
    client = CancelClient()
    executor = RunExecutor(registry, client=client, device_id="device-a")

    monkeypatch.setattr("agent.run_executor.check_clean_worktree", lambda project_path: None)
    monkeypatch.setattr("agent.run_executor.collect_git_artifacts", lambda project_path, job_dir: _git_artifacts(job_dir))
    monkeypatch.setattr("agent.codex_executor.find_codex_bin", lambda: "codex")
    monkeypatch.setattr("agent.codex_executor.subprocess.Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr("agent.codex_executor.time.sleep", lambda seconds: None)

    result = executor.handle(
        {
            "id": "cmd-1",
            "lease_token": "lease-a",
            "command_type": "RUN_EXECUTE",
            "payload_json": json.dumps(
                {
                    "run_id": 1,
                    "workspace_key": "repo",
                    "prompt": "long run",
                }
            ),
        }
    )

    assert result.success is False
    assert result.message == "run cancelled"
    assert process.terminated is True
    assert client.renewed == 1
    assert client.reconciled == 1


def test_run_executor_ignores_temporary_cancel_poll_error(monkeypatch, tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    registry = WorkspaceRegistry.load(_write_registry(tmp_path, repo))
    executor = RunExecutor(registry, client=_FailingCancelClient(), device_id="device-a")

    assert executor._should_cancel("cmd-1", "lease-a") is False


def test_local_workspace_lock_blocks_write_session_when_write_run_active(monkeypatch, tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    registry = WorkspaceRegistry.load(_write_registry(tmp_path, repo))
    workspace_lock = LocalWorkspaceLock()
    workspace_lock.acquire_write(repo, "run:active")

    class FakeSessionManager:
        workspace_registry = registry

        def open_session(self, **kwargs):
            raise AssertionError("open_session should not be called while workspace is busy")

    result = SessionOpenHandler(FakeSessionManager(), workspace_lock).handle(
        {
            "id": "cmd-session",
            "command_type": "SESSION_OPEN",
            "payload_json": json.dumps(
                {
                    "workspace_key": "repo",
                    "sandbox": "workspace-write",
                }
            ),
        }
    )

    assert result.success is False
    assert "workspace busy" in (result.message or "")


def test_local_workspace_lock_allows_read_only_session_when_write_run_active(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    registry = WorkspaceRegistry.load(_write_registry(tmp_path, repo))
    workspace_lock = LocalWorkspaceLock()
    workspace_lock.acquire_write(repo, "run:active")

    class FakeSession:
        cwd = repo
        agent_session_id = "agent-session"
        codex_thread_id = "codex-thread"
        workspace_key = "repo"

    class FakeSessionManager:
        workspace_registry = registry

        def open_session(self, **kwargs):
            return FakeSession()

    result = SessionOpenHandler(FakeSessionManager(), workspace_lock).handle(
        {
            "id": "cmd-session",
            "command_type": "SESSION_OPEN",
            "payload_json": json.dumps(
                {
                    "workspace_key": "repo",
                    "sandbox": "read-only",
                }
            ),
        }
    )

    assert result.success is True


def _write_registry(tmp_path, repo):
    registry_path = tmp_path / "workspaces.json"
    registry_path.write_text(
        json.dumps(
            {
                "allowed_roots": [str(tmp_path)],
                "workspaces": [
                    {
                        "key": "repo",
                        "name": "Repo",
                        "path": str(repo),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return registry_path


def _git_artifacts(job_dir: Path):
    job_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "status_file": job_dir / "git-status.txt",
        "diff_unstaged_file": job_dir / "diff-unstaged.patch",
        "diff_staged_file": job_dir / "diff-staged.patch",
        "untracked_files_file": job_dir / "untracked-files.txt",
        "combined_diff_file": job_dir / "diff.patch",
    }
    for path in paths.values():
        path.write_text("", encoding="utf-8")
    from agent.codex_executor import GitArtifactsResult

    return GitArtifactsResult(error_message=None, **paths)


class _FailingCancelClient:
    def renew_command(self, command_id, payload):
        raise AgentApiError("temporary network")
