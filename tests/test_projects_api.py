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
