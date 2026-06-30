from __future__ import annotations

from sqlmodel import select

from backend.models import AgentCommandStatus, AuditEvent
from tests.test_runs_api import add_device, add_project, add_workspace, make_client


def test_run_lifecycle_writes_audit_events(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")

        run = client.post(
            "/runs",
            json={
                "project_id": project.id,
                "workspace_id": workspace.id,
                "prompt": "audited run",
            },
        ).json()
        claim = client.post(
            "/agent/commands/claim",
            headers={"X-Agent-Token": "agent-secret"},
            json={"device_id": "device-a", "claim_request_id": "claim-audit"},
        ).json()
        client.post(
            f"/agent/commands/{run['command_id']}/ack",
            headers={"X-Agent-Token": "agent-secret"},
            json={"device_id": "device-a", "lease_token": claim["lease_token"]},
        )
        client.post(
            f"/agent/commands/{run['command_id']}/complete",
            headers={"X-Agent-Token": "agent-secret"},
            json={
                "device_id": "device-a",
                "lease_token": claim["lease_token"],
                "status": AgentCommandStatus.SUCCESS.value,
            },
        )

        events = session.exec(select(AuditEvent).order_by(AuditEvent.id)).all()
        assert [event.action for event in events] == [
            "run.created",
            "agent_command.claimed",
            "agent_command.acknowledged",
            "run.running",
            "agent_command.completed",
            "run.completed",
        ]
        assert events[0].entity_type == "run"
        assert events[0].entity_id == str(run["id"])
