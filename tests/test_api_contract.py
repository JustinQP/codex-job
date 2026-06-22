from __future__ import annotations

from backend.main import app


def test_openapi_keeps_core_routes_after_router_split() -> None:
    schema = app.openapi()
    paths = set(schema["paths"])

    expected_paths = {
        "/health",
        "/projects",
        "/tasks",
        "/runs",
        "/tasks/{task_id}",
        "/tasks/{task_id}/rerun",
        "/tasks/{task_id}/cancel",
        "/tasks/{task_id}/artifacts",
        "/tasks/{task_id}/log",
        "/tasks/{task_id}/result",
        "/tasks/{task_id}/diff",
        "/tasks/{task_id}/artifacts/git-status",
        "/tasks/{task_id}/artifacts/report",
        "/task-templates",
        "/runners",
        "/runner/register",
        "/runner/heartbeat",
        "/runner/tasks/claim",
        "/runner/tasks/{task_id}/finish",
        "/runner/tasks/{task_id}/cancel-state",
        "/app-server-bridge/health",
        "/agent/register",
        "/agent/heartbeat",
        "/agent/workspaces/sync",
        "/agent/commands/claim",
        "/agent/commands/{command_id}/ack",
        "/agent/commands/{command_id}/renew",
        "/agent/commands/{command_id}/complete",
        "/agent/commands/{command_id}/events",
        "/agent/reconcile",
        "/agent/runs/{task_id}/log-chunks",
        "/agent/runs/{task_id}/artifacts",
        "/devices",
        "/devices/{device_id}",
        "/workspaces",
        "/workspaces/{workspace_id}",
        "/app-threads",
        "/app-threads/{app_thread_id}",
        "/app-threads/{app_thread_id}/reopen",
        "/app-threads/{app_thread_id}/turns",
        "/app-threads/{app_thread_id}/turns/async",
        "/app-turns/{app_turn_id}",
        "/app-turns/{app_turn_id}/events",
        "/app-turns/{app_turn_id}/stream",
        "/app-turns/{app_turn_id}/cancel",
    }

    assert expected_paths <= paths
    assert len(paths) >= len(expected_paths)
