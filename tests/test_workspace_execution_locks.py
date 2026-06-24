from __future__ import annotations

from datetime import timedelta

from sqlmodel import select

from backend.models import AgentCommand, AgentCommandStatus, AppThread, Run, RunStatus, WorkspaceExecutionLock, utc_now
from backend.services import workspace_lock_service
from tests.test_runs_api import add_device, add_project, add_workspace
from tests.test_runs_api import make_client


def test_workspace_write_run_conflicts_with_write_session() -> None:
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")

        run = client.post(
            "/runs",
            json={
                "project_id": project.id,
                "workspace_id": workspace.id,
                "prompt": "write run",
                "sandbox": "workspace-write",
            },
        )
        session_request = client.post(
            "/app-threads",
            json={
                "project_id": project.id,
                "workspace_id": workspace.id,
                "title": "Write session",
                "sandbox": "workspace-write",
            },
        )

        assert run.status_code == 200
        assert session_request.status_code == 409
        detail = session_request.json()["detail"]
        assert detail["code"] == "workspace_busy"
        assert detail["owner_type"] == "run"
        assert detail["owner_id"] == str(run.json()["id"])


def test_different_workspace_write_runs_can_start() -> None:
    for client, session in make_client():
        project_a = add_project(session)
        project_b = add_project(session)
        add_device(session, "device-a")
        add_device(session, "device-b")
        workspace_a = add_workspace(session, "device-a")
        workspace_b = add_workspace(session, "device-b")

        first = client.post(
            "/runs",
            json={
                "project_id": project_a.id,
                "workspace_id": workspace_a.id,
                "prompt": "write a",
                "sandbox": "workspace-write",
            },
        )
        second = client.post(
            "/runs",
            json={
                "project_id": project_b.id,
                "workspace_id": workspace_b.id,
                "prompt": "write b",
                "sandbox": "workspace-write",
            },
        )

        assert first.status_code == 200
        assert second.status_code == 200


def test_expired_workspace_lock_is_recovered() -> None:
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")
        session.add(
            WorkspaceExecutionLock(
                workspace_id=workspace.id,
                owner_type="run",
                owner_id="old",
                lock_type="write",
                lease_expires_at=utc_now() - timedelta(seconds=1),
                created_at=utc_now() - timedelta(hours=1),
                updated_at=utc_now() - timedelta(hours=1),
            )
        )
        session.commit()

        response = client.post(
            "/runs",
            json={
                "project_id": project.id,
                "workspace_id": workspace.id,
                "prompt": "new write",
                "sandbox": "workspace-write",
            },
        )
        locks = session.exec(select(WorkspaceExecutionLock)).all()

        assert response.status_code == 200
        assert len(locks) == 1
        assert locks[0].owner_id == str(response.json()["id"])


def test_read_only_session_does_not_take_write_lock() -> None:
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")
        write_run = client.post(
            "/runs",
            json={
                "project_id": project.id,
                "workspace_id": workspace.id,
                "prompt": "write run",
                "sandbox": "workspace-write",
            },
        )
        read_session = client.post(
            "/app-threads",
            json={
                "project_id": project.id,
                "workspace_id": workspace.id,
                "title": "Read session",
                "sandbox": "read-only",
            },
        )

        assert write_run.status_code == 200
        assert read_session.status_code == 200
        assert session.exec(select(AppThread)).one().sandbox == "read-only"


def test_run_completion_releases_workspace_lock(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")
        first = client.post(
            "/runs",
            json={
                "project_id": project.id,
                "workspace_id": workspace.id,
                "prompt": "first",
                "sandbox": "workspace-write",
            },
        ).json()
        command_id = first["command_id"]
        claim = client.post(
            "/agent/commands/claim",
            headers={"X-Agent-Token": "agent-secret"},
            json={"device_id": "device-a", "claim_request_id": "claim-run"},
        ).json()
        client.post(
            f"/agent/commands/{command_id}/ack",
            headers={"X-Agent-Token": "agent-secret"},
            json={"device_id": "device-a", "lease_token": claim["lease_token"]},
        )
        complete = client.post(
            f"/agent/commands/{command_id}/complete",
            headers={"X-Agent-Token": "agent-secret"},
            json={
                "device_id": "device-a",
                "lease_token": claim["lease_token"],
                "status": AgentCommandStatus.SUCCESS.value,
            },
        )
        second = client.post(
            "/runs",
            json={
                "project_id": project.id,
                "workspace_id": workspace.id,
                "prompt": "second",
                "sandbox": "workspace-write",
            },
        )

        assert complete.status_code == 200
        assert second.status_code == 200


def test_claim_sweeper_expires_stale_run_and_releases_workspace_lock(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")
        created = client.post(
            "/runs",
            json={
                "project_id": project.id,
                "workspace_id": workspace.id,
                "prompt": "stale",
                "sandbox": "workspace-write",
            },
        ).json()
        command = session.get(AgentCommand, created["command_id"])
        command.status = AgentCommandStatus.RUNNING
        command.lease_token = "lease-stale"
        command.lease_expires_at = utc_now() - timedelta(seconds=1)
        session.add(command)
        session.commit()

        claim = client.post(
            "/agent/commands/claim",
            headers={"X-Agent-Token": "agent-secret"},
            json={"device_id": "device-a", "claim_request_id": "claim-after-stale"},
        )

        assert claim.status_code == 200
        assert claim.json() is None
        run = session.get(Run, created["id"])
        assert run.status == RunStatus.FAILED
        assert session.get(WorkspaceExecutionLock, 1) is None


def test_renew_run_command_extends_workspace_lock(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")
        created = client.post(
            "/runs",
            json={
                "project_id": project.id,
                "workspace_id": workspace.id,
                "prompt": "renew",
                "sandbox": "workspace-write",
            },
        ).json()
        claim = client.post(
            "/agent/commands/claim",
            headers={"X-Agent-Token": "agent-secret"},
            json={"device_id": "device-a", "claim_request_id": "claim-renew"},
        ).json()
        client.post(
            f"/agent/commands/{created['command_id']}/ack",
            headers={"X-Agent-Token": "agent-secret"},
            json={"device_id": "device-a", "lease_token": claim["lease_token"]},
        )
        lock = session.get(WorkspaceExecutionLock, 1)
        lock.lease_expires_at = utc_now() + timedelta(seconds=1)
        session.add(lock)
        session.commit()
        old_lock_expiry = lock.lease_expires_at

        renew = client.post(
            f"/agent/commands/{created['command_id']}/renew",
            headers={"X-Agent-Token": "agent-secret"},
            json={"device_id": "device-a", "lease_token": claim["lease_token"]},
        )

        assert renew.status_code == 200
        renewed_lock = session.get(WorkspaceExecutionLock, 1)
        assert renewed_lock.lease_expires_at > old_lock_expiry


def test_cancelled_running_run_releases_workspace_lock_after_agent_completion(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_TOKEN", "agent-secret")
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")
        created = client.post(
            "/runs",
            json={
                "project_id": project.id,
                "workspace_id": workspace.id,
                "prompt": "long write",
                "sandbox": "workspace-write",
            },
        ).json()
        claim = client.post(
            "/agent/commands/claim",
            headers={"X-Agent-Token": "agent-secret"},
            json={"device_id": "device-a", "claim_request_id": "claim-cancel"},
        ).json()
        client.post(
            f"/agent/commands/{created['command_id']}/ack",
            headers={"X-Agent-Token": "agent-secret"},
            json={"device_id": "device-a", "lease_token": claim["lease_token"]},
        )
        cancel = client.post(f"/runs/{created['id']}/cancel")
        complete = client.post(
            f"/agent/commands/{created['command_id']}/complete",
            headers={"X-Agent-Token": "agent-secret"},
            json={
                "device_id": "device-a",
                "lease_token": claim["lease_token"],
                "status": AgentCommandStatus.FAILED.value,
                "error_message": "run cancelled",
            },
        )
        next_run = client.post(
            "/runs",
            json={
                "project_id": project.id,
                "workspace_id": workspace.id,
                "prompt": "after cancel",
                "sandbox": "workspace-write",
            },
        )

        assert cancel.status_code == 200
        assert cancel.json()["cancel_requested"] is True
        assert complete.status_code == 200
        assert complete.json()["status"] == AgentCommandStatus.CANCELLED.value
        run = session.get(Run, created["id"])
        assert run.status == RunStatus.CANCELLED
        assert session.exec(select(WorkspaceExecutionLock)).all()[0].owner_id == str(next_run.json()["id"])
        assert next_run.status_code == 200


def test_closing_write_session_releases_workspace_lock() -> None:
    for client, session in make_client():
        project = add_project(session)
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")
        app_thread = client.post(
            "/app-threads",
            json={
                "project_id": project.id,
                "workspace_id": workspace.id,
                "title": "Write session",
                "sandbox": "workspace-write",
            },
        ).json()

        close = client.delete(f"/app-threads/{app_thread['id']}")
        run = client.post(
            "/runs",
            json={
                "project_id": project.id,
                "workspace_id": workspace.id,
                "prompt": "after close",
                "sandbox": "workspace-write",
            },
        )

        assert close.status_code == 200
        assert run.status_code == 200
