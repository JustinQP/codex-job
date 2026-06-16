from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlmodel import Session, select  # noqa: E402

from backend.db import engine, init_db  # noqa: E402
from backend.models import Project, Task, TaskStatus, utc_now  # noqa: E402
from runner.codex_executor import execute_codex, save_git_diff  # noqa: E402
from runner.config import DEFAULT_TIMEOUT_SECONDS, JOBS_DIR, POLL_INTERVAL_SECONDS  # noqa: E402


logger = logging.getLogger("codex-runner")


def claim_next_pending_task() -> Optional[int]:
    with Session(engine) as session:
        task = session.exec(
            select(Task)
            .where(Task.status == TaskStatus.PENDING)
            .order_by(Task.created_at)
        ).first()
        if task is None or task.id is None:
            return None

        now = utc_now()
        task.status = TaskStatus.RUNNING
        task.started_at = now
        task.updated_at = now
        session.add(task)
        session.commit()
        return task.id


def process_task(task_id: int) -> None:
    logger.info("processing task %s", task_id)

    with Session(engine) as session:
        task = session.get(Task, task_id)
        if task is None:
            logger.warning("task %s disappeared before processing", task_id)
            return

        project = session.get(Project, task.project_id)
        log_file, result_file, diff_file = ensure_artifact_paths(task)
        prompt = task.prompt
        timeout_seconds = task.timeout_seconds or DEFAULT_TIMEOUT_SECONDS
        project_path = Path(project.path) if project else None
        project_enabled = bool(project.enabled) if project else False
        session.add(task)
        session.commit()

    validation_error = validate_project(project_path, project_enabled)
    if validation_error:
        append_log(log_file, f"ERROR: {validation_error}\n")
        finish_task(
            task_id,
            status=TaskStatus.FAILED,
            exit_code=-1,
            error_message=validation_error,
        )
        return

    assert project_path is not None
    execution = execute_codex(
        project_path=project_path,
        prompt=prompt,
        log_file=log_file,
        result_file=result_file,
        timeout_seconds=timeout_seconds,
    )
    diff_error = save_git_diff(project_path, diff_file)

    error_messages = [
        message for message in (execution.error_message, diff_error) if message
    ]
    status = TaskStatus.SUCCESS if not error_messages else TaskStatus.FAILED
    finish_task(
        task_id,
        status=status,
        exit_code=execution.exit_code,
        error_message="; ".join(error_messages) if error_messages else None,
    )
    logger.info("task %s finished with status %s", task_id, status.value)


def ensure_artifact_paths(task: Task) -> tuple[Path, Path, Path]:
    if task.id is None:
        raise ValueError("task id is required")

    job_dir = JOBS_DIR / str(task.id)
    job_dir.mkdir(parents=True, exist_ok=True)

    log_file = job_dir / "run.log"
    result_file = job_dir / "result.md"
    diff_file = job_dir / "diff.patch"

    task.log_file = str(log_file)
    task.result_file = str(result_file)
    task.diff_file = str(diff_file)
    task.updated_at = utc_now()
    return log_file, result_file, diff_file


def validate_project(project_path: Optional[Path], project_enabled: bool) -> Optional[str]:
    if project_path is None:
        return "project not found"
    if not project_enabled:
        return "project is disabled"
    if not project_path.exists():
        return "project path does not exist"
    if not project_path.is_dir():
        return "project path must be a directory"
    return None


def finish_task(
    task_id: int,
    *,
    status: TaskStatus,
    exit_code: Optional[int],
    error_message: Optional[str],
) -> None:
    with Session(engine) as session:
        task = session.get(Task, task_id)
        if task is None:
            return

        now = utc_now()
        task.status = status
        task.exit_code = exit_code
        task.error_message = error_message
        task.finished_at = now
        task.updated_at = now
        session.add(task)
        session.commit()


def append_log(log_file: Path, message: str) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8", errors="replace") as log:
        log.write(message)


def run_loop(*, once: bool, poll_interval: float) -> None:
    init_db()
    logger.info("runner started")

    while True:
        task_id = claim_next_pending_task()
        if task_id is None:
            if once:
                logger.info("no pending task found")
                return
            time.sleep(poll_interval)
            continue

        try:
            process_task(task_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("task %s failed with unexpected error", task_id)
            finish_task(
                task_id,
                status=TaskStatus.FAILED,
                exit_code=-1,
                error_message=f"runner error: {exc}",
            )

        if once:
            return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Codex Remote Runner worker")
    parser.add_argument("--once", action="store_true", help="process at most one task")
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=POLL_INTERVAL_SECONDS,
        help="poll interval in seconds",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = parse_args()
    try:
        run_loop(once=args.once, poll_interval=args.poll_interval)
    except KeyboardInterrupt:
        logger.info("runner stopped")


if __name__ == "__main__":
    main()
