from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from agent.api_client import AgentApiClient
from backend.schemas import RunArtifactUpload


RUN_ARTIFACT_FILES = {
    "result": "result.md",
    "diff": "diff.patch",
    "git_status": "git-status.txt",
    "diff_unstaged": "diff-unstaged.patch",
    "diff_staged": "diff-staged.patch",
    "untracked_files": "untracked-files.txt",
    "test_output": "test-output.txt",
    "task_report": "task-report.md",
}


@dataclass(frozen=True)
class RunArtifactManifestItem:
    artifact_type: str
    filename: str
    sequence: int
    size_bytes: int
    sha256: str
    content: str


def build_run_artifact_manifest(job_dir: Path) -> list[RunArtifactManifestItem]:
    items: list[RunArtifactManifestItem] = []
    sequence = 1
    for artifact_type, filename in RUN_ARTIFACT_FILES.items():
        path = job_dir / filename
        if not path.exists() or not path.is_file():
            continue
        content_bytes = path.read_bytes()
        items.append(
            RunArtifactManifestItem(
                artifact_type=artifact_type,
                filename=filename,
                sequence=sequence,
                size_bytes=len(content_bytes),
                sha256=hashlib.sha256(content_bytes).hexdigest(),
                content=content_bytes.decode("utf-8", errors="replace"),
            )
        )
        sequence += 1
    return items


class RunArtifactUploader:
    def __init__(self, *, client: AgentApiClient) -> None:
        self.client = client

    def upload_manifest(
        self,
        *,
        task_id: int,
        device_id: str,
        command_id: str,
        manifest: list[RunArtifactManifestItem],
    ) -> list[dict]:
        responses = []
        for item in manifest:
            responses.append(
                self.client.upload_run_artifact(
                    task_id,
                    RunArtifactUpload(
                        device_id=device_id,
                        command_id=command_id,
                        artifact_type=item.artifact_type,
                        filename=item.filename,
                        sequence=item.sequence,
                        size_bytes=item.size_bytes,
                        sha256=item.sha256,
                        content=item.content,
                    ),
                )
            )
        return responses
