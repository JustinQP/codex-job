from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_BRIDGE_URL = "http://127.0.0.1:8766"
DEFAULT_TIMEOUT_SECONDS = 300.0


@dataclass
class AppServerBridgeError(Exception):
    status_code: int | None
    code: str
    message: str
    step: str = "request"

    def __str__(self) -> str:
        status = self.status_code if self.status_code is not None else "n/a"
        return f"{self.code} at {self.step} ({status}): {self.message}"


class AppServerBridgeClient:
    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.base_url = _clean_base_url(base_url or os.environ.get("APP_SERVER_BRIDGE_URL") or DEFAULT_BRIDGE_URL)
        self.token = token if token is not None else os.environ.get("APP_SERVER_BRIDGE_TOKEN")
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else _read_timeout_seconds()

    def get_health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def create_thread(self, title: str) -> dict[str, Any]:
        return self._request("POST", "/threads", {"title": title})

    def list_threads(self) -> dict[str, Any]:
        return self._request("GET", "/threads")

    def get_thread(self, bridge_thread_id: str) -> dict[str, Any]:
        return self._request("GET", f"/threads/{_quote_path(bridge_thread_id)}")

    def rename_thread(self, bridge_thread_id: str, title: str) -> dict[str, Any]:
        return self._request("PATCH", f"/threads/{_quote_path(bridge_thread_id)}", {"title": title})

    def delete_thread(self, bridge_thread_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"/threads/{_quote_path(bridge_thread_id)}")

    def send_turn(self, bridge_thread_id: str, message: str) -> dict[str, Any]:
        return self._request("POST", f"/threads/{_quote_path(bridge_thread_id)}/turns", {"message": message})

    def get_final(self, bridge_thread_id: str) -> dict[str, Any]:
        return self._request("GET", f"/threads/{_quote_path(bridge_thread_id)}/final")

    def get_events(self, bridge_thread_id: str) -> dict[str, Any]:
        return self._request("GET", f"/threads/{_quote_path(bridge_thread_id)}/events")

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = None
        headers = {"Accept": "application/json"}
        if self.token:
            headers["X-Bridge-Token"] = self.token
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"

        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw_body = response.read().decode("utf-8", errors="replace")
                return _parse_json(raw_body, response.status, "parse_json")
        except urllib.error.HTTPError as exc:
            raw_body = exc.read().decode("utf-8", errors="replace")
            raise _http_error(exc.code, raw_body) from exc
        except TimeoutError as exc:
            raise AppServerBridgeError(None, "timeout", "App Server Bridge request timed out.", "request") from exc
        except socket.timeout as exc:
            raise AppServerBridgeError(None, "timeout", "App Server Bridge request timed out.", "request") from exc
        except urllib.error.URLError as exc:
            message = str(exc.reason) if getattr(exc, "reason", None) else str(exc)
            raise AppServerBridgeError(None, "network_error", message, "request") from exc
        except OSError as exc:
            raise AppServerBridgeError(None, "network_error", str(exc), "request") from exc


def get_default_client() -> AppServerBridgeClient:
    return AppServerBridgeClient()


def _http_error(status_code: int, raw_body: str) -> AppServerBridgeError:
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return AppServerBridgeError(status_code, "http_error", raw_body or f"HTTP {status_code}", "http")
    if not isinstance(payload, dict):
        return AppServerBridgeError(status_code, "http_error", f"HTTP {status_code}", "http")
    error = payload.get("error")
    code = "http_error"
    message = payload.get("detail") or f"HTTP {status_code}"
    if isinstance(error, dict):
        code = str(error.get("code") or code)
        message = str(error.get("message") or message)
    return AppServerBridgeError(status_code, code, message, str(payload.get("step") or "http"))


def _parse_json(raw_body: str, status_code: int | None, step: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_body or "{}")
    except json.JSONDecodeError as exc:
        raise AppServerBridgeError(status_code, "invalid_json", str(exc), step) from exc
    if not isinstance(payload, dict):
        raise AppServerBridgeError(status_code, "invalid_json", "Bridge response JSON must be an object.", step)
    return payload


def _read_timeout_seconds() -> float:
    raw_value = os.environ.get("APP_SERVER_BRIDGE_TIMEOUT_SECONDS")
    if not raw_value:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        return max(0.1, float(raw_value))
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS


def _clean_base_url(value: str) -> str:
    return value.strip().rstrip("/")


def _quote_path(value: str) -> str:
    return urllib.parse.quote(value, safe="")
