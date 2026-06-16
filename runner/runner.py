from __future__ import annotations

import argparse
import atexit
import socket
import logging
import os
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
from runner.codex_executor import (  # noqa: E402
    check_clean_worktree,
    collect_git_artifacts,
    ensure_git_repository,
    execute_codex,
)
from runner.config import (  # noqa: E402
    DEFAULT_TIMEOUT_SECONDS,
    JOBS_DIR,
    POLL_INTERVAL_SECONDS,
    RUNNER_LOCK_FILE,
    require_clean_worktree,
)


logger = logging.getLogger("codex-runner")
RUNNER_ID = f"{socket.gethostname()}-{os.getpid()}"


class RunnerLock:
    def __init__(self, lock_file: Path) -> None:
        self.lock_file = lock_file
        self.acquired = False

    def acquire(self) -> None:
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        self._cleanup_stale_lock_if_needed()
        try:
            fd = os.open(
                self.lock_file,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            )
        except FileExistsError as exc:
            existing = self.lock_file.read_text(
                encoding="utf-8",
                errors="replace",
            ).strip()
            detail = f" existing lock: {existing}" if existing else ""
            raise RuntimeError(
                f"runner lock already exists: {self.lock_file}.{detail}"
            ) from exc

        with os.fdopen(fd, "w", encoding="utf-8") as lock:
            lock.write(f"pid={os.getpid()}\n")
            lock.write(f"created_at={utc_now().isoformat()}\n")
        self.acquired = True

    def _cleanup_stale_lock_if_needed(self) -> None:
        if not self.lock_file.exists():
            return

        existing = self.lock_file.read_text(
            encoding="utf-8",
            errors="replace",
        )
        pid = parse_lock_pid(existing)
        if pid is not None and is_process_running(pid):
            raise RuntimeError(
                f"runner lock already exists: {self.lock_file}. "
                f"existing pid={pid}"
            )

        logger.warning("removing stale runner lock: %s", self.lock_file)
        self.lock_file.unlink(missing_ok=True)

    def release(self) -> None:
        if not self.acquired:
            return
        try:
            self.lock_file.unlink(missing_ok=True)
        finally:
            self.acquired = False


def parse_lock_pid(content: str) -> Optional[int]:
    for line in content.splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip().lower() == "pid":
            try:
                pid = int(value.strip())
            except ValueError:
                return None
            return pid if pid > 0 else None
    return None


def is_process_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


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
        project_require_clean_worktree = (
            project.require_clean_worktree if project else None
        )
        task.runner_pid = os.getpid()
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
    preflight_error = validate_git_preflight(
        project_path,
        log_file,
        require_clean=project_require_clean_worktree,
    )
    if preflight_error:
        finish_task(
            task_id,
            status=TaskStatus.FAILED,
            exit_code=-1,
            error_message=preflight_error,
        )
        return

    execution = execute_codex(
        project_path=project_path,
        prompt=prompt,
        log_file=log_file,
        result_file=result_file,
        timeout_seconds=timeout_seconds,
        should_cancel=lambda: is_cancel_requested(task_id),
    )
    diff_error = collect_git_artifacts(project_path, diff_file.parent).error_message
    test_output_error = write_test_output(task_id)

    error_messages = [
        message
        for message in (execution.error_message, diff_error, test_output_error)
        if message
    ]
    if execution.error_message == "task cancelled":
        status = TaskStatus.CANCELLED
    else:
        status = TaskStatus.SUCCESS if not error_messages else TaskStatus.FAILED
    finish_task(
        task_id,
        status=status,
        exit_code=execution.exit_code,
        error_message="; ".join(error_messages) if error_messages else None,
    )
    write_task_report(task_id)
    logger.info("task %s finished with status %s", task_id, status.value)


def is_cancel_requested(task_id: int) -> bool:
    with Session(engine) as session:
        task = session.get(Task, task_id)
        return bool(task and task.cancel_requested)


def write_test_output(task_id: int) -> Optional[str]:
    with Session(engine) as session:
        task = session.get(Task, task_id)
        if task is None or not task.diff_file:
            return "test output could not be written"
        project = session.get(Project, task.project_id)

        test_output_path = Path(task.diff_file).resolve().parent / "test-output.txt"
        lines = [
            "Configured checks are recorded but not executed automatically in v0.3.0.",
            "This avoids exposing a remote arbitrary shell execution path.",
            "",
            f"test_command={project.test_command if project else ''}",
            f"smoke_check_command={project.smoke_check_command if project else ''}",
        ]
        test_output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return None


def write_task_report(task_id: int) -> Optional[str]:
    with Session(engine) as session:
        task = session.get(Task, task_id)
        if task is None or not task.diff_file:
            return "task report could not be written"
        project = session.get(Project, task.project_id)
        report_path = Path(task.diff_file).resolve().parent / "task-report.md"
        content = "\n".join(
            [
                f"# Task {task.id} Report",
                "",
                f"- Status: {task.status.value}",
                f"- Task type: {task.task_type.value}",
                f"- Project id: {task.project_id}",
                f"- Timeout seconds: {task.timeout_seconds}",
                f"- Exit code: {task.exit_code}",
                f"- Cancel requested: {task.cancel_requested}",
                f"- Error: {task.error_message or ''}",
                f"- Project default branch: {project.default_branch if project else ''}",
                f"- Project test command: {project.test_command if project else ''}",
                f"- Project smoke check command: {project.smoke_check_command if project else ''}",
                "",
                "## Artifacts",
                "",
                "- result.md",
                "- git-status.txt",
                "- diff-unstaged.patch",
                "- diff-staged.patch",
                "- untracked-files.txt",
                "- diff.patch",
                "- test-output.txt",
            ]
        )
        report_path.write_text(content + "\n", encoding="utf-8")
        return None


def validate_git_preflight(
    project_path: Path,
    log_file: Path,
    *,
    require_clean: Optional[bool] = None,
) -> Optional[str]:
    clean_required = require_clean_worktree() if require_clean is None else require_clean
    if clean_required:
        error_message = check_clean_worktree(project_path)
    else:
        error_message = ensure_git_repository(project_path)

    if error_message:
        append_log(log_file, f"ERROR: {error_message}\n")
    return error_message


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
        task.runner_pid = None
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
    runner_lock = RunnerLock(RUNNER_LOCK_FILE)
    runner_lock.acquire()
    atexit.register(runner_lock.release)
    write_runner_record()
    logger.info("runner started")

    try:
        while True:
            task_id = claim_next_pending_task()
            write_runner_record()
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
    finally:
        runner_lock.release()


def write_runner_record() -> None:
    from backend.models import RunnerRecord

    with Session(engine) as session:
        now = utc_now()
        runner = session.get(RunnerRecord, RUNNER_ID)
        if runner is None:
            runner = RunnerRecord(
                runner_id=RUNNER_ID,
                pid=os.getpid(),
                hostname=socket.gethostname(),
                status="ONLINE",
                registered_at=now,
                last_heartbeat_at=now,
            )
        else:
            runner.pid = os.getpid()
            runner.hostname = socket.gethostname()
            runner.status = "ONLINE"
            runner.last_heartbeat_at = now
        session.add(runner)
        session.commit()


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
