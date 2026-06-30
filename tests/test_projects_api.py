from __future__ import annotations

from tests.test_runs_api import add_device, add_workspace, make_client


def test_create_project_can_bind_remote_workspace_without_local_path() -> None:
    for client, session in make_client():
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")

        response = client.post(
            "/projects",
            json={
                "name": "Remote Repo",
                "path": "remote/repo-label",
                "workspace_id": workspace.id,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["workspace_id"] == workspace.id
        assert body["workspace_binding_status"] == "BOUND"
        assert body["path_label"] == "repo-label"


def test_update_project_defaults_and_workspace_binding() -> None:
    for client, session in make_client():
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")
        created = client.post(
            "/projects",
            json={
                "name": "Remote Repo",
                "path": "remote/repo-label",
                "workspace_id": workspace.id,
            },
        ).json()

        response = client.patch(
            f"/projects/{created['id']}",
            json={
                "name": "Remote Repo Updated",
                "enabled": False,
                "workspace_id": workspace.id,
                "default_model": "gpt-5",
                "default_reasoning_effort": "high",
                "default_sandbox": "read-only",
                "require_clean_worktree": True,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Remote Repo Updated"
        assert body["enabled"] is False
        assert body["workspace_id"] == workspace.id
        assert body["default_model"] == "gpt-5"
        assert body["default_sandbox"] == "read-only"


def test_update_workspace_defaults() -> None:
    for client, session in make_client():
        add_device(session, "device-a")
        workspace = add_workspace(session, "device-a")

        response = client.patch(
            f"/workspaces/{workspace.id}",
            json={
                "name": "Repo Updated",
                "enabled": False,
                "default_model": "gpt-5",
                "default_reasoning_effort": "medium",
                "default_sandbox": "read-only",
                "default_approval_policy": "never",
                "require_clean_worktree": True,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Repo Updated"
        assert body["enabled"] is False
        assert body["default_model"] == "gpt-5"
        assert body["require_clean_worktree"] is True


def test_update_and_disable_device_api() -> None:
    for client, session in make_client():
        add_device(session, "device-a")

        renamed = client.patch("/devices/device-a", json={"display_name": "Desk Renamed"})
        disabled = client.post("/devices/device-a/disable")

        assert renamed.status_code == 200
        assert renamed.json()["display_name"] == "Desk Renamed"
        assert disabled.status_code == 200
        assert disabled.json()["status"] == "DISABLED"
