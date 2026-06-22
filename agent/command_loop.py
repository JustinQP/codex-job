from __future__ import annotations

import time
from threading import Event
from typing import Any
from uuid import uuid4

from agent.api_client import AgentApiClient, AgentApiError
from agent.command_handlers import CommandHandlerRegistry
from agent.heartbeat import register_agent, send_heartbeat
from agent.identity import AgentIdentity
from agent.local_state import AgentLocalState, CurrentCommandState
from agent.workspace_registry import WorkspaceRegistry
from backend.models import AgentCommandStatus
from backend.schemas import (
    AgentCommandClaimRequest,
    AgentCommandCompleteRequest,
    AgentCommandLeaseRequest,
    WorkspaceSyncRequest,
)


class AgentCommandLoop:
    def __init__(
        self,
        *,
        client: AgentApiClient,
        identity: AgentIdentity,
        local_state: AgentLocalState,
        workspace_registry: WorkspaceRegistry | None = None,
        handlers: CommandHandlerRegistry | None = None,
        poll_interval_seconds: float = 2.0,
        max_retries: int = 3,
    ) -> None:
        self.client = client
        self.identity = identity
        self.local_state = local_state
        self.workspace_registry = workspace_registry
        self.handlers = handlers or CommandHandlerRegistry()
        self.poll_interval_seconds = poll_interval_seconds
        self.max_retries = max_retries

    def bootstrap(self) -> None:
        register_agent(self.client, self.identity)
        if self.workspace_registry is not None:
            self.client.sync_workspaces(
                WorkspaceSyncRequest(
                    device_id=self.identity.device_id,
                    workspaces=self.workspace_registry.to_sync_items(),
                )
            )

    def run_forever(self, stop_event: Event | None = None) -> None:
        stop_event = stop_event or Event()
        self.bootstrap()
        while not stop_event.is_set():
            try:
                self.run_once()
            except AgentApiError:
                if stop_event.wait(self.poll_interval_seconds):
                    break
                continue
            if stop_event.wait(self.poll_interval_seconds):
                break

    def run_once(self) -> dict[str, Any] | None:
        return self._with_retries(self._run_once)

    def _run_once(self) -> dict[str, Any] | None:
        send_heartbeat(self.client, self.identity)
        current = self.local_state.load_current_command()
        if current is not None:
            command = self.client.claim_command(
                AgentCommandClaimRequest(
                    device_id=self.identity.device_id,
                    claim_request_id=current.claim_request_id,
                )
            )
        else:
            claim_request_id = str(uuid4())
            command = self.client.claim_command(
                AgentCommandClaimRequest(
                    device_id=self.identity.device_id,
                    claim_request_id=claim_request_id,
                )
            )
            if command is not None:
                current = CurrentCommandState(
                    command_id=str(command["id"]),
                    claim_request_id=claim_request_id,
                    lease_token=str(command["lease_token"]),
                )
                self.local_state.save_current_command(current)

        if command is None or current is None:
            return None

        lease = AgentCommandLeaseRequest(
            device_id=self.identity.device_id,
            lease_token=current.lease_token,
        )
        self.client.ack_command(current.command_id, lease)
        self.client.renew_command(current.command_id, lease)
        result = self.handlers.handle(command)
        self.client.complete_command(
            current.command_id,
            AgentCommandCompleteRequest(
                device_id=self.identity.device_id,
                lease_token=current.lease_token,
                status=AgentCommandStatus.SUCCESS if result.success else AgentCommandStatus.FAILED,
                error_message=None if result.success else result.message,
            ),
        )
        self.local_state.clear_current_command()
        return command

    def _with_retries(self, operation):
        last_error: AgentApiError | None = None
        for attempt in range(self.max_retries):
            try:
                return operation()
            except AgentApiError as exc:
                last_error = exc
                if attempt + 1 >= self.max_retries:
                    break
                time.sleep(min(0.2 * (attempt + 1), self.poll_interval_seconds))
        if last_error is not None:
            raise last_error
        return None
