from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from app_server_event_parser import detect_errors, extract_assistant_text, write_summary
from app_server_stdio_client import JsonlRpcClient, extract_thread_id, response_result


EXPECTED_TOKEN = "justin-plus-session-test"
TURN_1_MESSAGE = f"请记住这个词：{EXPECTED_TOKEN}。只回复“已记住”。"
TURN_2_MESSAGE = "刚才让你记住的词是什么？只回复这个词。"
DEFAULT_TIMEOUT_SECONDS = 180.0


def main() -> int:
    return_code, _result = run_thread_reuse_poc()
    return return_code


def run_thread_reuse_poc(
    codex_command: str = "codex.cmd",
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[int, dict[str, Any]]:
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent
    run_dir = _create_run_dir(script_dir)
    turn_1_dir = run_dir / "turn-1"
    turn_2_dir = run_dir / "turn-2"
    turn_1_dir.mkdir(parents=True, exist_ok=True)
    turn_2_dir.mkdir(parents=True, exist_ok=True)

    raw_events_path = run_dir / "_all-events.jsonl"
    stderr_path = run_dir / "stderr.log"
    command = [codex_command, "app-server", "--listen", "stdio://"]
    client: JsonlRpcClient | None = None
    failed_step = "launch"
    run_errors: list[str] = []
    thread_id = ""
    turn_1_id = ""
    turn_2_id = ""

    try:
        client = JsonlRpcClient(command, repo_root, raw_events_path, stderr_path)

        failed_step = "initialize"
        client.request(
            "poc3-1-initialize",
            "initialize",
            {
                "clientInfo": {
                    "name": "codex-job-app-server-thread-reuse-poc",
                    "title": "codex-job app-server thread reuse POC",
                    "version": "0.3.0",
                },
                "capabilities": {
                    "experimentalApi": True,
                },
            },
        )
        initialize_response = client.wait_for_response("poc3-1-initialize", timeout=30)
        initialize_result = response_result(initialize_response, failed_step)

        failed_step = "thread/start"
        client.request(
            "poc3-2-thread-start",
            "thread/start",
            {
                "cwd": str(repo_root),
                "approvalPolicy": "never",
                "sandbox": "read-only",
                "sessionStartSource": "startup",
                "threadSource": "codex-job-app-server-poc3",
                "ephemeral": True,
                "developerInstructions": "不要修改文件，只回复要求文本。",
            },
        )
        thread_start_response = client.wait_for_response("poc3-2-thread-start", timeout=60)
        thread_start_result = response_result(thread_start_response, failed_step)
        thread_id = extract_thread_id(thread_start_result)

        failed_step = "turn-1"
        turn_1_id = _run_turn(
            client=client,
            request_id="poc3-3-turn-1-start",
            thread_id=thread_id,
            repo_root=repo_root,
            message=TURN_1_MESSAGE,
            timeout=timeout,
        )

        failed_step = "turn-2"
        turn_2_id = _run_turn(
            client=client,
            request_id="poc3-4-turn-2-start",
            thread_id=thread_id,
            repo_root=repo_root,
            message=TURN_2_MESSAGE,
            timeout=timeout,
        )

        thread_state = {
            "command": command,
            "cwd": str(repo_root),
            "thread_id": thread_id,
            "turn_1_id": turn_1_id,
            "turn_2_id": turn_2_id,
            "initialize_result": initialize_result,
            "thread_start_result": thread_start_result,
        }
    except Exception as exc:
        run_errors.append(f"{failed_step}: {exc}")
        thread_state = {
            "command": command,
            "cwd": str(repo_root),
            "thread_id": thread_id,
            "turn_1_id": turn_1_id,
            "turn_2_id": turn_2_id,
            "failed_step": failed_step,
        }
    finally:
        if client is not None:
            client.close()

    all_events = _client_messages(client)
    turn_1_events = _events_for_turn(all_events, turn_1_id, "poc3-3-turn-1-start")
    turn_2_events = _events_for_turn(all_events, turn_2_id, "poc3-4-turn-2-start")

    _write_events_jsonl(turn_1_dir / "events.jsonl", turn_1_events)
    _write_events_jsonl(turn_2_dir / "events.jsonl", turn_2_events)
    _delete_if_exists(raw_events_path)
    (run_dir / "thread-state.json").write_text(
        json.dumps(thread_state, ensure_ascii=False, indent=2),
        encoding="utf-8",
        errors="replace",
    )

    turn_1_summary = write_summary(turn_1_dir, turn_1_events)
    turn_2_summary = write_summary(turn_2_dir, turn_2_events)
    turn_1_final = extract_assistant_text(turn_1_events)
    turn_2_final = extract_assistant_text(turn_2_events)
    errors = run_errors + _format_summary_errors("turn-1", turn_1_summary) + _format_summary_errors("turn-2", turn_2_summary)
    context_retained = _is_turn_1_ack(turn_1_final) and EXPECTED_TOKEN in turn_2_final.lower()

    result = {
        "thread_id": thread_id,
        "turn_1_id": turn_1_id,
        "turn_2_id": turn_2_id,
        "turn_1_final": turn_1_final,
        "turn_2_final": turn_2_final,
        "context_retained": context_retained,
        "expected_token": EXPECTED_TOKEN,
        "turn_1_acknowledged": _is_turn_1_ack(turn_1_final),
        "turn_2_contains_expected_token": EXPECTED_TOKEN in turn_2_final.lower(),
        "errors": errors,
        "run_dir": str(run_dir),
        "stderr_path": str(stderr_path),
        "turn_1_summary": turn_1_summary,
        "turn_2_summary": turn_2_summary,
    }
    (run_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
        errors="replace",
    )

    _print_result(run_dir, result)
    return (0 if context_retained and not errors else 1), result


def _run_turn(
    client: JsonlRpcClient,
    request_id: str,
    thread_id: str,
    repo_root: Path,
    message: str,
    timeout: float,
) -> str:
    turn_start_event_index = client.message_count
    client.request(
        request_id,
        "turn/start",
        {
            "threadId": thread_id,
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
    turn_start_response = client.wait_for_response(request_id, timeout=60)
    turn_id = _extract_turn_id(response_result(turn_start_response, request_id))

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        message_index, event = client.wait_for_match(
            lambda item: _is_turn_completed(item, turn_id),
            timeout=max(0.1, deadline - time.monotonic()),
            start_index=turn_start_event_index,
        )
        turn_start_event_index = message_index + 1
        if _is_turn_completed(event, turn_id):
            return turn_id

    raise TimeoutError(f"timed out waiting for turn/completed: {turn_id}")


def _create_run_dir(script_dir: Path) -> Path:
    runs_dir = script_dir / "runs"
    timestamp = datetime.now().strftime("thread-reuse-%Y%m%d-%H%M%S")
    run_dir = runs_dir / timestamp
    suffix = 1
    while run_dir.exists():
        run_dir = runs_dir / f"{timestamp}-{suffix}"
        suffix += 1
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


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


def _is_turn_completed(event: dict[str, Any], turn_id: str) -> bool:
    return _event_name(event) == "turn/completed" and _event_turn_id(event) == turn_id


def _events_for_turn(events: list[dict[str, Any]], turn_id: str, request_id: str) -> list[dict[str, Any]]:
    if not turn_id:
        return [event for event in events if event.get("id") == request_id]
    return [
        event
        for event in events
        if event.get("id") == request_id or _event_turn_id(event) == turn_id
    ]


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


def _client_messages(client: JsonlRpcClient | None) -> list[dict[str, Any]]:
    if client is None:
        return []
    with client._condition:
        return list(client._messages)


def _write_events_jsonl(path: Path, events: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", errors="replace") as file:
        for event in events:
            file.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")


def _delete_if_exists(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _is_turn_1_ack(text: str) -> bool:
    normalized = text.strip().lower()
    return (
        "已记住" in normalized
        or "记住了" in normalized
        or "我记住" in normalized
        or normalized in {"好的", "好", "ok", "okay"}
    )


def _format_summary_errors(label: str, summary: dict[str, Any]) -> list[str]:
    formatted_errors: list[str] = []
    for error in summary.get("errors", []):
        formatted_errors.append(f"{label}: {json.dumps(error, ensure_ascii=False)}")
    return formatted_errors


def _print_result(run_dir: Path, result: dict[str, Any]) -> None:
    print(f"run_dir={run_dir}")
    print(f"thread_id={result['thread_id']}")
    print(f"context_retained={str(result['context_retained']).lower()}")
    print("turn_1_final_preview=")
    print(result["turn_1_final"][:500])
    print("turn_2_final_preview=")
    print(result["turn_2_final"][:500])
    print(f"errors={json.dumps(result['errors'], ensure_ascii=False)}")


if __name__ == "__main__":
    raise SystemExit(main())
