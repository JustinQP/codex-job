from __future__ import annotations

from backend.models import AgentCommandStatus
from backend.schemas import AgentCommandCompleteRequest, AgentCommandLeaseRequest
from backend.services import agent_command_service
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
