from __future__ import annotations

import argparse
import atexit
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock, RLock
from typing import Any
from urllib.parse import urlparse

from app_server_event_parser import extract_assistant_text, load_events, summarize_events, write_summary
from app_server_stdio_client import JsonlRpcClient, extract_thread_id, response_result


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8766
DEFAULT_CODEX_COMMAND = "codex.cmd"
DEFAULT_TIMEOUT_SECONDS = 180.0
DEVELOPER_INSTRUCTIONS = "Do not modify files. Reply only to the user request."


@dataclass
class BridgeThread:
    bridge_thread_id: str
    app_thread_id: str
    client: JsonlRpcClient
    run_dir: Path
    raw_events_path: Path
    stderr_path: Path
    created_at: str
    updated_at: str
    turn_count: int = 0
    status: str = "idle"
    last_turn_id: str | None = None
    last_assistant_final: str = ""
    last_summary: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    lock: Lock = field(default_factory=Lock)


class BridgeState:
    def __init__(self, repo_root: Path, codex_command: str, timeout: float, token: str | None) -> None:
        self.repo_root = repo_root
        self.script_dir = Path(__file__).resolve().parent
        self.bridge_runs_dir = self.script_dir / "bridge-runs"
        self.codex_command = codex_command
        self.timeout = timeout
        self.token = token
        self.threads: dict[str, BridgeThread] = {}
        self.lock = RLock()

    def create_thread(self) -> BridgeThread:
        bridge_thread_id = str(uuid.uuid4())
        run_dir = self.bridge_runs_dir / bridge_thread_id
        run_dir.mkdir(parents=True, exist_ok=False)
        raw_events_path = run_dir / "_all-events.jsonl"
        stderr_path = run_dir / "stderr.log"
        command = [self.codex_command, "app-server", "--listen", "stdio://"]
        client = JsonlRpcClient(command, self.repo_root, raw_events_path, stderr_path)

        try:
            client.request(
                f"{bridge_thread_id}-initialize",
                "initialize",
                {
                    "clientInfo": {
                        "name": "codex-job-app-server-http-bridge-poc",
                        "title": "codex-job app-server HTTP Bridge POC",
                        "version": "0.4.0",
                    },
                    "capabilities": {
                        "experimentalApi": True,
                    },
                },
            )
            initialize_response = client.wait_for_response(f"{bridge_thread_id}-initialize", timeout=30)
            response_result(initialize_response, "initialize")

            client.request(
                f"{bridge_thread_id}-thread-start",
                "thread/start",
                {
                    "cwd": str(self.repo_root),
                    "approvalPolicy": "never",
                    "sandbox": "read-only",
                    "sessionStartSource": "startup",
                    "threadSource": "codex-job-app-server-bridge-poc",
                    "ephemeral": True,
                    "developerInstructions": DEVELOPER_INSTRUCTIONS,
                },
            )
            thread_start_response = client.wait_for_response(f"{bridge_thread_id}-thread-start", timeout=60)
            thread_start_result = response_result(thread_start_response, "thread/start")
            app_thread_id = extract_thread_id(thread_start_result)
        except Exception:
            client.close()
            raise

        now = _utc_now()
        bridge_thread = BridgeThread(
            bridge_thread_id=bridge_thread_id,
            app_thread_id=app_thread_id,
            client=client,
            run_dir=run_dir,
            raw_events_path=raw_events_path,
            stderr_path=stderr_path,
            created_at=now,
            updated_at=now,
        )
        with self.lock:
            self.threads[bridge_thread_id] = bridge_thread
        return bridge_thread

    def get_thread(self, bridge_thread_id: str) -> BridgeThread | None:
        with self.lock:
            return self.threads.get(bridge_thread_id)

    def close_all(self) -> None:
        with self.lock:
            threads = list(self.threads.values())
            self.threads.clear()
        for bridge_thread in threads:
            bridge_thread.status = "closed"
            bridge_thread.client.close()


STATE: BridgeState | None = None


class BridgeRequestHandler(BaseHTTPRequestHandler):
    server_version = "CodexAppServerBridgePOC/0.4"

    def do_GET(self) -> None:
        route = self._route()
        if route == ["health"]:
            self._send_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "service": "app-server-bridge-poc",
                    "threads": len(_state().threads),
                    "token_required": bool(_state().token),
                },
            )
            return

        if not self._check_auth():
            return

        if len(route) == 2 and route[0] == "threads":
            self._handle_get_thread(route[1])
            return
        if len(route) == 3 and route[0] == "threads" and route[2] == "events":
            self._handle_get_events(route[1])
            return
        if len(route) == 3 and route[0] == "threads" and route[2] == "final":
            self._handle_get_final(route[1])
            return

        self._send_error_json(HTTPStatus.NOT_FOUND, "not_found", "Route not found.")

    def do_POST(self) -> None:
        route = self._route()
        if route == ["health"]:
            self._send_error_json(HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed", "Use GET /health.")
            return

        if not self._check_auth():
            return

        if route == ["threads"]:
            self._handle_create_thread()
            return
        if len(route) == 3 and route[0] == "threads" and route[2] == "turns":
            self._handle_create_turn(route[1])
            return

        self._send_error_json(HTTPStatus.NOT_FOUND, "not_found", "Route not found.")

    def log_message(self, format: str, *args: Any) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {self.address_string()} {format % args}")

    def _handle_create_thread(self) -> None:
        try:
            bridge_thread = _state().create_thread()
        except Exception as exc:
            self._send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, "thread_create_failed", str(exc))
            return

        self._send_json(
            HTTPStatus.CREATED,
            {
                "bridge_thread_id": bridge_thread.bridge_thread_id,
                "app_thread_id": bridge_thread.app_thread_id,
                "status": bridge_thread.status,
                "created_at": bridge_thread.created_at,
                "run_dir": str(bridge_thread.run_dir),
            },
        )

    def _handle_create_turn(self, bridge_thread_id: str) -> None:
        bridge_thread = _state().get_thread(bridge_thread_id)
        if bridge_thread is None:
            self._send_error_json(HTTPStatus.NOT_FOUND, "thread_not_found", "Unknown bridge thread id.")
            return

        body = self._read_json_body()
        if body is None:
            return
        message = body.get("message")
        if not isinstance(message, str) or not message.strip():
            self._send_error_json(HTTPStatus.BAD_REQUEST, "invalid_message", "JSON body must include a non-empty string field: message.")
            return

        with bridge_thread.lock:
            try:
                result = _run_turn(bridge_thread, message.strip(), _state().repo_root, _state().timeout)
            except Exception as exc:
                bridge_thread.status = "error"
                bridge_thread.errors.append(str(exc))
                bridge_thread.updated_at = _utc_now()
                self._send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, "turn_failed", str(exc))
                return

        self._send_json(HTTPStatus.OK, result)

    def _handle_get_thread(self, bridge_thread_id: str) -> None:
        bridge_thread = _state().get_thread(bridge_thread_id)
        if bridge_thread is None:
            self._send_error_json(HTTPStatus.NOT_FOUND, "thread_not_found", "Unknown bridge thread id.")
            return
        self._send_json(HTTPStatus.OK, _thread_status(bridge_thread))

    def _handle_get_events(self, bridge_thread_id: str) -> None:
        bridge_thread = _state().get_thread(bridge_thread_id)
        if bridge_thread is None:
            self._send_error_json(HTTPStatus.NOT_FOUND, "thread_not_found", "Unknown bridge thread id.")
            return

        turn_dir = _latest_turn_dir(bridge_thread)
        if turn_dir is None:
            self._send_json(
                HTTPStatus.OK,
                {
                    "bridge_thread_id": bridge_thread.bridge_thread_id,
                    "turn_count": bridge_thread.turn_count,
                    "events": None,
                    "message": "No turns have completed yet.",
                },
            )
            return

        events_path = turn_dir / "events.jsonl"
        events = load_events(events_path)
        summary = summarize_events(events)
        self._send_json(
            HTTPStatus.OK,
            {
                "bridge_thread_id": bridge_thread.bridge_thread_id,
                "app_thread_id": bridge_thread.app_thread_id,
                "turn_count": bridge_thread.turn_count,
                "latest_turn_dir": str(turn_dir),
                "events_path": str(events_path),
                "summary": summary,
            },
        )

    def _handle_get_final(self, bridge_thread_id: str) -> None:
        bridge_thread = _state().get_thread(bridge_thread_id)
        if bridge_thread is None:
            self._send_error_json(HTTPStatus.NOT_FOUND, "thread_not_found", "Unknown bridge thread id.")
            return
        self._send_json(
            HTTPStatus.OK,
            {
                "bridge_thread_id": bridge_thread.bridge_thread_id,
                "app_thread_id": bridge_thread.app_thread_id,
                "turn_count": bridge_thread.turn_count,
                "assistant_final": bridge_thread.last_assistant_final,
            },
        )

    def _route(self) -> list[str]:
        parsed = urlparse(self.path)
        return [part for part in parsed.path.strip("/").split("/") if part]

    def _check_auth(self) -> bool:
        token = _state().token
        if not token:
            return True
        if self.headers.get("X-Bridge-Token") == token:
            return True
        self._send_error_json(HTTPStatus.UNAUTHORIZED, "unauthorized", "Missing or invalid X-Bridge-Token.")
        return False

    def _read_json_body(self) -> dict[str, Any] | None:
        content_length = self.headers.get("Content-Length")
        if not content_length:
            return {}
        try:
            length = int(content_length)
        except ValueError:
            self._send_error_json(HTTPStatus.BAD_REQUEST, "invalid_content_length", "Invalid Content-Length.")
            return None
        raw_body = self.rfile.read(length)
        try:
            parsed = json.loads(raw_body.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            self._send_error_json(HTTPStatus.BAD_REQUEST, "invalid_json", str(exc))
            return None
        if not isinstance(parsed, dict):
            self._send_error_json(HTTPStatus.BAD_REQUEST, "invalid_json_body", "JSON body must be an object.")
            return None
        return parsed

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8", errors="replace")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_error_json(self, status: HTTPStatus, code: str, message: str) -> None:
        self._send_json(
            status,
            {
                "error": {
                    "code": code,
                    "message": message,
                }
            },
        )


def _run_turn(
    bridge_thread: BridgeThread,
    message: str,
    repo_root: Path,
    timeout: float,
) -> dict[str, Any]:
    bridge_thread.status = "running"
    bridge_thread.updated_at = _utc_now()
    turn_number = bridge_thread.turn_count + 1
    request_id = f"{bridge_thread.bridge_thread_id}-turn-{turn_number}-start"
    start_index = bridge_thread.client.message_count

    bridge_thread.client.request(
        request_id,
        "turn/start",
        {
            "threadId": bridge_thread.app_thread_id,
            "cwd": str(repo_root),
            "approvalPolicy": "never",
            "sandboxPolicy": {
                "type": "readOnly",
                "networkAccess": False,
            },
            "clientUserMessageId": f"{request_id}-user-message-{int(time.time())}",
            "input": [
                {
                    "type": "text",
                    "text": message,
                }
            ],
        },
    )
    turn_start_response = bridge_thread.client.wait_for_response(request_id, timeout=60)
    turn_id = _extract_turn_id(response_result(turn_start_response, "turn/start"))

    deadline = time.monotonic() + timeout
    next_index = start_index
    while time.monotonic() < deadline:
        message_index, event = bridge_thread.client.wait_for_match(
            lambda item: _is_turn_completed(item, turn_id),
            timeout=max(0.1, deadline - time.monotonic()),
            start_index=next_index,
        )
        next_index = message_index + 1
        if _is_turn_completed(event, turn_id):
            break
    else:
        raise TimeoutError(f"timed out waiting for turn/completed: {turn_id}")

    all_events = _client_messages(bridge_thread.client)
    turn_events = _events_for_turn(all_events, turn_id, request_id)
    turn_dir = bridge_thread.run_dir / f"turn-{turn_number}"
    turn_dir.mkdir(parents=True, exist_ok=True)
    _write_events_jsonl(turn_dir / "events.jsonl", turn_events)
    summary = write_summary(turn_dir, turn_events)
    assistant_final = extract_assistant_text(turn_events)

    bridge_thread.turn_count = turn_number
    bridge_thread.last_turn_id = turn_id
    bridge_thread.last_assistant_final = assistant_final
    bridge_thread.last_summary = summary
    bridge_thread.status = "idle"
    bridge_thread.updated_at = _utc_now()

    return {
        "bridge_thread_id": bridge_thread.bridge_thread_id,
        "app_thread_id": bridge_thread.app_thread_id,
        "turn_id": turn_id,
        "turn_count": bridge_thread.turn_count,
        "status": bridge_thread.status,
        "assistant_final_preview": assistant_final[:500],
        "turn_dir": str(turn_dir),
        "summary": summary,
    }


def _thread_status(bridge_thread: BridgeThread) -> dict[str, Any]:
    return {
        "bridge_thread_id": bridge_thread.bridge_thread_id,
        "app_thread_id": bridge_thread.app_thread_id,
        "status": bridge_thread.status,
        "turn_count": bridge_thread.turn_count,
        "created_at": bridge_thread.created_at,
        "updated_at": bridge_thread.updated_at,
        "run_dir": str(bridge_thread.run_dir),
        "last_turn_id": bridge_thread.last_turn_id,
        "errors": bridge_thread.errors,
    }


def _latest_turn_dir(bridge_thread: BridgeThread) -> Path | None:
    if bridge_thread.turn_count <= 0:
        return None
    turn_dir = bridge_thread.run_dir / f"turn-{bridge_thread.turn_count}"
    return turn_dir if turn_dir.exists() else None


def _extract_turn_id(turn_start_result: Any) -> str:
    if not isinstance(turn_start_result, dict):
        raise RuntimeError("turn/start result is not an object")
    turn = turn_start_result.get("turn")
    if not isinstance(turn, dict):
        raise RuntimeError("turn/start result.turn is not an object")
    turn_id = turn.get("id")
    if not isinstance(turn_id, str) or not turn_id:
        raise RuntimeError("turn/start result.turn.id is missing")
    return turn_id


def _events_for_turn(events: list[dict[str, Any]], turn_id: str, request_id: str) -> list[dict[str, Any]]:
    return [
        event
        for event in events
        if event.get("id") == request_id or _event_turn_id(event) == turn_id
    ]


def _is_turn_completed(event: dict[str, Any], turn_id: str) -> bool:
    return _event_name(event) == "turn/completed" and _event_turn_id(event) == turn_id


def _event_turn_id(event: dict[str, Any]) -> str | None:
    result = event.get("result")
    if isinstance(result, dict):
        turn = result.get("turn")
        if isinstance(turn, dict) and isinstance(turn.get("id"), str):
            return turn["id"]
        if isinstance(result.get("turnId"), str):
            return result["turnId"]

    params = event.get("params")
    if isinstance(params, dict):
        if isinstance(params.get("turnId"), str):
            return params["turnId"]
        turn = params.get("turn")
        if isinstance(turn, dict) and isinstance(turn.get("id"), str):
            return turn["id"]
    return None


def _event_name(event: dict[str, Any]) -> str:
    for key in ("method", "type", "event"):
        value = event.get(key)
        if isinstance(value, str):
            return value
    if "id" in event and ("result" in event or "error" in event):
        return "response"
    return "unknown"


def _client_messages(client: JsonlRpcClient) -> list[dict[str, Any]]:
    with client._condition:
        return list(client._messages)


def _write_events_jsonl(path: Path, events: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", errors="replace") as file:
        for event in events:
            file.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state() -> BridgeState:
    if STATE is None:
        raise RuntimeError("Bridge state is not initialized")
    return STATE


def build_server(host: str, port: int, codex_command: str, timeout: float, token: str | None) -> ThreadingHTTPServer:
    global STATE
    repo_root = Path(__file__).resolve().parent.parent.parent
    STATE = BridgeState(repo_root=repo_root, codex_command=codex_command, timeout=timeout, token=token)
    atexit.register(STATE.close_all)
    return ThreadingHTTPServer((host, port), BridgeRequestHandler)


def main() -> int:
    parser = argparse.ArgumentParser(description="Minimal HTTP bridge for Codex App Server POC.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host to bind. Use 127.0.0.1 by default.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to bind.")
    parser.add_argument("--codex-command", default=os.environ.get("CODEX_COMMAND", DEFAULT_CODEX_COMMAND), help="Codex command path.")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS, help="Turn completion timeout in seconds.")
    args = parser.parse_args()

    token = os.environ.get("APP_SERVER_BRIDGE_TOKEN") or None
    server = build_server(args.host, args.port, args.codex_command, args.timeout, token)
    print(f"App Server Bridge listening on http://{args.host}:{args.port}")
    print(f"codex_command={args.codex_command}")
    print(f"token_required={str(bool(token)).lower()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping App Server Bridge...")
    finally:
        server.server_close()
        _state().close_all()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
