from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections.abc import Generator
from pathlib import Path
import sys
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from agent.app_server.session_manager import AgentAppSessionManager
from agent.command_loop import AgentCommandLoop
from agent.identity import AgentIdentity
from agent.local_state import AgentLocalState
from agent.workspace_registry import WorkspaceRegistry
from backend import db
from backend.db import get_session
from backend.main import app
from backend.schemas import (
    AgentCommandClaimRequest,
    AgentCommandCompleteRequest,
    AgentCommandEventsUploadRequest,
    AgentCommandLeaseRequest,
    AgentReconcileRequest,
    DeviceHeartbeat,
    DeviceRegister,
    RunArtifactUpload,
    RunLogChunkUpload,
    WorkspaceSyncRequest,
)
from backend.services import run_service


API_TOKEN = "smoke-api-token"
AGENT_TOKEN = "smoke-agent-token"


class FakeJsonlRpcClient:
    def __init__(
        self,
        command: list[str],
        cwd: Path,
        events_path: Path,
        stderr_path: Path,
    ) -> None:
        self.command = command
        self.cwd = cwd
        self.events_path = events_path
        self.stderr_path = stderr_path
        self.requests: list[dict[str, Any]] = []
        self.thread_id = "smoke-codex-thread"
        self.turn_id = "smoke-codex-turn"
        self.closed = False
        self._messages: list[dict[str, Any]] = []
        self._condition = _NoopCondition()

    @property
    def message_count(self) -> int:
        return len(self._messages)

    def request(self, request_id: str, method: str, params: dict[str, Any] | None = None) -> None:
        self.requests.append({"id": request_id, "method": method, "params": params or {}})
        if method == "turn/start":
            self._messages.extend(
                [
                    {"id": request_id, "result": {"turn": {"id": self.turn_id}}},
                    {
                        "method": "agent/message_delta",
                        "params": {"turnId": self.turn_id, "itemId": "assistant", "delta": "smoke assistant"},
                    },
                    {"method": "turn/completed", "params": {"turnId": self.turn_id}},
                ]
            )

    def wait_for_response(self, request_id: str, timeout: float) -> dict[str, Any]:
        del timeout
        if request_id.endswith("-initialize"):
            return {"id": request_id, "result": {"ok": True}}
        if request_id.endswith("-thread-start"):
            return {"id": request_id, "result": {"thread": {"id": self.thread_id}}}
        if "-turn-" in request_id:
            return {"id": request_id, "result": {"turn": {"id": self.turn_id}}}
        raise RuntimeError(f"unexpected app-server response request id: {request_id}")

    def wait_for_match(self, predicate, timeout: float, start_index: int = 0):
        del timeout
        for index, message in enumerate(self._messages[start_index:], start=start_index):
            if predicate(message):
                return index, message
        raise TimeoutError("no matching fake app-server event")

    def close(self) -> None:
        self.closed = True


class _NoopCondition:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class InProcessAgentClient:
    def __init__(self, client: TestClient) -> None:
        self.client = client

    def register(self, payload: DeviceRegister) -> dict[str, Any]:
        return self._post("/agent/register", payload.model_dump())

    def heartbeat(self, payload: DeviceHeartbeat) -> dict[str, Any]:
        return self._post("/agent/heartbeat", payload.model_dump(exclude_none=True))

    def sync_workspaces(self, payload: WorkspaceSyncRequest) -> dict[str, Any]:
        return self._post("/agent/workspaces/sync", payload.model_dump(exclude_none=True))

    def claim_command(self, payload: AgentCommandClaimRequest) -> dict[str, Any] | None:
        return self._post("/agent/commands/claim", payload.model_dump(exclude_none=True))

    def ack_command(self, command_id: str, payload: AgentCommandLeaseRequest) -> dict[str, Any]:
        return self._post(f"/agent/commands/{command_id}/ack", payload.model_dump(exclude_none=True))

    def renew_command(self, command_id: str, payload: AgentCommandLeaseRequest) -> dict[str, Any]:
        return self._post(f"/agent/commands/{command_id}/renew", payload.model_dump(exclude_none=True))

    def complete_command(self, command_id: str, payload: AgentCommandCompleteRequest) -> dict[str, Any]:
        return self._post(f"/agent/commands/{command_id}/complete", payload.model_dump(exclude_none=True))

    def upload_command_events(self, command_id: str, payload: AgentCommandEventsUploadRequest) -> dict[str, Any]:
        return self._post(
            f"/agent/commands/{command_id}/events",
            payload.model_dump(mode="json", exclude_none=True),
        )

    def reconcile(self, payload: AgentReconcileRequest) -> dict[str, Any]:
        return self._post("/agent/reconcile", payload.model_dump(exclude_none=True))

    def upload_run_log_chunk(self, run_id: int, payload: RunLogChunkUpload) -> dict[str, Any]:
        return self._post(f"/agent/runs/{run_id}/log-chunks", payload.model_dump(exclude_none=True))

    def upload_run_artifact(self, run_id: int, payload: RunArtifactUpload) -> dict[str, Any]:
        return self._post(f"/agent/runs/{run_id}/artifacts", payload.model_dump(exclude_none=True))

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        response = self.client.post(path, headers={"X-Agent-Token": AGENT_TOKEN}, json=payload)
        response.raise_for_status()
        return response.json()


def run_local_e2e_smoke() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="codex-job-smoke-") as raw_tmp:
        tmp = Path(raw_tmp)
        workspace = tmp / "workspace"
        workspace.mkdir()
        registry_path = tmp / "workspaces.json"
        registry_path.write_text(
            json.dumps(
                {
                    "allowed_roots": [str(tmp)],
                    "workspaces": [
                        {
                            "key": "smoke-repo",
                            "name": "Smoke Repo",
                            "path": str(workspace),
                            "enabled": True,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(engine)
        session = Session(engine)
        old_jobs_dir = db.JOBS_DIR
        old_run_jobs_dir = run_service.JOBS_DIR
        old_api_token = os.environ.get("API_TOKEN")
        old_agent_token = os.environ.get("AGENT_TOKEN")
        old_fake_run = os.environ.get("CODEX_AGENT_FAKE_RUN")
        db.JOBS_DIR = tmp / "jobs"
        run_service.JOBS_DIR = db.JOBS_DIR
        os.environ["API_TOKEN"] = API_TOKEN
        os.environ["AGENT_TOKEN"] = AGENT_TOKEN
        os.environ["CODEX_AGENT_FAKE_RUN"] = "1"

        def override_get_session() -> Generator[Session, None, None]:
            yield session

        app.dependency_overrides[get_session] = override_get_session
        try:
            with TestClient(app) as client:
                agent_client = InProcessAgentClient(client)
                identity = AgentIdentity(
                    device_id="smoke-device",
                    display_name="Smoke Device",
                    created_at="2026-06-24T00:00:00+00:00",
                )
                registry = WorkspaceRegistry.load(registry_path)
                session_manager = AgentAppSessionManager(
                    workspace_registry=registry,
                    codex_command="fake-codex",
                    data_dir=tmp / "agent-app-server",
                    client_factory=FakeJsonlRpcClient,
                )
                loop = AgentCommandLoop(
                    client=agent_client,
                    identity=identity,
                    local_state=AgentLocalState(tmp / "agent-state.json"),
                    workspace_registry=registry,
                    app_session_manager=session_manager,
                    poll_interval_seconds=0,
                )
                loop.bootstrap()
                synced_workspace = client.get("/workspaces", headers=_api_headers()).json()[0]
                project = client.post(
                    "/projects",
                    headers=_api_headers(),
                    json={
                        "name": "Smoke Project",
                        "path": str(workspace),
                        "workspace_id": synced_workspace["id"],
                        "enabled": True,
                    },
                ).json()
                run = client.post(
                    "/runs",
                    headers=_api_headers(),
                    json={
                        "project_id": project["id"],
                        "workspace_id": synced_workspace["id"],
                        "prompt": "smoke read-only run",
                        "sandbox": "read-only",
                    },
                ).json()
                loop.run_once()
                run = client.get(f"/runs/{run['id']}", headers=_api_headers()).json()
                cancelled_run = client.post(
                    "/runs",
                    headers=_api_headers(),
                    json={
                        "project_id": project["id"],
                        "workspace_id": synced_workspace["id"],
                        "prompt": "smoke cancel run",
                        "sandbox": "read-only",
                    },
                ).json()
                cancel_response = client.post(
                    f"/runs/{cancelled_run['id']}/cancel",
                    headers=_api_headers(),
                ).json()
                loop.run_once()
                app_thread = client.post(
                    "/app-threads",
                    headers=_api_headers(),
                    json={
                        "project_id": project["id"],
                        "workspace_id": synced_workspace["id"],
                        "title": "Smoke Session",
                        "sandbox": "read-only",
                    },
                ).json()
                loop.run_once()
                app_thread = client.get(f"/app-threads/{app_thread['id']}", headers=_api_headers()).json()
                app_turn = client.post(
                    f"/app-threads/{app_thread['id']}/turns/async",
                    headers=_api_headers(),
                    json={"message": "hello smoke"},
                ).json()
                loop.run_once()
                app_turn = client.get(f"/app-turns/{app_turn['id']}", headers=_api_headers()).json()
                cancelled_turn = client.post(
                    f"/app-threads/{app_thread['id']}/turns/async",
                    headers=_api_headers(),
                    json={"message": "cancel me"},
                ).json()
                cancelled_turn = client.post(
                    f"/app-turns/{cancelled_turn['id']}/cancel",
                    headers=_api_headers(),
                ).json()
                closed_thread = client.delete(
                    f"/app-threads/{app_thread['id']}",
                    headers=_api_headers(),
                ).json()
                result = {
                    "device_id": identity.device_id,
                    "workspace_id": synced_workspace["id"],
                    "project_id": project["id"],
                    "run_status": run["status"],
                    "cancel_requested": cancel_response["cancel_requested"],
                    "app_thread_status": app_thread["status"],
                    "app_turn_status": app_turn["status"],
                    "cancelled_turn_status": cancelled_turn["status"],
                    "closed_thread_status": closed_thread["status"],
                }
                _assert_smoke_result(result)
                return result
        finally:
            app.dependency_overrides.clear()
            session.close()
            db.JOBS_DIR = old_jobs_dir
            run_service.JOBS_DIR = old_run_jobs_dir
            _restore_env("API_TOKEN", old_api_token)
            _restore_env("AGENT_TOKEN", old_agent_token)
            _restore_env("CODEX_AGENT_FAKE_RUN", old_fake_run)


def _assert_smoke_result(result: dict[str, Any]) -> None:
    expected = {
        "run_status": "SUCCESS",
        "cancel_requested": True,
        "app_thread_status": "ACTIVE",
        "app_turn_status": "SUCCESS",
        "cancelled_turn_status": "CANCELLED",
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise RuntimeError(f"smoke failed: expected {key}={value!r}, got {result.get(key)!r}")
    if result.get("closed_thread_status") not in {"CLOSING", "CLOSED"}:
        raise RuntimeError(f"smoke failed: unexpected closed thread status {result.get('closed_thread_status')!r}")


def _api_headers() -> dict[str, str]:
    return {"X-API-Token": API_TOKEN}


def _restore_env(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local in-process Codex Job E2E smoke.")
    parser.parse_args()
    result = run_local_e2e_smoke()
    print("SMOKE PASS")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
