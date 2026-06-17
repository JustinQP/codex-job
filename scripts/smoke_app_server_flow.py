from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


EXPECTED_TOKEN = "app-thread-smoke-ok"


class SmokeFlowError(RuntimeError):
    def __init__(
        self,
        step: str,
        message: str,
        *,
        status_code: int | None = None,
        body: str | None = None,
        cleanup_status: str = "SKIPPED",
        cleanup_error: str | None = None,
        response: Any = None,
    ) -> None:
        super().__init__(message)
        self.step = step
        self.status_code = status_code
        self.body = body
        self.cleanup_status = cleanup_status
        self.cleanup_error = cleanup_error
        self.response = response


def request_json(
    base_url: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    token: str | None = None,
    timeout: int = 120,
    step: str | None = None,
) -> Any:
    url = f"{base_url.rstrip('/')}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if token:
        headers["X-API-Token"] = token
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SmokeFlowError(
            step or path,
            "HTTP request failed",
            status_code=exc.code,
            body=body,
            response=_parse_json_or_none(body),
        ) from exc
    except urllib.error.URLError as exc:
        raise SmokeFlowError(step or path, f"Request failed: {exc.reason}") from exc

    if not body:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise SmokeFlowError(step or path, "Response is not valid JSON", body=body) from exc


def run_smoke_flow(args: argparse.Namespace) -> dict[str, Any]:
    base_url = args.base_url
    token = args.token
    created_app_thread_id: int | None = None
    cleanup_status = "SKIPPED"
    cleanup_error = None
    async_conflict_checked = False
    async_conflict_passed = False

    try:
        backend_health = request_json(base_url, "GET", "/health", token=token, step="backend_health")
        bridge_health = request_json(
            base_url,
            "GET",
            "/app-server-bridge/health",
            token=token,
            step="bridge_health",
        )

        project_id = args.project_id
        if project_id is None:
            project = request_json(
                base_url,
                "POST",
                "/projects",
                {
                    "name": args.project_name,
                    "path": str(Path(args.project_path).expanduser().resolve()),
                    "enabled": True,
                },
                token=token,
                step="create_project",
            )
            project_id = int(project["id"])

        app_thread = request_json(
            base_url,
            "POST",
            "/app-threads",
            {
                "project_id": project_id,
                "title": args.title,
            },
            token=token,
            step="create_app_thread",
        )
        created_app_thread_id = int(app_thread["id"])

        if args.async_turn:
            turn, poll_count, conflict_checked, conflict_passed = _run_async_turn(
                base_url,
                token,
                created_app_thread_id,
                args,
            )
            async_conflict_checked = conflict_checked
            async_conflict_passed = conflict_passed
            turn_id = turn.get("id")
            final_turn_status = turn.get("status")
            if final_turn_status == "FAILED":
                raise SmokeFlowError(
                    "poll_app_turn",
                    str(turn.get("error_message") or "async app turn failed"),
                )
        else:
            turn = request_json(
                base_url,
                "POST",
                f"/app-threads/{created_app_thread_id}/turns",
                {"message": args.message},
                token=token,
                timeout=args.turn_timeout_seconds,
                step="send_app_turn",
            )
            turn_id = turn.get("id")
            poll_count = 0
            final_turn_status = turn.get("status")

        final = request_json(
            base_url,
            "GET",
            f"/app-threads/{created_app_thread_id}/final",
            token=token,
            step="get_app_thread_final",
        )
        turns = request_json(
            base_url,
            "GET",
            f"/app-threads/{created_app_thread_id}/turns",
            token=token,
            step="list_app_turns",
        )
        events = request_json(
            base_url,
            "GET",
            f"/app-threads/{created_app_thread_id}/events",
            token=token,
            step="get_app_thread_events",
        )
        closed = request_json(
            base_url,
            "DELETE",
            f"/app-threads/{created_app_thread_id}",
            token=token,
            step="close_app_thread",
        )
        cleanup_status = _cleanup_status(closed)
    except SmokeFlowError as exc:
        cleanup_status, cleanup_error = cleanup_app_thread(base_url, token, created_app_thread_id)
        exc.cleanup_status = cleanup_status
        exc.cleanup_error = cleanup_error
        raise

    assistant_final = final.get("assistant_final") if isinstance(final, dict) else None
    passed = EXPECTED_TOKEN in str(assistant_final or "")
    return {
        "backend_health": backend_health,
        "bridge_health": bridge_health,
        "project_id": project_id,
        "app_thread_id": created_app_thread_id,
        "created_app_thread_id": created_app_thread_id,
        "turn_id": turn_id,
        "assistant_final": assistant_final,
        "turn_count": len(turns) if isinstance(turns, list) else None,
        "events_summary": events.get("event_summary") if isinstance(events, dict) else events,
        "closed_status": closed.get("status") if isinstance(closed, dict) else None,
        "cleanup_status": cleanup_status,
        "cleanup_error": cleanup_error,
        "async_turn": bool(args.async_turn),
        "poll_count": poll_count,
        "final_turn_status": final_turn_status,
        "async_conflict_checked": async_conflict_checked,
        "async_conflict_passed": async_conflict_passed,
        "pass": passed,
    }


def _run_async_turn(
    base_url: str,
    token: str | None,
    app_thread_id: int,
    args: argparse.Namespace,
) -> tuple[dict[str, Any], int, bool, bool]:
    turn = request_json(
        base_url,
        "POST",
        f"/app-threads/{app_thread_id}/turns/async",
        {"message": args.message},
        token=token,
        step="create_async_app_turn",
    )
    turn_id = turn.get("id")
    if not isinstance(turn_id, int):
        raise SmokeFlowError("create_async_app_turn", "async turn response missing id")

    conflict_checked = False
    conflict_passed = False
    if args.check_async_conflict:
        conflict_checked = True
        try:
            request_json(
                base_url,
                "POST",
                f"/app-threads/{app_thread_id}/turns/async",
                {"message": args.message},
                token=token,
                step="check_async_conflict",
            )
        except SmokeFlowError as exc:
            if exc.status_code == 409:
                conflict_passed = True
            else:
                raise
        else:
            raise SmokeFlowError("check_async_conflict", "second async turn did not return 409")

    poll_count = 0
    deadline = time.monotonic() + args.poll_timeout_seconds
    while True:
        if time.monotonic() > deadline:
            raise SmokeFlowError("poll_app_turn", "async app turn polling timed out")
        if poll_count > 0 or turn.get("status") not in {"SUCCESS", "FAILED"}:
            if poll_count > 0:
                time.sleep(args.poll_interval_seconds)
            turn = request_json(
                base_url,
                "GET",
                f"/app-turns/{turn_id}",
                token=token,
                step="poll_app_turn",
            )
        poll_count += 1
        if turn.get("status") in {"SUCCESS", "FAILED"}:
            return turn, poll_count, conflict_checked, conflict_passed


def cleanup_app_thread(base_url: str, token: str | None, app_thread_id: int | None) -> tuple[str, str | None]:
    if app_thread_id is None:
        return "SKIPPED", None
    try:
        closed = request_json(
            base_url,
            "DELETE",
            f"/app-threads/{app_thread_id}",
            token=token,
            step="cleanup_app_thread",
        )
    except SmokeFlowError as exc:
        return "FAILED", f"{exc.step}: {exc}"
    return _cleanup_status(closed), None


def _cleanup_status(payload: Any) -> str:
    if isinstance(payload, dict):
        status = payload.get("status")
        if isinstance(status, str) and status:
            return status
    return "CLOSED"


def _parse_json_or_none(raw_body: str) -> Any:
    try:
        return json.loads(raw_body)
    except json.JSONDecodeError:
        return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test the main App Server thread API flow")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--token", default=os.environ.get("API_TOKEN"))
    parser.add_argument("--project-id", type=int)
    parser.add_argument("--project-name", default="smoke-app-server-project")
    parser.add_argument("--project-path", default=str(Path.cwd()))
    parser.add_argument("--title", default="Smoke App Thread")
    parser.add_argument("--message", default="请只回复 app-thread-smoke-ok，不要修改文件。")
    parser.add_argument("--turn-timeout-seconds", type=int, default=300)
    parser.add_argument("--async-turn", action="store_true")
    parser.add_argument("--poll-interval-seconds", type=float, default=2)
    parser.add_argument("--poll-timeout-seconds", type=float, default=300)
    parser.add_argument("--check-async-conflict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = run_smoke_flow(args)
    except SmokeFlowError as exc:
        print(
            json.dumps(
                {
                    "pass": False,
                    "failed_step": exc.step,
                    "status_code": exc.status_code,
                    "body": exc.body,
                    "error": str(exc),
                    "cleanup_status": exc.cleanup_status,
                    "cleanup_error": exc.cleanup_error,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
