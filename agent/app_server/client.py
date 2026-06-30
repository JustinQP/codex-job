from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable


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

    def trim_messages(self, max_messages: int) -> None:
        if max_messages < 1:
            return
        with self._condition:
            excess = len(self._messages) - max_messages
            if excess > 0:
                del self._messages[:excess]

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
        except BaseException as exc:
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
