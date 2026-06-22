from __future__ import annotations

from agent.event_uploader import CommandEventUploader
from agent.local_state import AgentLocalState


class FakeEventClient:
    def __init__(self) -> None:
        self.uploads = []

    def upload_command_events(self, command_id, payload):
        self.uploads.append((command_id, payload))
        return {"accepted_count": len(payload.events), "duplicate_count": 0, "latest_sequence": 2}


def test_event_uploader_caches_until_acknowledged(tmp_path) -> None:
    client = FakeEventClient()
    state = AgentLocalState(tmp_path / "state.json")
    uploader = CommandEventUploader(client=client, local_state=state)

    uploader.cache_event(command_id="cmd-1", sequence=1, kind="log", payload={"text": "one"})
    uploader.cache_event(command_id="cmd-1", sequence=2, kind="log", payload={"text": "two"})
    response = uploader.flush(command_id="cmd-1", device_id="device-a", lease_token="lease-a")

    assert response["accepted_count"] == 2
    assert len(client.uploads) == 1
    assert client.uploads[0][1].events[0].sequence == 1
    assert state.load_pending_events("cmd-1") == []
