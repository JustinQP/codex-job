from __future__ import annotations

from pathlib import Path

from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from backend.models import Project, Task, TaskStatus, TaskType, utc_now
from backend.schemas import (
    RunnerTaskArtifactsUpload,
    RunnerTaskFinishRequest,
    RunnerTaskLogUpload,
)
from backend.services import runner_service


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def add_project_and_task(session: Session, project_path: Path) -> Task:
    project = Project(
        name="demo",
        path=str(project_path),
        enabled=True,
        test_command="pytest -q",
        smoke_check_command="python -m compileall backend",
        default_branch="main",
        require_clean_worktree=True,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    task = Task(
        project_id=project.id,
        prompt="remote work",
        task_type=TaskType.IMPLEMENT,
        status=TaskStatus.PENDING,
        timeout_seconds=120,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def test_runner_service_claim_upload_and_finish(
    monkeypatch,
    tmp_path: Path,
) -> None:
    jobs_dir = tmp_path / "jobs"
    monkeypatch.setattr(runner_service, "JOBS_DIR", jobs_dir)
    session = make_session()
    try:
        task = add_project_and_task(session, tmp_path / "project")

        claimed = runner_service.claim_task(session, "runner-1")

        assert claimed is not None
        assert claimed.task_id == task.id
        assert claimed.prompt == "remote work"
        assert claimed.project_path == str(tmp_path / "project")
        db_task = session.get(Task, task.id)
        assert db_task.status == TaskStatus.RUNNING
        assert db_task.runner_id == "runner-1"

        runner_service.upload_task_log(
            session,
            task.id,
            RunnerTaskLogUpload(
                runner_id="runner-1",
                content="first\n",
                append=False,
            ),
        )
        runner_service.upload_task_log(
            session,
            task.id,
            RunnerTaskLogUpload(
                runner_id="runner-1",
                content="second\n",
                append=True,
            ),
        )
        runner_service.upload_task_artifacts(
            session,
            task.id,
            RunnerTaskArtifactsUpload(
                runner_id="runner-1",
                result="result text",
                diff="diff text",
                git_status=" M file.py",
                task_report="# report",
            ),
        )
        finished = runner_service.finish_task(
            session,
            task.id,
            RunnerTaskFinishRequest(
                runner_id="runner-1",
                status=TaskStatus.SUCCESS,
                exit_code=0,
                error_message=None,
            ),
        )

        assert finished.status == TaskStatus.SUCCESS
        assert finished.exit_code == 0
        assert finished.runner_id is None
        assert (jobs_dir / str(task.id) / "run.log").read_text(encoding="utf-8") == (
            "first\nsecond\n"
        )
        assert (jobs_dir / str(task.id) / "result.md").read_text(
            encoding="utf-8"
        ) == "result text"
        assert (jobs_dir / str(task.id) / "diff.patch").read_text(
            encoding="utf-8"
        ) == "diff text"
        assert (jobs_dir / str(task.id) / "git-status.txt").read_text(
            encoding="utf-8"
        ) == " M file.py"
    finally:
        session.close()


def test_runner_service_claim_returns_none_without_pending_task() -> None:
    session = make_session()
    try:
        assert runner_service.claim_task(session, "runner-1") is None
    finally:
        session.close()
