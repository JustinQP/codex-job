from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

import pytest

from agent.api_client import AgentApiClient, AgentApiError
from agent.heartbeat import build_heartbeat_payload, build_register_payload
from agent.identity import AgentIdentity
from backend.models import AgentCommandStatus
from backend.schemas import (
    AgentCommandClaimRequest,
    AgentCommandCompleteRequest,
    AgentCommandEventUploadItem,
    AgentCommandEventsUploadRequest,
    AgentCommandLeaseRequest,
    AgentReconcileRequest,
    DeviceHeartbeat,
    DeviceRegister,
    RunArtifactUpload,
    RunLogChunkUpload,
    WorkspaceSyncItem,
    WorkspaceSyncRequest,
)


class AgentClientHandler(BaseHTTPRequestHandler):
    calls: list[tuple[str, str | None, dict]] = []

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or "0")
        body = self.rfile.read(length).decode("utf-8")
        payload = json.loads(body) if body else {}
        self.__class__.calls.append(
            (self.path, self.headers.get("X-Agent-Token"), payload)
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "path": self.path}).encode("utf-8"))

    def log_message(self, format, *args) -> None:
        return


def serve():
    AgentClientHandler.calls = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), AgentClientHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_agent_api_client_sends_agent_token_and_json() -> None:
    server = serve()
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        client = AgentApiClient(base_url=base_url, agent_token="secret")

        registered = client.register(
            DeviceRegister(
                device_id="device-a",
                display_name="Desk",
                hostname="host",
                os_name="Windows",
                agent_version="0.1.0",
            )
        )
        heartbeat = client.heartbeat(DeviceHeartbeat(device_id="device-a"))
        synced = client.sync_workspaces(
            WorkspaceSyncRequest(
                device_id="device-a",
                workspaces=[
                    WorkspaceSyncItem(
                        workspace_key="repo",
                        name="Repo",
                        path_label="repo",
                    )
                ],
            )
        )
        claim = client.claim_command(
            AgentCommandClaimRequest(device_id="device-a", claim_request_id="claim-1")
        )
        ack = client.ack_command(
            "cmd-1",
            AgentCommandLeaseRequest(device_id="device-a", lease_token="lease-a"),
        )
        renew = client.renew_command(
            "cmd-1",
            AgentCommandLeaseRequest(device_id="device-a", lease_token="lease-a"),
        )
        complete = client.complete_command(
            "cmd-1",
            AgentCommandCompleteRequest(
                device_id="device-a",
                lease_token="lease-a",
                status=AgentCommandStatus.SUCCESS,
                result_payload={"ok": True},
            ),
        )
        events = client.upload_command_events(
            "cmd-1",
            AgentCommandEventsUploadRequest(
                device_id="device-a",
                lease_token="lease-a",
                events=[
                    AgentCommandEventUploadItem(
                        sequence=1,
                        kind="log",
                        payload={"text": "hello"},
                        created_at="2026-06-22T00:00:00+00:00",
                    )
                ],
            ),
        )
        reconcile = client.reconcile(
            AgentReconcileRequest(
                device_id="device-a",
                command_id="cmd-1",
                process_status="STARTING",
            )
        )
        log_chunk = client.upload_run_log_chunk(
            1,
            RunLogChunkUpload(
                device_id="device-a",
                command_id="cmd-1",
                offset=0,
                content="hello",
            ),
        )
        artifact = client.upload_run_artifact(
            1,
            RunArtifactUpload(
                device_id="device-a",
                command_id="cmd-1",
                artifact_type="result",
                filename="result.md",
                sequence=1,
                size_bytes=5,
                sha256="0" * 64,
                content="hello",
            ),
        )

        assert registered == {"ok": True, "path": "/agent/register"}
        assert heartbeat == {"ok": True, "path": "/agent/heartbeat"}
        assert synced == {"ok": True, "path": "/agent/workspaces/sync"}
        assert claim == {"ok": True, "path": "/agent/commands/claim"}
        assert ack == {"ok": True, "path": "/agent/commands/cmd-1/ack"}
        assert renew == {"ok": True, "path": "/agent/commands/cmd-1/renew"}
        assert complete == {"ok": True, "path": "/agent/commands/cmd-1/complete"}
        assert events == {"ok": True, "path": "/agent/commands/cmd-1/events"}
        assert reconcile == {"ok": True, "path": "/agent/reconcile"}
        assert log_chunk == {"ok": True, "path": "/agent/runs/1/log-chunks"}
        assert artifact == {"ok": True, "path": "/agent/runs/1/artifacts"}
        assert AgentClientHandler.calls[0][0] == "/agent/register"
        assert AgentClientHandler.calls[0][1] == "secret"
        assert AgentClientHandler.calls[0][2]["device_id"] == "device-a"
        assert AgentClientHandler.calls[1][0] == "/agent/heartbeat"
        assert AgentClientHandler.calls[1][2] == {"device_id": "device-a"}
        assert AgentClientHandler.calls[2][0] == "/agent/workspaces/sync"
        assert AgentClientHandler.calls[2][2]["workspaces"][0]["workspace_key"] == "repo"
        assert AgentClientHandler.calls[3][0] == "/agent/commands/claim"
        assert AgentClientHandler.calls[3][2]["claim_request_id"] == "claim-1"
        assert AgentClientHandler.calls[4][0] == "/agent/commands/cmd-1/ack"
        assert AgentClientHandler.calls[5][0] == "/agent/commands/cmd-1/renew"
        assert AgentClientHandler.calls[6][0] == "/agent/commands/cmd-1/complete"
        assert AgentClientHandler.calls[6][2]["result_payload"] == {"ok": True}
        assert AgentClientHandler.calls[7][0] == "/agent/commands/cmd-1/events"
        assert AgentClientHandler.calls[7][2]["events"][0]["sequence"] == 1
        assert AgentClientHandler.calls[8][0] == "/agent/reconcile"
        assert AgentClientHandler.calls[8][2]["command_id"] == "cmd-1"
        assert AgentClientHandler.calls[9][0] == "/agent/runs/1/log-chunks"
        assert AgentClientHandler.calls[9][2]["offset"] == 0
        assert AgentClientHandler.calls[10][0] == "/agent/runs/1/artifacts"
        assert AgentClientHandler.calls[10][2]["artifact_type"] == "result"
    finally:
        server.shutdown()


def test_agent_api_client_requires_token() -> None:
    with pytest.raises(AgentApiError, match="AGENT_TOKEN"):
        AgentApiClient(base_url="http://127.0.0.1:1", agent_token=None)


def test_heartbeat_payload_uses_stable_identity() -> None:
    identity = AgentIdentity(
        device_id="device-a",
        display_name="Desk",
        created_at="2026-01-01T00:00:00+00:00",
    )

    register_payload = build_register_payload(identity)
    heartbeat_payload = build_heartbeat_payload(identity)

    assert register_payload.device_id == "device-a"
    assert register_payload.display_name == "Desk"
    assert heartbeat_payload.device_id == "device-a"
    assert heartbeat_payload.display_name == "Desk"
    assert "codex_exec" in (register_payload.capabilities_json or "")
