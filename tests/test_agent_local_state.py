from __future__ import annotations

from agent.local_state import AgentLocalState, CurrentCommandState


def test_agent_local_state_recovers_current_command_from_backup(tmp_path) -> None:
    state_path = tmp_path / "state.json"
    backup_path = tmp_path / "state.json.bak"
    backup_path.write_text(
        """
{
  "current_command": {
    "command_id": "cmd-1",
    "claim_request_id": "claim-1",
    "lease_token": "lease-1",
    "phase": "COMPLETION_PENDING",
    "status": "SUCCESS",
    "error_message": null,
    "result_payload": {"ok": true}
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    state_path.write_text("{broken", encoding="utf-8")

    current = AgentLocalState(state_path).load_current_command()

    assert current is not None
    assert current.command_id == "cmd-1"
    assert current.phase == "COMPLETION_PENDING"
    assert current.result_payload == {"ok": True}


def test_agent_local_state_writes_backup_before_replacing_existing_state(tmp_path) -> None:
    state_path = tmp_path / "state.json"
    state = AgentLocalState(state_path)
    state.save_current_command(
        CurrentCommandState(
            command_id="cmd-old",
            claim_request_id="claim-old",
            lease_token="lease-old",
        )
    )

    state.save_current_command(
        CurrentCommandState(
            command_id="cmd-new",
            claim_request_id="claim-new",
            lease_token="lease-new",
        )
    )

    backup_text = state_path.with_suffix(state_path.suffix + ".bak").read_text(encoding="utf-8")
    assert "cmd-old" in backup_text
    assert state.load_current_command().command_id == "cmd-new"
