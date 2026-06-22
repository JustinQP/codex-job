from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

import pytest

from agent.api_client import AgentApiClient, AgentApiError
from agent.heartbeat import build_heartbeat_payload, build_register_payload
from agent.identity import AgentIdentity
from backend.schemas import DeviceHeartbeat, DeviceRegister


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

        assert registered == {"ok": True, "path": "/agent/register"}
        assert heartbeat == {"ok": True, "path": "/agent/heartbeat"}
        assert AgentClientHandler.calls[0][0] == "/agent/register"
        assert AgentClientHandler.calls[0][1] == "secret"
        assert AgentClientHandler.calls[0][2]["device_id"] == "device-a"
        assert AgentClientHandler.calls[1][0] == "/agent/heartbeat"
        assert AgentClientHandler.calls[1][2] == {"device_id": "device-a"}
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
