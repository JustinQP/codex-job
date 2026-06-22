from __future__ import annotations

from pathlib import Path

from agent.api_client import AgentApiClient
from backend.schemas import RunLogChunkUpload


class RunLogUploadTracker:
    def __init__(self, log_file: Path) -> None:
        self.log_file = log_file
        self.offset = 0

    def next_chunk(self) -> tuple[int, str] | None:
        if not self.log_file.exists():
            return None
        data = self.log_file.read_bytes()
        if len(data) <= self.offset:
            return None
        chunk = data[self.offset:]
        return self.offset, chunk.decode("utf-8", errors="replace")

    def mark_uploaded(self, offset: int) -> None:
        self.offset = offset


class RunLogUploader:
    def __init__(self, *, client: AgentApiClient, tracker: RunLogUploadTracker) -> None:
        self.client = client
        self.tracker = tracker

    def upload_new_content(self, *, task_id: int, device_id: str, command_id: str) -> dict | None:
        chunk = self.tracker.next_chunk()
        if chunk is None:
            return None
        offset, content = chunk
        response = self.client.upload_run_log_chunk(
            task_id,
            RunLogChunkUpload(
                device_id=device_id,
                command_id=command_id,
                offset=offset,
                content=content,
            ),
        )
        current_offset = response.get("current_offset")
        if isinstance(current_offset, int):
            self.tracker.mark_uploaded(current_offset)
        return response
