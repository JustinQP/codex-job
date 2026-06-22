from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agent.api_client import AgentApiClient
from agent.local_state import AgentLocalState, PendingCommandEvent
from backend.schemas import AgentCommandEventUploadItem, AgentCommandEventsUploadRequest


class CommandEventUploader:
    def __init__(self, *, client: AgentApiClient, local_state: AgentLocalState) -> None:
        self.client = client
        self.local_state = local_state

    def cache_event(self, *, command_id: str, sequence: int, kind: str, payload: dict[str, Any]) -> None:
        self.local_state.append_pending_event(
            PendingCommandEvent(
                command_id=command_id,
                sequence=sequence,
                kind=kind,
                payload=payload,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        )

    def flush(self, *, command_id: str, device_id: str, lease_token: str) -> dict[str, Any] | None:
        pending = self.local_state.load_pending_events(command_id)
        if not pending:
            return None
        response = self.client.upload_command_events(
            command_id,
            AgentCommandEventsUploadRequest(
                device_id=device_id,
                lease_token=lease_token,
                events=[
                    AgentCommandEventUploadItem(
                        sequence=event.sequence,
                        kind=event.kind,
                        payload=event.payload,
                        created_at=event.created_at,
                    )
                    for event in pending
                ],
            ),
        )
        latest_sequence = response.get("latest_sequence")
        if isinstance(latest_sequence, int):
            self.local_state.clear_pending_events(command_id, latest_sequence)
        return response
