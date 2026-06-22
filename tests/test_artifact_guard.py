from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.routers.tasks import _read_task_artifact


class FakeTask:
    def __init__(self, log_file: str) -> None:
        self.log_file = log_file


def test_read_task_artifact_rejects_path_outside_jobs_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    outside_file = tmp_path / "outside.log"
    outside_file.write_text("outside", encoding="utf-8")

    def fake_get_task_or_404(session, task_id: int) -> FakeTask:
        return FakeTask(str(outside_file))

    monkeypatch.setattr(
        "backend.routers.tasks.task_service.get_task_or_404",
        fake_get_task_or_404,
    )

    with pytest.raises(HTTPException) as exc_info:
        _read_task_artifact(1, "log_file", session=object())

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "artifact path is outside jobs directory"
