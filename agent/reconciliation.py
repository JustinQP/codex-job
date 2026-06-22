from __future__ import annotations

from agent.api_client import AgentApiClient
from agent.identity import AgentIdentity
from agent.local_state import AgentLocalState
from backend.schemas import AgentReconcileRequest


def reconcile_local_state(
    *,
    client: AgentApiClient,
    identity: AgentIdentity,
    local_state: AgentLocalState,
    process_status: str = "STARTING",
) -> dict:
    current = local_state.load_current_command()
    response = client.reconcile(
        AgentReconcileRequest(
            device_id=identity.device_id,
            command_id=current.command_id if current else None,
            process_status=process_status,
            last_uploaded_sequence=None,
        )
    )
    if response.get("action") == "STOP":
        local_state.clear_current_command()
    return response
