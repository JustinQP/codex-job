from __future__ import annotations

from typing import Any

from scripts import smoke_app_server_flow


def test_run_smoke_flow_success(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_request_json(
        base_url: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        del base_url, payload, kwargs
        calls.append((method, path))
        if path == "/health":
            return {"status": "ok"}
        if path == "/app-server-bridge/health":
            return {"status": "ok", "mode": "poc"}
        if path == "/projects":
            return {"id": 10}
        if path == "/app-threads":
            return {"id": 20, "status": "ACTIVE"}
        if path == "/app-threads/20/turns" and method == "POST":
            return {"id": 30}
        if path == "/app-threads/20/final":
            return {"assistant_final": "app-thread-smoke-ok"}
        if path == "/app-threads/20/turns" and method == "GET":
            return [{"id": 30}]
        if path == "/app-threads/20/events":
            return {"event_summary": {"total_events": 2}}
        if path == "/app-threads/20" and method == "DELETE":
            return {"status": "CLOSED"}
        raise AssertionError(f"unexpected request: {method} {path}")

    monkeypatch.setattr(smoke_app_server_flow, "request_json", fake_request_json)
    args = smoke_app_server_flow.parse_args(["--base-url", "http://backend.local"])

    summary = smoke_app_server_flow.run_smoke_flow(args)

    assert summary["pass"] is True
    assert summary["project_id"] == 10
    assert summary["app_thread_id"] == 20
    assert summary["turn_id"] == 30
    assert summary["closed_status"] == "CLOSED"
    assert summary["cleanup_status"] == "CLOSED"
    assert summary["cleanup_error"] is None
    assert ("GET", "/app-server-bridge/health") in calls


def test_run_smoke_flow_returns_false_when_final_missing_expected_token(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_request_json(
        base_url: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        del base_url, payload, kwargs
        calls.append((method, path))
        if path == "/health":
            return {"status": "ok"}
        if path == "/app-server-bridge/health":
            return {"status": "ok"}
        if path == "/projects":
            return {"id": 10}
        if path == "/app-threads":
            return {"id": 20}
        if path == "/app-threads/20/turns" and method == "POST":
            return {"id": 30}
        if path == "/app-threads/20/final":
            return {"assistant_final": "different response"}
        if path == "/app-threads/20/turns" and method == "GET":
            return [{"id": 30}]
        if path == "/app-threads/20/events":
            return {"event_summary": {}}
        if path == "/app-threads/20" and method == "DELETE":
            return {"status": "CLOSED"}
        raise AssertionError(f"unexpected request: {method} {path}")

    monkeypatch.setattr(smoke_app_server_flow, "request_json", fake_request_json)
    args = smoke_app_server_flow.parse_args([])

    summary = smoke_app_server_flow.run_smoke_flow(args)

    assert summary["pass"] is False
    assert summary["assistant_final"] == "different response"
    assert summary["cleanup_status"] == "CLOSED"
    assert ("DELETE", "/app-threads/20") in calls


def test_main_returns_1_when_final_missing_expected_token(monkeypatch, capsys) -> None:
    def fake_run_smoke_flow(args) -> dict[str, Any]:
        del args
        return {
            "assistant_final": "different response",
            "cleanup_status": "CLOSED",
            "pass": False,
        }

    monkeypatch.setattr(smoke_app_server_flow, "run_smoke_flow", fake_run_smoke_flow)

    exit_code = smoke_app_server_flow.main([])

    assert exit_code == 1
    assert '"pass": false' in capsys.readouterr().out


def test_run_smoke_flow_cleans_up_after_send_turn_failure(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_request_json(
        base_url: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        del base_url, payload, kwargs
        calls.append((method, path))
        if path == "/health":
            return {"status": "ok"}
        if path == "/app-server-bridge/health":
            return {"status": "ok"}
        if path == "/projects":
            return {"id": 10}
        if path == "/app-threads":
            return {"id": 20}
        if path == "/app-threads/20/turns" and method == "POST":
            raise smoke_app_server_flow.SmokeFlowError(
                "send_app_turn",
                "HTTP request failed",
                status_code=504,
                body='{"detail":"timeout"}',
            )
        if path == "/app-threads/20" and method == "DELETE":
            return {"status": "CLOSED"}
        raise AssertionError(f"unexpected request: {method} {path}")

    monkeypatch.setattr(smoke_app_server_flow, "request_json", fake_request_json)
    args = smoke_app_server_flow.parse_args([])

    try:
        smoke_app_server_flow.run_smoke_flow(args)
    except smoke_app_server_flow.SmokeFlowError as exc:
        assert exc.step == "send_app_turn"
        assert exc.status_code == 504
        assert exc.cleanup_status == "CLOSED"
        assert exc.cleanup_error is None
    else:
        raise AssertionError("expected SmokeFlowError")

    assert ("DELETE", "/app-threads/20") in calls


def test_run_smoke_flow_async_success(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_request_json(
        base_url: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        del base_url, payload, kwargs
        calls.append((method, path))
        if path == "/health":
            return {"status": "ok"}
        if path == "/app-server-bridge/health":
            return {"status": "ok"}
        if path == "/projects":
            return {"id": 10}
        if path == "/app-threads":
            return {"id": 20}
        if path == "/app-threads/20/turns/async" and method == "POST":
            return {"id": 30, "status": "PENDING"}
        if path == "/app-turns/30":
            return {"id": 30, "status": "SUCCESS"}
        if path == "/app-threads/20/final":
            return {"assistant_final": "app-thread-smoke-ok"}
        if path == "/app-threads/20/turns" and method == "GET":
            return [{"id": 30}]
        if path == "/app-threads/20/events":
            return {"event_summary": {"total_events": 2}}
        if path == "/app-threads/20" and method == "DELETE":
            return {"status": "CLOSED"}
        raise AssertionError(f"unexpected request: {method} {path}")

    monkeypatch.setattr(smoke_app_server_flow, "request_json", fake_request_json)
    args = smoke_app_server_flow.parse_args(["--async-turn", "--poll-interval-seconds", "0"])

    summary = smoke_app_server_flow.run_smoke_flow(args)

    assert summary["pass"] is True
    assert summary["async_turn"] is True
    assert summary["poll_count"] == 1
    assert summary["final_turn_status"] == "SUCCESS"
    assert ("DELETE", "/app-threads/20") in calls


def test_run_smoke_flow_async_failed_turn_cleans_up(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_request_json(
        base_url: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        del base_url, payload, kwargs
        calls.append((method, path))
        if path == "/health":
            return {"status": "ok"}
        if path == "/app-server-bridge/health":
            return {"status": "ok"}
        if path == "/projects":
            return {"id": 10}
        if path == "/app-threads":
            return {"id": 20}
        if path == "/app-threads/20/turns/async":
            return {"id": 30, "status": "PENDING"}
        if path == "/app-turns/30":
            return {"id": 30, "status": "FAILED", "error_message": "timeout"}
        if path == "/app-threads/20" and method == "DELETE":
            return {"status": "CLOSED"}
        raise AssertionError(f"unexpected request: {method} {path}")

    monkeypatch.setattr(smoke_app_server_flow, "request_json", fake_request_json)
    args = smoke_app_server_flow.parse_args(["--async-turn", "--poll-interval-seconds", "0"])

    try:
        smoke_app_server_flow.run_smoke_flow(args)
    except smoke_app_server_flow.SmokeFlowError as exc:
        assert exc.step == "poll_app_turn"
        assert "timeout" in str(exc)
        assert exc.cleanup_status == "CLOSED"
    else:
        raise AssertionError("expected SmokeFlowError")

    assert ("DELETE", "/app-threads/20") in calls


def test_run_smoke_flow_async_poll_timeout_cleans_up(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_request_json(
        base_url: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        del base_url, payload, kwargs
        calls.append((method, path))
        if path == "/health":
            return {"status": "ok"}
        if path == "/app-server-bridge/health":
            return {"status": "ok"}
        if path == "/projects":
            return {"id": 10}
        if path == "/app-threads":
            return {"id": 20}
        if path == "/app-threads/20/turns/async":
            return {"id": 30, "status": "PENDING"}
        if path == "/app-turns/30":
            return {"id": 30, "status": "RUNNING"}
        if path == "/app-threads/20" and method == "DELETE":
            return {"status": "CLOSED"}
        raise AssertionError(f"unexpected request: {method} {path}")

    monkeypatch.setattr(smoke_app_server_flow, "request_json", fake_request_json)
    args = smoke_app_server_flow.parse_args(
        ["--async-turn", "--poll-interval-seconds", "0", "--poll-timeout-seconds", "0"]
    )

    try:
        smoke_app_server_flow.run_smoke_flow(args)
    except smoke_app_server_flow.SmokeFlowError as exc:
        assert exc.step == "poll_app_turn"
        assert "timed out" in str(exc)
        assert exc.cleanup_status == "CLOSED"
    else:
        raise AssertionError("expected SmokeFlowError")

    assert ("DELETE", "/app-threads/20") in calls


def test_run_smoke_flow_preserves_original_error_when_cleanup_fails(monkeypatch) -> None:
    def fake_request_json(
        base_url: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        del base_url, payload, kwargs
        if path == "/health":
            return {"status": "ok"}
        if path == "/app-server-bridge/health":
            return {"status": "ok"}
        if path == "/projects":
            return {"id": 10}
        if path == "/app-threads":
            return {"id": 20}
        if path == "/app-threads/20/turns" and method == "POST":
            raise smoke_app_server_flow.SmokeFlowError(
                "send_app_turn",
                "HTTP request failed",
                status_code=504,
            )
        if path == "/app-threads/20" and method == "DELETE":
            raise smoke_app_server_flow.SmokeFlowError(
                "cleanup_app_thread",
                "HTTP request failed",
                status_code=503,
            )
        raise AssertionError(f"unexpected request: {method} {path}")

    monkeypatch.setattr(smoke_app_server_flow, "request_json", fake_request_json)
    args = smoke_app_server_flow.parse_args([])

    try:
        smoke_app_server_flow.run_smoke_flow(args)
    except smoke_app_server_flow.SmokeFlowError as exc:
        assert exc.step == "send_app_turn"
        assert exc.cleanup_status == "FAILED"
        assert "cleanup_app_thread" in str(exc.cleanup_error)
    else:
        raise AssertionError("expected SmokeFlowError")


def test_main_returns_1_on_http_error(monkeypatch, capsys) -> None:
    def fake_run_smoke_flow(args) -> dict[str, Any]:
        del args
        raise smoke_app_server_flow.SmokeFlowError(
            "bridge_health",
            "HTTP request failed",
            status_code=503,
            body='{"detail":"bridge down"}',
        )

    monkeypatch.setattr(smoke_app_server_flow, "run_smoke_flow", fake_run_smoke_flow)

    exit_code = smoke_app_server_flow.main([])

    assert exit_code == 1
    output = capsys.readouterr().out
    assert '"failed_step": "bridge_health"' in output
    assert '"status_code": 503' in output
    assert '"cleanup_status": "SKIPPED"' in output
