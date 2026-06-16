from __future__ import annotations

from pathlib import Path

from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

import runner.runner as runner_module
from backend.models import Project, Task, TaskStatus, TaskType, utc_now


def test_write_task_report_and_test_output(tmp_path: Path, monkeypatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(runner_module, "engine", engine)

    with Session(engine) as session:
        project = Project(
            name="demo",
            path=str(tmp_path),
            enabled=True,
            test_command="pytest -q",
            smoke_check_command="python -m compileall backend",
            default_branch="main",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(project)
        session.commit()
        session.refresh(project)

        job_dir = tmp_path / "job"
        job_dir.mkdir()
        task = Task(
            project_id=project.id,
            prompt="do work",
            task_type=TaskType.IMPLEMENT,
            status=TaskStatus.SUCCESS,
            timeout_seconds=120,
            diff_file=str(job_dir / "diff.patch"),
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        task_id = task.id

    assert runner_module.write_test_output(task_id) is None
    assert runner_module.write_task_report(task_id) is None
    assert "pytest -q" in (job_dir / "test-output.txt").read_text(encoding="utf-8")
    assert "Task" in (job_dir / "task-report.md").read_text(encoding="utf-8")
