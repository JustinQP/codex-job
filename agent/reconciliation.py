from __future__ import annotations

from agent.api_client import AgentApiClient
from agent.event_uploader import CommandEventUploader
from agent.identity import AgentIdentity
from agent.local_state import AgentLocalState
from backend.schemas import AgentReconcileRequest


def reconcile_local_state(
    *,
    client: AgentApiClient,
    identity: AgentIdentity,
    local_state: AgentLocalState,
    event_uploader: CommandEventUploader | None = None,
    process_status: str = "STARTING",
) -> dict:
    current = local_state.load_current_command()
    last_uploaded_sequence = (
        local_state.latest_pending_event_sequence(current.command_id)
        if current is not None
        else None
    )
    response = client.reconcile(
        AgentReconcileRequest(
            device_id=identity.device_id,
            command_id=current.command_id if current else None,
            process_status=process_status,
            last_uploaded_sequence=last_uploaded_sequence,
        )
    )
    if response.get("action") == "STOP":
        local_state.clear_current_command()
    elif response.get("action") == "UPLOAD_EVENTS" and current is not None:
        uploader = event_uploader or CommandEventUploader(client=client, local_state=local_state)
        upload_from_sequence = response.get("upload_from_sequence")
        uploader.flush(
            command_id=current.command_id,
            device_id=identity.device_id,
            lease_token=current.lease_token,
            from_sequence=upload_from_sequence if isinstance(upload_from_sequence, int) else None,
        )
    return response
