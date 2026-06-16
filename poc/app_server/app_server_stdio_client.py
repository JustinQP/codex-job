from __future__ import annotations

import argparse
import json
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


USER_MESSAGE = "请只回复 app-server-python-ok，不要修改任何文件。"
DEFAULT_TIMEOUT_SECONDS = 180.0


class JsonlRpcClient:
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
        self._events_file = events_path.open("w", encoding="utf-8", errors="replace")
        self._stderr_file = stderr_path.open("w", encoding="utf-8", errors="replace")
        self._messages: list[dict[str, Any]] = []
        self._condition = threading.Condition()
        self._read_error: BaseException | None = None
        self._invalid_stdout_lines: list[str] = []

        try:
            self.process = subprocess.Popen(
                command,
                cwd=str(cwd),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=self._stderr_file,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except Exception:
            self._events_file.close()
            self._stderr_file.close()
            raise
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()

    @property
    def message_count(self) -> int:
        with self._condition:
            return len(self._messages)

    @property
    def invalid_stdout_lines(self) -> list[str]:
        return list(self._invalid_stdout_lines)

    def send(self, payload: dict[str, Any]) -> None:
        if self.process.stdin is None:
            raise RuntimeError("app-server stdin is not available")
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        self.process.stdin.write(line + "\n")
        self.process.stdin.flush()

    def request(self, request_id: str, method: str, params: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {"id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        self.send(payload)

    def wait_for(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        timeout: float,
        start_index: int = 0,
    ) -> dict[str, Any]:
        _, message = self.wait_for_match(predicate, timeout, start_index)
        return message

    def wait_for_match(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        timeout: float,
        start_index: int = 0,
    ) -> tuple[int, dict[str, Any]]:
        deadline = time.monotonic() + timeout
        with self._condition:
            next_index = start_index
            while True:
                while next_index < len(self._messages):
                    message_index = next_index
                    message = self._messages[next_index]
                    next_index += 1
                    if predicate(message):
                        return message_index, message

                if self._read_error is not None:
                    raise RuntimeError(f"stdout reader failed: {self._read_error}") from self._read_error

                if self.process.poll() is not None:
                    raise RuntimeError(f"app-server exited with code {self.process.returncode}")

                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("timed out waiting for app-server JSONL message")
                self._condition.wait(timeout=min(remaining, 0.5))

    def wait_for_response(self, request_id: str, timeout: float) -> dict[str, Any]:
        return self.wait_for(lambda message: message.get("id") == request_id, timeout)

    def close(self) -> None:
        if self.process.stdin is not None:
            try:
                self.process.stdin.close()
            except OSError:
                pass

        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)

        self._reader.join(timeout=2)
        self._events_file.close()
        self._stderr_file.close()

    def _read_stdout(self) -> None:
        try:
            if self.process.stdout is None:
                raise RuntimeError("app-server stdout is not available")

            for raw_line in self.process.stdout:
                stripped = raw_line.strip()
                if not stripped:
                    continue
                try:
                    message = json.loads(stripped)
                except json.JSONDecodeError:
                    self._invalid_stdout_lines.append(stripped)
                    continue

                self._events_file.write(stripped + "\n")
                self._events_file.flush()

                with self._condition:
                    self._messages.append(message)
                    self._condition.notify_all()
        except BaseException as exc:  # Keep diagnostics visible to waiters.
            self._read_error = exc
            with self._condition:
                self._condition.notify_all()


def response_result(response: dict[str, Any], step: str) -> Any:
    if "error" in response:
        raise RuntimeError(f"{step} returned error: {json.dumps(response['error'], ensure_ascii=False)}")
    if "result" not in response:
        raise RuntimeError(f"{step} response has no result field: {json.dumps(response, ensure_ascii=False)}")
    return response["result"]


def extract_thread_id(thread_start_result: Any) -> str:
    if not isinstance(thread_start_result, dict):
        raise RuntimeError("thread/start result is not an object")
    thread = thread_start_result.get("thread")
    if not isinstance(thread, dict):
        raise RuntimeError("thread/start result.thread is not an object")
    thread_id = thread.get("id")
    if not isinstance(thread_id, str) or not thread_id:
        raise RuntimeError("thread/start result.thread.id is missing")
    return thread_id


def contains_expected_text(message: Any) -> bool:
    if isinstance(message, str):
        return "app-server-python-ok" in message
    if isinstance(message, dict):
        return any(contains_expected_text(value) for value in message.values())
    if isinstance(message, list):
        return any(contains_expected_text(item) for item in message)
    return False


def recent_methods(messages: list[dict[str, Any]], limit: int = 12) -> list[str]:
    methods: list[str] = []
    for message in messages:
        method = message.get("method")
        if isinstance(method, str):
            methods.append(method)
        elif "id" in message:
            methods.append(f"response:{message.get('id')}")
    return methods[-limit:]


def build_paths() -> tuple[Path, Path, Path]:
    script_dir = Path(__file__).resolve().parent
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    events_path = script_dir / f"events-{timestamp}.jsonl"
    stderr_path = script_dir / f"app-server-stderr-{timestamp}.log"
    repo_root = script_dir.parent.parent
    return repo_root, events_path, stderr_path


def run(codex_command: str, timeout: float) -> int:
    repo_root, events_path, stderr_path = build_paths()
    command = [codex_command, "app-server", "--listen", "stdio://"]
    client: JsonlRpcClient | None = None
    failed_step = "launch"
    turn_start_accepted = False
    expected_text_seen = False

    print(f"events_file={events_path}")
    print(f"stderr_file={stderr_path}")
    print(f"command={' '.join(command)}")

    try:
        client = JsonlRpcClient(command, repo_root, events_path, stderr_path)

        failed_step = "initialize"
        client.request(
            "poc-1-initialize",
            "initialize",
            {
                "clientInfo": {
                    "name": "codex-job-app-server-python-poc",
                    "title": "codex-job app-server Python POC",
                    "version": "0.1.0",
                },
                "capabilities": {
                    "experimentalApi": True,
                },
            },
        )
        initialize_response = client.wait_for_response("poc-1-initialize", timeout=30)
        response_result(initialize_response, failed_step)
        print("initialize=ok")

        failed_step = "thread/start"
        client.request(
            "poc-2-thread-start",
            "thread/start",
            {
                "cwd": str(repo_root),
                "approvalPolicy": "never",
                "sandbox": "read-only",
                "sessionStartSource": "startup",
                "threadSource": "codex-job-app-server-poc",
                "ephemeral": True,
                "developerInstructions": "Do not modify files. Reply with only the requested text.",
            },
        )
        thread_start_response = client.wait_for_response("poc-2-thread-start", timeout=60)
        thread_id = extract_thread_id(response_result(thread_start_response, failed_step))
        print(f"thread/start=ok thread_id={thread_id}")

        failed_step = "turn/start"
        turn_start_event_index = client.message_count
        client.request(
            "poc-3-turn-start",
            "turn/start",
            {
                "threadId": thread_id,
                "cwd": str(repo_root),
                "approvalPolicy": "never",
                "sandboxPolicy": {
                    "type": "readOnly",
                    "networkAccess": False,
                },
                "clientUserMessageId": f"poc-user-message-{int(time.time())}",
                "input": [
                    {
                        "type": "text",
                        "text": USER_MESSAGE,
                    }
                ],
            },
        )
        turn_start_response = client.wait_for_response("poc-3-turn-start", timeout=60)
        response_result(turn_start_response, failed_step)
        turn_start_accepted = True
        print("turn/start=ok")

        failed_step = "turn/completed"
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            message_index, message = client.wait_for_match(
                lambda item: item.get("method") in {"agent/message_delta", "agent/messageDelta", "item/completed", "turn/completed"},
                timeout=max(0.1, deadline - time.monotonic()),
                start_index=turn_start_event_index,
            )
            turn_start_event_index = message_index + 1
            expected_text_seen = expected_text_seen or contains_expected_text(message)
            if message.get("method") == "turn/completed":
                expected_text_seen = expected_text_seen or contains_expected_text(message)
                print("turn/completed=ok")
                break
        else:
            raise TimeoutError("timed out waiting for turn/completed")

        print(f"expected_text_seen={str(expected_text_seen).lower()}")
        print(f"message_sent={str(turn_start_accepted).lower()}")
        return 0

    except FileNotFoundError as exc:
        print(f"RESULT=failed failed_step={failed_step}")
        print(f"detail=failed to launch app-server: {exc}")
        print("next_schema=not applicable; verify codex.cmd is on PATH or pass --codex-command")
        return 2
    except Exception as exc:
        print(f"RESULT=failed failed_step={failed_step}")
        print(f"detail={exc}")
        if client is not None:
            with client._condition:
                methods = recent_methods(client._messages)
                received_count = len(client._messages)
            print(f"received_json_lines={received_count}")
            print(f"recent_methods={json.dumps(methods, ensure_ascii=False)}")
            if client.invalid_stdout_lines:
                print(f"invalid_stdout_lines={len(client.invalid_stdout_lines)}")
        print(
            "schema_hints="
            "poc/app_server/schema/v1/InitializeParams.json,"
            "poc/app_server/schema/v2/ThreadStartParams.json,"
            "poc/app_server/schema/v2/TurnStartParams.json"
        )
        print(f"message_sent={str(turn_start_accepted).lower()}")
        return 1
    finally:
        if client is not None:
            client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Minimal Codex App Server stdio JSONL POC.")
    parser.add_argument("--codex-command", default="codex.cmd", help="Codex command to execute.")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS, help="Turn completion timeout in seconds.")
    args = parser.parse_args()
    return run(args.codex_command, args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
