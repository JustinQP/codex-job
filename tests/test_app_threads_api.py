from __future__ import annotations

from datetime import timedelta

from backend.models import Device, DeviceStatus
from backend.models import AgentCommandStatus
from backend.schemas import (
    APP_THREAD_TITLE_MAX_LENGTH,
    APP_TURN_MESSAGE_MAX_LENGTH,
    AgentCommandCompleteRequest,
    AgentCommandLeaseRequest,
    AppThreadCreate,
    AppTurnCreate,
)
from backend.models import AppThread, AppTurn, WorkspaceExecutionLock
from backend.services import agent_command_service, app_thread_service
import pytest
from sqlmodel import select
from tests.test_runs_api import add_device, add_project, add_workspace, make_client


def api_headers() -> dict[str, str]:
    return {"X-Agent-Token": "agent-secret"}


def test_create_app_thread_generates_session_open_command(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")

        response = client.post(
            "/app-threads",
            json={"project_id": project.id, "workspace_id": workspace.id, "title": "Demo"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "OPENING"
        assert body["device_id"] == "device-a"
        assert body["workspace_id"] == workspace.id
        assert "bridge_thread_id" not in body
        assert "app_thread_id" not in body
        command = agent_command_service.list_commands_for_device(session, "device-a")[0]
        assert command.command_type == "SESSION_OPEN"
        assert command.aggregate_type == "app_thread"


def test_create_app_thread_advanced_config_is_sent_to_agent(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")

        response = client.post(
            "/app-threads",
            json={
                "project_id": project.id,
                "workspace_id": workspace.id,
                "title": "Advanced",
                "sandbox": "workspace-write",
                "approval_policy": "never",
                "network_access": True,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["sandbox"] == "workspace-write"
        assert body["approval_policy"] == "never"
        assert body["network_access"] is True
        command = agent_command_service.list_commands_for_device(session, "device-a")[0]
        assert '"sandbox":"workspace-write"' in command.payload_json
        assert '"network_access":true' in command.payload_json


def test_complete_session_open_and_turn_start_exposes_codex_ids(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")
        created = client.post(
            "/app-threads",
            json={"project_id": project.id, "workspace_id": workspace.id, "title": "Demo"},
        ).json()
        open_command = agent_command_service.list_commands_for_device(session, "device-a")[0]
        open_command = agent_command_service.claim_command(session, device_id="device-a", claim_request_id="claim-open")
        assert open_command is not None
        lease = AgentCommandLeaseRequest(device_id="device-a", lease_token=open_command.lease_token)
        client.post(f"/agent/commands/{open_command.id}/ack", headers=api_headers(), json=lease.model_dump())
        complete_open = AgentCommandCompleteRequest(
            device_id="device-a",
            lease_token=open_command.lease_token,
            status=AgentCommandStatus.SUCCESS,
            result_payload={"agent_session_id": "agent-session-1", "codex_thread_id": "codex-thread-1"},
        )
        assert client.post(
            f"/agent/commands/{open_command.id}/complete",
            headers=api_headers(),
            json=complete_open.model_dump(mode="json"),
        ).status_code == 200

        active = client.get(f"/app-threads/{created['id']}").json()
        assert active["status"] == "ACTIVE"
        assert active["agent_session_id"] == "agent-session-1"
        assert active["codex_thread_id"] == "codex-thread-1"

        turn = client.post(f"/app-threads/{created['id']}/turns/async", json={"message": "hello"})
        assert turn.status_code == 200
        turn_body = turn.json()
        turn_command = agent_command_service.list_commands_for_device(session, "device-a")[1]
        turn_command = agent_command_service.claim_command(session, device_id="device-a", claim_request_id="claim-turn")
        assert turn_command is not None
        turn_lease = AgentCommandLeaseRequest(device_id="device-a", lease_token=turn_command.lease_token)
        client.post(f"/agent/commands/{turn_command.id}/ack", headers=api_headers(), json=turn_lease.model_dump())
        complete_turn = AgentCommandCompleteRequest(
            device_id="device-a",
            lease_token=turn_command.lease_token,
            status=AgentCommandStatus.SUCCESS,
            result_payload={
                "assistant_final": "hi",
                "codex_turn_id": "codex-turn-1",
                "event_summary": {"total_events": 1, "assistant_text_preview": "hi"},
            },
        )
        assert client.post(
            f"/agent/commands/{turn_command.id}/complete",
            headers=api_headers(),
            json=complete_turn.model_dump(mode="json"),
        ).status_code == 200

        finished = client.get(f"/app-turns/{turn_body['id']}").json()
        assert finished["status"] == "SUCCESS"
        assert finished["assistant_final"] == "hi"
        assert finished["codex_turn_id"] == "codex-turn-1"
        assert "bridge_turn_id" not in finished


def test_session_open_failure_marks_thread_error_and_releases_lock(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")
        created = client.post(
            "/app-threads",
            json={"project_id": project.id, "workspace_id": workspace.id, "title": "Demo"},
        ).json()
        command = agent_command_service.claim_command(session, device_id="device-a", claim_request_id="claim-open")
        assert command is not None
        lease = {"device_id": "device-a", "lease_token": command.lease_token}
        client.post(f"/agent/commands/{command.id}/ack", headers=api_headers(), json=lease)

        response = client.post(
            f"/agent/commands/{command.id}/complete",
            headers=api_headers(),
            json={**lease, "status": "FAILED", "error_message": "open failed"},
        )

        assert response.status_code == 200
        thread = client.get(f"/app-threads/{created['id']}").json()
        assert thread["status"] == "ERROR"
        assert thread["last_error"] == "open failed"


def test_close_active_thread_creates_session_close_command(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")
        created = client.post(
            "/app-threads",
            json={"project_id": project.id, "workspace_id": workspace.id, "title": "Demo"},
        ).json()
        command = agent_command_service.claim_command(session, device_id="device-a", claim_request_id="claim-open")
        assert command is not None
        lease = {"device_id": "device-a", "lease_token": command.lease_token}
        client.post(f"/agent/commands/{command.id}/ack", headers=api_headers(), json=lease)
        client.post(
            f"/agent/commands/{command.id}/complete",
            headers=api_headers(),
            json={
                **lease,
                "status": "SUCCESS",
                "result_payload": {"agent_session_id": "agent-session-1", "codex_thread_id": "codex-thread-1"},
            },
        )

        closed = client.delete(f"/app-threads/{created['id']}")

        assert closed.status_code == 200
        body = closed.json()
        assert body["status"] == "CLOSING"
        close_command = agent_command_service.list_commands_for_device(session, "device-a")[-1]
        assert close_command.command_type == "SESSION_CLOSE"


def test_create_app_thread_rolls_back_when_command_creation_fails(monkeypatch) -> None:
    def fail_create_command(*args, **kwargs):
        raise agent_command_service.AgentCommandServiceError("boom", "boom")

    monkeypatch.setattr(agent_command_service, "create_command", fail_create_command)
    for _client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")

        with pytest.raises(agent_command_service.AgentCommandServiceError):
            app_thread_service.create_app_thread(
                session,
                AppThreadCreate(project_id=project.id, workspace_id=workspace.id, title="rollback"),
            )

        assert len(session.exec(select(AppThread)).all()) == 0
        assert len(session.exec(select(WorkspaceExecutionLock)).all()) == 0


def test_create_app_thread_rejects_expired_online_device() -> None:
    for client, session in make_client():
        project = add_project(session)
        device = add_device(session, "device-a")
        device.lease_expires_at = app_thread_service.utc_now() - timedelta(seconds=1)
        session.add(device)
        session.commit()
        workspace = add_workspace(session, "device-a")

        response = client.post(
            "/app-threads",
            json={"project_id": project.id, "workspace_id": workspace.id, "title": "Expired"},
        )

        assert response.status_code == 409
        assert response.json()["detail"] == "device is offline"
        assert session.get(Device, "device-a").status == DeviceStatus.OFFLINE


def test_create_app_thread_rejects_oversized_title() -> None:
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")

        response = client.post(
            "/app-threads",
            json={
                "project_id": project.id,
                "workspace_id": workspace.id,
                "title": "x" * (APP_THREAD_TITLE_MAX_LENGTH + 1),
            },
        )

        assert response.status_code == 422


def test_reopen_app_thread_rejects_expired_online_device(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        project = add_project(session)
        device = add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")
        created = client.post(
            "/app-threads",
            json={"project_id": project.id, "workspace_id": workspace.id, "title": "Demo"},
        ).json()
        app_thread = session.get(AppThread, created["id"])
        assert app_thread is not None
        app_thread.status = app_thread_service.APP_THREAD_RECOVER_REQUIRED
        app_thread.agent_session_id = None
        session.add(app_thread)
        device.lease_expires_at = app_thread_service.utc_now() - timedelta(seconds=1)
        session.add(device)
        lock = session.get(WorkspaceExecutionLock, 1)
        if lock is not None:
            session.delete(lock)
        session.commit()

        response = client.post(f"/app-threads/{created['id']}/reopen")

        assert response.status_code == 409
        assert response.json()["detail"] == "device is offline"
        assert session.get(Device, "device-a").status == DeviceStatus.OFFLINE


def test_app_turn_timeout_is_sent_to_agent_command(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")
        created = client.post(
            "/app-threads",
            json={"project_id": project.id, "workspace_id": workspace.id, "title": "Demo"},
        ).json()
        command = agent_command_service.claim_command(session, device_id="device-a", claim_request_id="claim-open")
        assert command is not None
        lease = {"device_id": "device-a", "lease_token": command.lease_token}
        client.post(f"/agent/commands/{command.id}/ack", headers=api_headers(), json=lease)
        client.post(
            f"/agent/commands/{command.id}/complete",
            headers=api_headers(),
            json={
                **lease,
                "status": "SUCCESS",
                "result_payload": {"agent_session_id": "agent-session-1", "codex_thread_id": "codex-thread-1"},
            },
        )

        response = client.post(
            f"/app-threads/{created['id']}/turns/async",
            json={"message": "slow please", "timeout_seconds": 900},
        )

        assert response.status_code == 200
        turn_command = agent_command_service.list_commands_for_device(session, "device-a")[-1]
        assert turn_command.command_type == "TURN_START"
        assert '"timeout_seconds":900' in turn_command.payload_json


def test_app_turn_rejects_oversized_message(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")
        created = client.post(
            "/app-threads",
            json={"project_id": project.id, "workspace_id": workspace.id, "title": "Demo"},
        ).json()

        response = client.post(
            f"/app-threads/{created['id']}/turns/async",
            json={"message": "x" * (APP_TURN_MESSAGE_MAX_LENGTH + 1)},
        )

        assert response.status_code == 422


def test_create_app_turn_rolls_back_when_command_creation_fails(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")
        created = client.post(
            "/app-threads",
            json={"project_id": project.id, "workspace_id": workspace.id, "title": "Demo"},
        ).json()
        command = agent_command_service.claim_command(session, device_id="device-a", claim_request_id="claim-open")
        assert command is not None
        lease = {"device_id": "device-a", "lease_token": command.lease_token}
        client.post(f"/agent/commands/{command.id}/ack", headers=api_headers(), json=lease)
        client.post(
            f"/agent/commands/{command.id}/complete",
            headers=api_headers(),
            json={
                **lease,
                "status": "SUCCESS",
                "result_payload": {"agent_session_id": "agent-session-1", "codex_thread_id": "codex-thread-1"},
            },
        )

        def fail_create_command(*args, **kwargs):
            raise agent_command_service.AgentCommandServiceError("boom", "boom")

        monkeypatch.setattr(agent_command_service, "create_command", fail_create_command)
        app_thread = session.get(AppThread, created["id"])

        with pytest.raises(agent_command_service.AgentCommandServiceError):
            app_thread_service.create_agent_async_app_turn(
                session,
                app_thread,
                AppTurnCreate(message="hello").message,
            )

        assert len(session.exec(select(AppTurn)).all()) == 0


def test_list_app_turns_returns_latest_limited_turns_in_ascending_order(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")
        created = client.post(
            "/app-threads",
            json={"project_id": project.id, "workspace_id": workspace.id, "title": "Demo"},
        ).json()
        for index in range(5):
            session.add(
                AppTurn(
                    app_thread_id=created["id"],
                    user_message=f"turn-{index + 1}",
                    status="SUCCESS",
                )
            )
        session.commit()

        response = client.get(f"/app-threads/{created['id']}/turns", params={"limit": 3})

        assert response.status_code == 200
        assert [turn["user_message"] for turn in response.json()] == ["turn-3", "turn-4", "turn-5"]
