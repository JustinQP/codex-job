from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from app_server_event_parser import load_events, write_summary
from app_server_stdio_client import JsonlRpcClient, extract_thread_id, response_result


DEFAULT_MESSAGE = "请只回复 app-server-parser-ok，不要修改文件。"
DEFAULT_TIMEOUT_SECONDS = 180.0


def create_run_dir(script_dir: Path) -> Path:
    runs_dir = script_dir / "runs"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = runs_dir / timestamp
    suffix = 1
    while run_dir.exists():
        run_dir = runs_dir / f"{timestamp}-{suffix}"
        suffix += 1
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def run_conversation(codex_command: str, message: str, timeout: float) -> tuple[int, dict[str, Any]]:
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent
    run_dir = create_run_dir(script_dir)
    events_path = run_dir / "events.jsonl"
    stderr_path = run_dir / "stderr.log"
    command = [codex_command, "app-server", "--listen", "stdio://"]
    client: JsonlRpcClient | None = None
    failed_step = "launch"
    run_error: str | None = None

    try:
        client = JsonlRpcClient(command, repo_root, events_path, stderr_path)

        failed_step = "initialize"
        client.request(
            "poc2-1-initialize",
            "initialize",
            {
                "clientInfo": {
                    "name": "codex-job-app-server-conversation-poc",
                    "title": "codex-job app-server conversation POC",
                    "version": "0.2.0",
                },
                "capabilities": {
                    "experimentalApi": True,
                },
            },
        )
        initialize_response = client.wait_for_response("poc2-1-initialize", timeout=30)
        response_result(initialize_response, failed_step)

        failed_step = "thread/start"
        client.request(
            "poc2-2-thread-start",
            "thread/start",
            {
                "cwd": str(repo_root),
                "approvalPolicy": "never",
                "sandbox": "read-only",
                "sessionStartSource": "startup",
                "threadSource": "codex-job-app-server-poc2",
                "ephemeral": True,
                "developerInstructions": "Do not modify files. Reply with only the requested text.",
            },
        )
        thread_start_response = client.wait_for_response("poc2-2-thread-start", timeout=60)
        thread_id = extract_thread_id(response_result(thread_start_response, failed_step))

        failed_step = "turn/start"
        turn_event_index = client.message_count
        client.request(
            "poc2-3-turn-start",
            "turn/start",
            {
                "threadId": thread_id,
                "cwd": str(repo_root),
                "approvalPolicy": "never",
                "sandboxPolicy": {
                    "type": "readOnly",
                    "networkAccess": False,
                },
                "clientUserMessageId": f"poc2-user-message-{int(time.time())}",
                "input": [
                    {
                        "type": "text",
                        "text": message,
                    }
                ],
            },
        )
        turn_start_response = client.wait_for_response("poc2-3-turn-start", timeout=60)
        response_result(turn_start_response, failed_step)

        failed_step = "turn/completed"
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            message_index, event = client.wait_for_match(
                _is_turn_progress_event,
                timeout=max(0.1, deadline - time.monotonic()),
                start_index=turn_event_index,
            )
            turn_event_index = message_index + 1
            if _event_name(event) == "turn/completed":
                break
        else:
            raise TimeoutError("timed out waiting for turn/completed")

        return_code = 0
    except Exception as exc:
        run_error = f"{failed_step}: {exc}"
        return_code = 1
    finally:
        if client is not None:
            client.close()

    events = load_events(events_path)
    summary = write_summary(run_dir, events)
    summary["run_dir"] = str(run_dir)
    summary["events_path"] = str(events_path)
    summary["stderr_path"] = str(stderr_path)
    summary["run_error"] = run_error
    summary["failed_step"] = failed_step if run_error else None
    summary_path = run_dir / "run-summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
        errors="replace",
    )

    _print_result(run_dir, summary)
    return return_code, summary


def _is_turn_progress_event(event: dict[str, Any]) -> bool:
    name = _event_name(event)
    return (
        name == "turn/completed"
        or "agentmessage" in _normalized(name)
        or "assistant" in _normalized(name)
        or name in {"item/completed", "item/started"}
    )


def _event_name(event: dict[str, Any]) -> str:
    for key in ("method", "type", "event"):
        value = event.get(key)
        if isinstance(value, str):
            return value
    if "id" in event and ("result" in event or "error" in event):
        return "response"
    return "unknown"


def _normalized(value: Any) -> str:
    return str(value or "").replace("-", "_").replace("/", "_").lower()


def _print_result(run_dir: Path, summary: dict[str, Any]) -> None:
    assistant_path = run_dir / "assistant-final.md"
    assistant_preview = assistant_path.read_text(encoding="utf-8", errors="replace")[:500]

    print(f"run_dir={run_dir}")
    print(f"total_events={summary['total_events']}")
    print("event_type_counts=" + json.dumps(summary["event_type_counts"], ensure_ascii=False, sort_keys=True))
    print("assistant_final_preview=")
    print(assistant_preview)
    print(f"has_errors={str(summary['has_errors']).lower()}")
    if summary.get("run_error"):
        print(f"run_error={summary['run_error']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Codex App Server conversation POC with event parsing.")
    parser.add_argument("--message", default=DEFAULT_MESSAGE, help="User message to send to app-server.")
    parser.add_argument("--codex-command", default="codex.cmd", help="Codex command to execute.")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS, help="Turn completion timeout in seconds.")
    args = parser.parse_args()

    return_code, _summary = run_conversation(args.codex_command, args.message, args.timeout)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
