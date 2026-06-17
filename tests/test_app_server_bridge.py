from __future__ import annotations

import json
import sys
import threading
import urllib.error
import urllib.request
from collections.abc import Generator
from pathlib import Path
from typing import Any


APP_SERVER_DIR = Path(__file__).resolve().parents[1] / "poc" / "app_server"
if str(APP_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(APP_SERVER_DIR))

import app_server_bridge as bridge  # noqa: E402


class FakeProcess:
    returncode = None

    def poll(self) -> None:
        return None


class FakeJsonlRpcClient:
    instances: list["FakeJsonlRpcClient"] = []

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
        self._messages: list[dict[str, Any]] = []
        self._condition = threading.Condition()
        self.process = FakeProcess()
        self.closed = False
        self.thread_id = f"app-thread-{len(self.instances) + 1}"
        self.turn_counter = 0
        self.instances.append(self)

    @property
    def message_count(self) -> int:
        with self._condition:
            return len(self._messages)

    def request(self, request_id: str, method: str, params: dict[str, Any] | None = None) -> None:
        if method == "initialize":
            self._append({"id": request_id, "result": {"ok": True}})
            return
        if method == "thread/start":
            self._append({"id": request_id, "result": {"thread": {"id": self.thread_id}}})
            return
        if method == "turn/start":
            self.turn_counter += 1
            turn_id = f"turn-{self.turn_counter}"
            message = _input_text(params)
            assistant_text = f"assistant:{message}"
            self._append({"id": request_id, "result": {"turn": {"id": turn_id}}})
            self._append(
                {
                    "method": "agent/message_delta",
                    "params": {
                        "turnId": turn_id,
                        "itemId": f"item-{self.turn_counter}",
                        "delta": assistant_text,
                    },
                }
            )
            self._append({"method": "turn/completed", "params": {"turnId": turn_id}})
            return
        raise AssertionError(f"unexpected method: {method}")

    def wait_for_response(self, request_id: str, timeout: float) -> dict[str, Any]:
        del timeout
        with self._condition:
            for message in self._messages:
                if message.get("id") == request_id:
                    return message
        raise TimeoutError(request_id)

    def wait_for_match(self, predicate, timeout: float, start_index: int = 0):
        del timeout
        with self._condition:
            for index, message in enumerate(self._messages[start_index:], start=start_index):
                if predicate(message):
                    return index, message
        raise TimeoutError("no matching fake message")

    def close(self) -> None:
        self.closed = True

    def _append(self, message: dict[str, Any]) -> None:
        with self._condition:
            self._messages.append(message)
            self._condition.notify_all()


def _input_text(params: dict[str, Any] | None) -> str:
    if not isinstance(params, dict):
        return ""
    input_items = params.get("input")
    if not isinstance(input_items, list) or not input_items:
        return ""
    first = input_items[0]
    if not isinstance(first, dict):
        return ""
    value = first.get("text")
    return value if isinstance(value, str) else ""


def bridge_server(
    tmp_path: Path,
    monkeypatch,
    *,
    token: str | None = None,
) -> Generator[tuple[str, bridge.BridgeState], None, None]:
    FakeJsonlRpcClient.instances.clear()
    monkeypatch.setattr(bridge, "JsonlRpcClient", FakeJsonlRpcClient)
    server = bridge.build_server(
        "127.0.0.1",
        0,
        "fake-codex.cmd",
        5.0,
        token,
        1800.0,
    )
    state = bridge._state()
    state.bridge_runs_dir = tmp_path / "bridge-runs"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}", state
    finally:
        server.shutdown()
        server.server_close()
        state.close_all()
        bridge.STATE = None
        thread.join(timeout=2)


def request_json(
    base_url: str,
    method: str,
    path: str,
    *,
    token: str | None = None,
    body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    data = None
    headers: dict[str, str] = {}
    if token is not None:
        headers["X-Bridge-Token"] = token
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    request = urllib.request.Request(f"{base_url}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_health_does_not_require_token_and_reports_status(tmp_path: Path, monkeypatch) -> None:
    for base_url, _state in bridge_server(tmp_path, monkeypatch, token="secret"):
        status, body = request_json(base_url, "GET", "/health")

        assert status == 200
        assert body["status"] == "ok"
        assert body["service"] == "app-server-bridge-poc"
        assert body["threads"] == 0
        assert body["token_required"] is True
        assert body["idle_timeout_seconds"] == 1800.0
        assert body["codex_command"] == "fake-codex.cmd"
        assert body["repo_root"]
        assert body["mode"] == "poc"
        assert body["sandbox"] == "readOnly"


def test_token_protects_threads_routes(tmp_path: Path, monkeypatch) -> None:
    for base_url, _state in bridge_server(tmp_path, monkeypatch, token="secret"):
        health_status, _ = request_json(base_url, "GET", "/health")
        missing_status, missing_body = request_json(base_url, "GET", "/threads")
        ok_status, ok_body = request_json(base_url, "GET", "/threads", token="secret")

        assert health_status == 200
        assert missing_status == 401
        assert missing_body["error"]["code"] == "unauthorized"
        assert ok_status == 200
        assert ok_body["threads"] == []


def test_threads_create_list_patch_and_delete(tmp_path: Path, monkeypatch) -> None:
    for base_url, _state in bridge_server(tmp_path, monkeypatch):
        created_status, created = request_json(
            base_url,
            "POST",
            "/threads",
            body={"title": "Custom title"},
        )
        default_status, default_thread = request_json(
            base_url,
            "POST",
            "/threads",
            body={"title": "  "},
        )
        list_status, listed = request_json(base_url, "GET", "/threads")
        patch_status, patched = request_json(
            base_url,
            "PATCH",
            f"/threads/{created['bridge_thread_id']}",
            body={"title": "Renamed"},
        )
        empty_patch_status, empty_patch = request_json(
            base_url,
            "PATCH",
            f"/threads/{created['bridge_thread_id']}",
            body={"title": ""},
        )
        missing_patch_status, _ = request_json(
            base_url,
            "PATCH",
            "/threads/missing",
            body={"title": "x"},
        )
        delete_status, deleted = request_json(
            base_url,
            "DELETE",
            f"/threads/{created['bridge_thread_id']}",
        )
        missing_delete_status, _ = request_json(base_url, "DELETE", "/threads/missing")

        assert created_status == 201
        assert created["title"] == "Custom title"
        assert created["status"] == "idle"
        assert created["bridge_thread_id"]
        assert created["app_thread_id"] == "app-thread-1"
        assert default_status == 201
        assert default_thread["title"].startswith("Thread ")
        assert list_status == 200
        assert listed["count"] == 2
        assert {"title", "status", "turn_count", "created_at", "updated_at"} <= set(listed["threads"][0])
        assert patch_status == 200
        assert patched["title"] == "Renamed"
        assert empty_patch_status == 400
        assert empty_patch["error"]["code"] == "invalid_title"
        assert missing_patch_status == 404
        assert delete_status == 200
        assert deleted["title"] == "Renamed"
        assert deleted["closed"] is True
        assert FakeJsonlRpcClient.instances[0].closed is True
        assert missing_delete_status == 404


def test_delete_conflicts_when_thread_running_or_locked(tmp_path: Path, monkeypatch) -> None:
    for base_url, state in bridge_server(tmp_path, monkeypatch):
        _, running_thread = request_json(base_url, "POST", "/threads")
        state.threads[running_thread["bridge_thread_id"]].status = "running"
        running_status, running_body = request_json(
            base_url,
            "DELETE",
            f"/threads/{running_thread['bridge_thread_id']}",
        )
        state.threads[running_thread["bridge_thread_id"]].status = "idle"

        _, locked_thread = request_json(base_url, "POST", "/threads")
        locked = state.threads[locked_thread["bridge_thread_id"]]
        locked.lock.acquire()
        try:
            locked_status, locked_body = request_json(
                base_url,
                "DELETE",
                f"/threads/{locked_thread['bridge_thread_id']}",
            )
        finally:
            locked.lock.release()

        assert running_status == 409
        assert running_body["error"]["code"] == "thread_running"
        assert locked_status == 409
        assert locked_body["error"]["code"] == "thread_running"


def test_turn_routes_and_final(tmp_path: Path, monkeypatch) -> None:
    for base_url, state in bridge_server(tmp_path, monkeypatch):
        empty_status, empty_body = request_json(base_url, "POST", "/threads/missing/turns", body={"message": ""})
        missing_status, missing_body = request_json(base_url, "POST", "/threads/missing/turns", body={"message": "hello"})
        _, created = request_json(base_url, "POST", "/threads", body={"title": "Turn thread"})
        bridge_thread_id = created["bridge_thread_id"]

        locked = state.threads[bridge_thread_id]
        locked.lock.acquire()
        try:
            conflict_status, conflict_body = request_json(
                base_url,
                "POST",
                f"/threads/{bridge_thread_id}/turns",
                body={"message": "hello"},
            )
        finally:
            locked.lock.release()

        turn_status, turn_body = request_json(
            base_url,
            "POST",
            f"/threads/{bridge_thread_id}/turns",
            body={"message": "hello"},
        )
        final_status, final_body = request_json(base_url, "GET", f"/threads/{bridge_thread_id}/final")
        missing_final_status, _ = request_json(base_url, "GET", "/threads/missing/final")

        turn_dir = Path(turn_body["turn_dir"])
        assert empty_status == 400
        assert empty_body["error"]["code"] == "invalid_message"
        assert missing_status == 404
        assert missing_body["error"]["code"] == "thread_not_found"
        assert conflict_status == 409
        assert conflict_body["error"]["code"] == "turn_conflict"
        assert turn_status == 200
        assert turn_body["assistant_final_preview"] == "assistant:hello"
        assert turn_dir.is_relative_to(tmp_path)
        assert (turn_dir / "events.jsonl").exists()
        assert (turn_dir / "run-summary.json").exists()
        assert (turn_dir / "assistant-final.md").read_text(encoding="utf-8") == "assistant:hello"
        assert final_status == 200
        assert final_body["assistant_final"] == "assistant:hello"
        assert missing_final_status == 404
