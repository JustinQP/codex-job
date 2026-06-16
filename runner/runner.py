from __future__ import annotations

import argparse
import atexit
import json
import socket
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.models import TaskStatus, TaskType, utc_now  # noqa: E402
from backend.services.project_service import validate_project_whitelist  # noqa: E402
from runner.codex_executor import (  # noqa: E402
    check_clean_worktree,
    collect_git_artifacts,
    ensure_git_repository,
    execute_codex,
)
from runner.config import (  # noqa: E402
    BACKEND_URL,
    DEFAULT_TIMEOUT_SECONDS,
    JOBS_DIR,
    POLL_INTERVAL_SECONDS,
    RUNNER_LOCK_FILE,
    RUNNER_ID,
    RUNNER_TOKEN,
    require_clean_worktree,
)


logger = logging.getLogger("codex-runner")


@dataclass
class ClaimedTask:
    task_id: int
    project_id: int
    project_path: Path
    prompt: str
    timeout_seconds: int
    task_type: TaskType
    require_clean_worktree: Optional[bool]
    test_command: Optional[str]
    smoke_check_command: Optional[str]
    default_branch: Optional[str]


class LogUploadTracker:
    def __init__(self, task_id: int, log_file: Path, interval_seconds: float = 10.0):
        self.task_id = task_id
        self.log_file = log_file
        self.interval_seconds = interval_seconds
        self.last_upload_at = 0.0
        self.last_uploaded_size = 0

    def maybe_upload(self) -> None:
        now = time.monotonic()
        if now - self.last_upload_at < self.interval_seconds:
            return
        self.upload(force=False)

    def upload(self, *, force: bool) -> None:
        if not self.log_file.exists():
            return
        content = self.log_file.read_text(encoding="utf-8", errors="replace")
        if not force and len(content) == self.last_uploaded_size:
            self.last_upload_at = time.monotonic()
            return
        _upload_log_content(self.task_id, content)
        self.last_uploaded_size = len(content)
        self.last_upload_at = time.monotonic()


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


def register_runner() -> None:
    _runner_request(
        "POST",
        "/runner/register",
        {
            "runner_id": RUNNER_ID,
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
        },
    )


def send_heartbeat() -> None:
    _runner_request(
        "POST",
        "/runner/heartbeat",
        {
            "runner_id": RUNNER_ID,
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
        },
    )


def claim_next_pending_task() -> Optional[ClaimedTask]:
    payload = _runner_request(
        "POST",
        "/runner/tasks/claim",
        {"runner_id": RUNNER_ID},
    )
    if not payload:
        return None
    return ClaimedTask(
        task_id=payload["task_id"],
        project_id=payload["project_id"],
        project_path=Path(payload["project_path"]),
        prompt=payload["prompt"],
        timeout_seconds=payload.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS,
        task_type=TaskType(payload.get("task_type") or TaskType.IMPLEMENT),
        require_clean_worktree=payload.get("require_clean_worktree"),
        test_command=payload.get("test_command"),
        smoke_check_command=payload.get("smoke_check_command"),
        default_branch=payload.get("default_branch"),
    )


def process_task(task: ClaimedTask) -> None:
    logger.info("processing task %s", task.task_id)
    log_file, result_file, diff_file = ensure_artifact_paths(task.task_id)
    log_tracker = LogUploadTracker(task.task_id, log_file)

    validation_error = validate_project(task.project_path, True)
    if validation_error:
        append_log(log_file, f"ERROR: {validation_error}\n")
        upload_artifacts(task.task_id, log_file, result_file, diff_file, log_tracker)
        finish_task(
            task.task_id,
            status=TaskStatus.FAILED,
            exit_code=-1,
            error_message=validation_error,
        )
        return

    preflight_error = validate_git_preflight(
        task.project_path,
        log_file,
        require_clean=task.require_clean_worktree,
    )
    if preflight_error:
        upload_artifacts(task.task_id, log_file, result_file, diff_file, log_tracker)
        finish_task(
            task.task_id,
            status=TaskStatus.FAILED,
            exit_code=-1,
            error_message=preflight_error,
        )
        return

    execution = execute_codex(
        project_path=task.project_path,
        prompt=task.prompt,
        log_file=log_file,
        result_file=result_file,
        timeout_seconds=task.timeout_seconds,
        should_cancel=lambda: is_cancel_requested(task.task_id),
        on_tick=log_tracker.maybe_upload,
    )
    diff_error = collect_git_artifacts(task.project_path, diff_file.parent).error_message
    test_output_error = write_test_output(task, diff_file.parent)

    error_messages = [
        message
        for message in (execution.error_message, diff_error, test_output_error)
        if message
    ]
    if execution.error_message == "task cancelled":
        status = TaskStatus.CANCELLED
    else:
        status = TaskStatus.SUCCESS if not error_messages else TaskStatus.FAILED
    write_task_report(
        task,
        diff_file.parent,
        status=status,
        exit_code=execution.exit_code,
        error_message="; ".join(error_messages) if error_messages else None,
    )
    upload_artifacts(task.task_id, log_file, result_file, diff_file, log_tracker)
    finish_task(
        task.task_id,
        status=status,
        exit_code=execution.exit_code,
        error_message="; ".join(error_messages) if error_messages else None,
    )
    logger.info("task %s finished with status %s", task.task_id, status.value)


def is_cancel_requested(task_id: int) -> bool:
    payload = _runner_request(
        "GET",
        f"/runner/tasks/{task_id}/cancel-state?runner_id={RUNNER_ID}",
    )
    return bool(payload and payload.get("cancel_requested"))


def write_test_output(task: ClaimedTask, job_dir: Path) -> Optional[str]:
    test_output_path = job_dir / "test-output.txt"
    lines = [
        "Configured checks are recorded but not executed automatically in v0.5.0.",
        "This avoids exposing a remote arbitrary shell execution path.",
        "",
        f"test_command={task.test_command or ''}",
        f"smoke_check_command={task.smoke_check_command or ''}",
    ]
    test_output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return None


def write_task_report(
    task: ClaimedTask,
    job_dir: Path,
    *,
    status: TaskStatus,
    exit_code: Optional[int],
    error_message: Optional[str],
) -> Optional[str]:
    report_path = job_dir / "task-report.md"
    content = "\n".join(
        [
            f"# Task {task.task_id} Report",
            "",
            f"- Status: {status.value}",
            f"- Task type: {task.task_type.value}",
            f"- Project id: {task.project_id}",
            f"- Timeout seconds: {task.timeout_seconds}",
            f"- Exit code: {exit_code}",
            "- Cancel requested: see backend task state",
            f"- Error: {error_message or ''}",
            f"- Project default branch: {task.default_branch or ''}",
            f"- Project test command: {task.test_command or ''}",
            f"- Project smoke check command: {task.smoke_check_command or ''}",
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


def ensure_artifact_paths(task_id: int) -> tuple[Path, Path, Path]:
    job_dir = JOBS_DIR / str(task_id)
    job_dir.mkdir(parents=True, exist_ok=True)

    log_file = job_dir / "run.log"
    result_file = job_dir / "result.md"
    diff_file = job_dir / "diff.patch"
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
    whitelist_error = validate_project_whitelist(project_path.resolve())
    if whitelist_error:
        return whitelist_error
    return None


def finish_task(
    task_id: int,
    *,
    status: TaskStatus,
    exit_code: Optional[int],
    error_message: Optional[str],
) -> None:
    _runner_request(
        "POST",
        f"/runner/tasks/{task_id}/finish",
        {
            "runner_id": RUNNER_ID,
            "status": status.value,
            "exit_code": exit_code,
            "error_message": error_message,
        },
    )


def upload_artifacts(
    task_id: int,
    log_file: Path,
    result_file: Path,
    diff_file: Path,
    log_tracker: Optional[LogUploadTracker] = None,
) -> None:
    job_dir = diff_file.parent
    try:
        if log_tracker is None:
            _upload_log_content(task_id, _read_text_if_exists(log_file))
        else:
            log_tracker.upload(force=True)
        _runner_request(
            "POST",
            f"/runner/tasks/{task_id}/artifacts",
            {
                "runner_id": RUNNER_ID,
                "result": _read_text_if_exists(result_file),
                "diff": _read_text_if_exists(diff_file),
                "git_status": _read_text_if_exists(job_dir / "git-status.txt"),
                "diff_unstaged": _read_text_if_exists(job_dir / "diff-unstaged.patch"),
                "diff_staged": _read_text_if_exists(job_dir / "diff-staged.patch"),
                "untracked_files": _read_text_if_exists(job_dir / "untracked-files.txt"),
                "test_output": _read_text_if_exists(job_dir / "test-output.txt"),
                "task_report": _read_text_if_exists(job_dir / "task-report.md"),
            },
        )
    except Exception as exc:
        write_upload_pending(job_dir, task_id, str(exc))
        raise
    clear_upload_pending(job_dir)


def _upload_log_content(task_id: int, content: str) -> None:
    _runner_request(
        "POST",
        f"/runner/tasks/{task_id}/log",
        {
            "runner_id": RUNNER_ID,
            "content": content,
            "append": False,
        },
    )


def write_upload_pending(job_dir: Path, task_id: int, error_message: str) -> None:
    payload = {
        "task_id": task_id,
        "runner_id": RUNNER_ID,
        "error_message": error_message,
        "created_at": utc_now().isoformat(),
        "retry_hint": "rerun runner upload manually after backend connectivity is restored",
    }
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "upload-pending.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def clear_upload_pending(job_dir: Path) -> None:
    (job_dir / "upload-pending.json").unlink(missing_ok=True)


def _read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def append_log(log_file: Path, message: str) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8", errors="replace") as log:
        log.write(message)


def run_loop(*, once: bool, poll_interval: float) -> None:
    runner_lock = RunnerLock(RUNNER_LOCK_FILE)
    runner_lock.acquire()
    atexit.register(runner_lock.release)
    register_runner()
    logger.info("runner started")

    try:
        while True:
            send_heartbeat()
            task = claim_next_pending_task()
            if task is None:
                if once:
                    logger.info("no pending task found")
                    return
                time.sleep(poll_interval)
                continue

            try:
                process_task(task)
            except Exception as exc:  # noqa: BLE001
                logger.exception("task %s failed with unexpected error", task.task_id)
                finish_task(
                    task.task_id,
                    status=TaskStatus.FAILED,
                    exit_code=-1,
                    error_message=f"runner error: {exc}",
                )

            if once:
                return
    finally:
        runner_lock.release()


def _runner_request(
    method: str,
    path: str,
    payload: Optional[dict] = None,
) -> Optional[dict]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if RUNNER_TOKEN:
        headers["X-API-Token"] = RUNNER_TOKEN

    url = f"{BACKEND_URL}{path}"
    raw = _open_runner_request_with_retry(method, url, body, headers)

    if not raw:
        return None
    return json.loads(raw)


def _open_runner_request_with_retry(
    method: str,
    url: str,
    body: Optional[bytes],
    headers: dict[str, str],
    *,
    attempts: int = 3,
    retry_delay_seconds: float = 1.0,
) -> str:
    last_error: Optional[BaseException] = None
    for attempt in range(1, attempts + 1):
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                return response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code < 500 or attempt == attempts:
                raise RuntimeError(
                    f"{method} {url} failed: {exc.code} {detail}"
                ) from exc
            last_error = exc
            logger.warning(
                "%s %s failed with %s; retrying attempt %s/%s",
                method,
                url,
                exc.code,
                attempt + 1,
                attempts,
            )
        except URLError as exc:
            if attempt == attempts:
                raise RuntimeError(f"{method} {url} failed: {exc}") from exc
            last_error = exc
            logger.warning(
                "%s %s failed with network error; retrying attempt %s/%s: %s",
                method,
                url,
                attempt + 1,
                attempts,
                exc,
            )
        time.sleep(retry_delay_seconds)
    raise RuntimeError(f"{method} {url} failed after retries: {last_error}")


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
