from __future__ import annotations

from backend.main import app


def test_openapi_exposes_v2_mainline_routes() -> None:
    schema = app.openapi()
    paths = set(schema["paths"])
    expected_paths = {
        "/health",
        "/projects",
        "/runs",
        "/runs/{run_id}",
        "/runs/{run_id}/rerun",
        "/runs/{run_id}/cancel",
        "/runs/{run_id}/artifacts",
        "/runs/{run_id}/log",
        "/runs/{run_id}/result",
        "/runs/{run_id}/diff",
        "/runs/{run_id}/artifacts/git-status",
        "/runs/{run_id}/artifacts/report",
        "/run-templates",
        "/agent/register",
        "/agent/heartbeat",
        "/agent/workspaces/sync",
        "/agent/commands/claim",
        "/agent/commands/{command_id}/ack",
        "/agent/commands/{command_id}/renew",
        "/agent/commands/{command_id}/complete",
        "/agent/commands/{command_id}/events",
        "/agent/reconcile",
        "/agent/runs/{run_id}/log-chunks",
        "/agent/runs/{run_id}/artifacts",
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


def test_openapi_removes_legacy_runner_task_bridge_routes() -> None:
    schema = app.openapi()
    paths = set(schema["paths"])
    removed_paths = {
        "/tasks",
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
        "/runner/tasks/{task_id}/log",
        "/runner/tasks/{task_id}/artifacts",
        "/runner/tasks/{task_id}/finish",
        "/runner/tasks/{task_id}/cancel-state",
        "/app-server-bridge/health",
    }

    assert paths.isdisjoint(removed_paths)
