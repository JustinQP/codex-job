from __future__ import annotations

import json
import threading
from collections.abc import Generator
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from backend.services.app_server_bridge_client import (
    AppServerBridgeClient,
    AppServerBridgeError,
)


class BridgeClientTestHandler(BaseHTTPRequestHandler):
    requests: list[dict[str, Any]] = []

    def do_GET(self) -> None:
        self._record()
        if self.path == "/health":
            self._json({"status": "ok", "mode": "poc"})
            return
        if self.path == "/threads":
            self._json({"threads": []})
            return
        if self.path == "/threads/thread-1":
            self._json({"bridge_thread_id": "thread-1"})
            return
        if self.path == "/threads/thread-1/final":
            self._json({"assistant_final": "done"})
            return
        if self.path == "/threads/thread-1/events":
            self._json({"summary": {"total_events": 1}})
            return
        if self.path == "/http-error":
            self._json(
                {
                    "error": {"code": "bridge_failed", "message": "Bridge failed"},
                    "detail": "Bridge failed",
                    "step": "turn/start",
                },
                status=HTTPStatus.BAD_GATEWAY,
            )
            return
        if self.path == "/invalid-json":
            self._raw("not-json")
            return
        self._json({"error": {"code": "not_found", "message": "missing"}}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        self._record()
        if self.path == "/threads":
            body = self._body()
            self._json(
                {
                    "bridge_thread_id": "thread-1",
                    "app_thread_id": "app-thread-1",
                    "title": body.get("title"),
                },
                status=HTTPStatus.CREATED,
            )
            return
        if self.path == "/threads/thread-1/turns":
            self._json({"turn_id": "turn-1", "assistant_final_preview": "done"})
            return
        self._json({"error": {"code": "not_found", "message": "missing"}}, status=HTTPStatus.NOT_FOUND)

    def do_PATCH(self) -> None:
        self._record()
        if self.path == "/threads/thread-1":
            self._json({"bridge_thread_id": "thread-1", "title": self._body().get("title")})
            return
        self._json({"error": {"code": "not_found", "message": "missing"}}, status=HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:
        self._record()
        if self.path == "/threads/thread-1":
            self._json({"closed": True})
            return
        self._json({"error": {"code": "not_found", "message": "missing"}}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _record(self) -> None:
        self.requests.append(
            {
                "method": self.command,
                "path": self.path,
                "token": self.headers.get("X-Bridge-Token"),
            }
        )

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _raw(self, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def bridge_http_server() -> Generator[str, None, None]:
    BridgeClientTestHandler.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), BridgeClientTestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_bridge_client_success_methods_send_token() -> None:
    for base_url in bridge_http_server():
        client = AppServerBridgeClient(base_url=base_url, token="secret", timeout_seconds=5)

        assert client.get_health()["status"] == "ok"
        assert client.create_thread("title")["bridge_thread_id"] == "thread-1"
        assert client.list_threads()["threads"] == []
        assert client.get_thread("thread-1")["bridge_thread_id"] == "thread-1"
        assert client.rename_thread("thread-1", "new")["title"] == "new"
        assert client.send_turn("thread-1", "hello")["turn_id"] == "turn-1"
        assert client.get_final("thread-1")["assistant_final"] == "done"
        assert client.get_events("thread-1")["summary"]["total_events"] == 1
        assert client.delete_thread("thread-1")["closed"] is True

        assert BridgeClientTestHandler.requests
        assert all(request["token"] == "secret" for request in BridgeClientTestHandler.requests)


def test_bridge_client_http_error_to_custom_error() -> None:
    for base_url in bridge_http_server():
        client = AppServerBridgeClient(base_url=base_url, token="super-secret", timeout_seconds=5)

        try:
            client._request("GET", "/http-error")
        except AppServerBridgeError as exc:
            assert exc.status_code == 502
            assert exc.code == "bridge_failed"
            assert exc.message == "Bridge failed"
            assert exc.step == "turn/start"
            assert "super-secret" not in str(exc)
        else:
            raise AssertionError("expected AppServerBridgeError")


def test_bridge_client_network_error_to_custom_error() -> None:
    client = AppServerBridgeClient(base_url="http://127.0.0.1:1", timeout_seconds=0.2)

    try:
        client.get_health()
    except AppServerBridgeError as exc:
        assert exc.code == "network_error"
        assert exc.status_code is None
    else:
        raise AssertionError("expected AppServerBridgeError")


def test_bridge_client_invalid_json_to_custom_error() -> None:
    for base_url in bridge_http_server():
        client = AppServerBridgeClient(base_url=base_url, timeout_seconds=5)

        try:
            client._request("GET", "/invalid-json")
        except AppServerBridgeError as exc:
            assert exc.code == "invalid_json"
            assert exc.step == "parse_json"
        else:
            raise AssertionError("expected AppServerBridgeError")
