from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backend.schemas import (
    AgentCommandClaimRequest,
    AgentCommandCompleteRequest,
    AgentCommandLeaseRequest,
    DeviceHeartbeat,
    DeviceRegister,
    WorkspaceSyncRequest,
)


class AgentApiError(RuntimeError):
    pass


class AgentApiClient:
    def __init__(self, *, base_url: str, agent_token: str | None, timeout: float = 30.0):
        if not agent_token:
            raise AgentApiError("AGENT_TOKEN is required for agent API calls")
        self.base_url = base_url.rstrip("/")
        self.agent_token = agent_token
        self.timeout = timeout

    def register(self, payload: DeviceRegister) -> dict[str, Any]:
        return self._json_request("/agent/register", payload.model_dump())

    def heartbeat(self, payload: DeviceHeartbeat) -> dict[str, Any]:
        return self._json_request("/agent/heartbeat", payload.model_dump(exclude_none=True))

    def sync_workspaces(self, payload: WorkspaceSyncRequest) -> dict[str, Any]:
        return self._json_request("/agent/workspaces/sync", payload.model_dump(exclude_none=True))

    def claim_command(self, payload: AgentCommandClaimRequest) -> dict[str, Any] | None:
        return self._json_request_or_none(
            "/agent/commands/claim",
            payload.model_dump(exclude_none=True),
        )

    def ack_command(self, command_id: str, payload: AgentCommandLeaseRequest) -> dict[str, Any]:
        return self._json_request(
            f"/agent/commands/{command_id}/ack",
            payload.model_dump(exclude_none=True),
        )

    def renew_command(self, command_id: str, payload: AgentCommandLeaseRequest) -> dict[str, Any]:
        return self._json_request(
            f"/agent/commands/{command_id}/renew",
            payload.model_dump(exclude_none=True),
        )

    def complete_command(self, command_id: str, payload: AgentCommandCompleteRequest) -> dict[str, Any]:
        return self._json_request(
            f"/agent/commands/{command_id}/complete",
            payload.model_dump(exclude_none=True),
        )

    def _json_request(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._json_request_or_none(path, payload)
        if not isinstance(data, dict):
            raise AgentApiError(f"agent API {path} returned non-object JSON")
        return data

    def _json_request_or_none(self, path: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Agent-Token": self.agent_token,
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise AgentApiError(f"agent API {path} failed: HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise AgentApiError(f"agent API {path} failed: {exc.reason}") from exc

        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise AgentApiError(f"agent API {path} returned invalid JSON") from exc
        if data is None:
            return None
        if not isinstance(data, dict):
            raise AgentApiError(f"agent API {path} returned non-object JSON")
        return data
