from __future__ import annotations

import json

from sqlmodel import Session

from agent.command_handlers import CommandHandlerRegistry
from agent.run_executor import RunExecutor
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
                    "task_id": 1,
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
        {
            "id": "cmd-1",
            "command_type": "RUN_EXECUTE",
            "payload_json": json.dumps({"task_id": 1, "workspace_key": "repo"}),
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
