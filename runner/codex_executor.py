from __future__ import annotations

import os
import platform
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from runner.config import GIT_DIFF_TIMEOUT_SECONDS


@dataclass
class CodexExecutionResult:
    exit_code: int
    timed_out: bool
    error_message: Optional[str]
    codex_bin: Optional[str]


@dataclass
class GitArtifactsResult:
    error_message: Optional[str]
    status_file: Path
    diff_unstaged_file: Path
    diff_staged_file: Path
    untracked_files_file: Path
    combined_diff_file: Path


def find_codex_bin() -> str:
    env_bin = os.environ.get("CODEX_BIN")
    if env_bin:
        found = shutil.which(env_bin)
        if found:
            return found

        explicit_path = Path(env_bin).expanduser()
        if explicit_path.exists():
            return str(explicit_path.resolve())

        raise FileNotFoundError(f"CODEX_BIN is set but not found: {env_bin}")

    for candidate in ("codex.cmd", "codex", "codex.exe"):
        found = shutil.which(candidate)
        if found:
            return found

    raise FileNotFoundError("codex CLI not found; set CODEX_BIN or add codex to PATH")


def execute_codex(
    *,
    project_path: Path,
    prompt: str,
    log_file: Path,
    result_file: Path,
    timeout_seconds: int,
    model: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    sandbox: str = "workspace-write",
    should_cancel: Optional[Callable[[], bool]] = None,
    on_tick: Optional[Callable[[], None]] = None,
    on_process_started: Optional[Callable[[subprocess.Popen[str]], None]] = None,
    on_process_finished: Optional[Callable[[], None]] = None,
) -> CodexExecutionResult:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    result_file.parent.mkdir(parents=True, exist_ok=True)
    result_file.touch(exist_ok=True)

    try:
        codex_bin = find_codex_bin()
    except FileNotFoundError as exc:
        _append_log(log_file, f"ERROR: {exc}\n")
        return CodexExecutionResult(
            exit_code=-1,
            timed_out=False,
            error_message=str(exc),
            codex_bin=None,
        )

    command = build_codex_command(
        codex_bin=codex_bin,
        project_path=project_path,
        result_file=result_file,
        prompt=prompt,
        model=model,
        reasoning_effort=reasoning_effort,
        sandbox=sandbox,
    )

    with log_file.open("a", encoding="utf-8", errors="replace") as log:
        log.write(f"Starting codex task in {project_path}\n")
        log.write(f"Codex binary: {codex_bin}\n")
        log.write(f"Timeout seconds: {timeout_seconds}\n")
        log.flush()

        try:
            process = subprocess.Popen(
                command,
                cwd=str(project_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except OSError as exc:
            message = f"failed to start codex: {exc}"
            log.write(f"ERROR: {message}\n")
            log.flush()
            return CodexExecutionResult(
                exit_code=-1,
                timed_out=False,
                error_message=message,
                codex_bin=codex_bin,
            )

        if on_process_started is not None:
            try:
                on_process_started(process)
            except Exception as exc:  # noqa: BLE001
                message = f"on_process_started failed: {exc}"
                log.write(f"ERROR: {message}\n")
                log.flush()
                _stop_process_tree(process, log)
                return CodexExecutionResult(
                    exit_code=-1,
                    timed_out=False,
                    error_message=message,
                    codex_bin=codex_bin,
                )

        def stream_output() -> None:
            if process.stdout is None:
                return
            for line in process.stdout:
                log.write(line)
                log.flush()

        stream_thread = threading.Thread(target=stream_output, daemon=True)
        stream_thread.start()

        timed_out = False
        deadline = time.monotonic() + timeout_seconds
        cancelled = False
        callback_error: Optional[str] = None
        exit_code: Optional[int] = None
        while exit_code is None:
            exit_code = process.poll()
            if exit_code is not None:
                break
            try:
                cancel_requested = (
                    should_cancel() if should_cancel is not None else False
                )
            except Exception as exc:  # noqa: BLE001
                callback_error = f"should_cancel failed: {exc}"
                exit_code = -1
                log.write(f"\nERROR: {callback_error}\n")
                log.write(f"Attempting to stop process tree for pid={process.pid}\n")
                log.flush()
                _stop_process_tree(process, log)
                break
            if cancel_requested:
                cancelled = True
                exit_code = -1
                log.write(f"\nERROR: cancellation requested for pid={process.pid}\n")
                log.write(f"Attempting to stop process tree for pid={process.pid}\n")
                log.flush()
                _stop_process_tree(process, log)
                break
            if time.monotonic() >= deadline:
                timed_out = True
                exit_code = -1
                log.write(f"\nERROR: task timed out after {timeout_seconds} seconds\n")
                log.write(f"Attempting to stop process tree for pid={process.pid}\n")
                log.flush()
                _stop_process_tree(process, log)
                break
            if on_tick is not None:
                try:
                    on_tick()
                except Exception as exc:  # noqa: BLE001
                    callback_error = f"on_tick failed: {exc}"
                    exit_code = -1
                    log.write(f"\nERROR: {callback_error}\n")
                    log.write(
                        f"Attempting to stop process tree for pid={process.pid}\n"
                    )
                    log.flush()
                    _stop_process_tree(process, log)
                    break
            time.sleep(1)

        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            log.write("ERROR: process did not exit cleanly after stop request\n")
            log.flush()
        finally:
            if on_process_finished is not None:
                on_process_finished()

        stream_thread.join(timeout=5)
        log.write(f"\nCodex exit code: {exit_code}\n")
        log.flush()

    error_message = None
    if callback_error:
        error_message = callback_error
    elif timed_out:
        error_message = f"task timed out after {timeout_seconds} seconds"
    elif cancelled:
        error_message = "task cancelled"
    elif exit_code != 0:
        error_message = f"codex exited with code {exit_code}"

    return CodexExecutionResult(
        exit_code=exit_code,
        timed_out=timed_out,
        error_message=error_message,
        codex_bin=codex_bin,
    )


def build_codex_command(
    *,
    codex_bin: str,
    project_path: Path,
    result_file: Path,
    prompt: str,
    model: Optional[str],
    reasoning_effort: Optional[str],
    sandbox: str,
) -> list[str]:
    command = [
        codex_bin,
        "exec",
        "--cd",
        str(project_path),
        "--sandbox",
        sandbox or "workspace-write",
        "--output-last-message",
        str(result_file),
    ]
    if model and model != "default":
        command.extend(["--model", model])
    if reasoning_effort and reasoning_effort != "default":
        command.extend(["-c", f"reasoning_effort={reasoning_effort}"])
    command.append(prompt)
    return command


def ensure_git_repository(project_path: Path) -> Optional[str]:
    completed = _run_git(project_path, ["git", "rev-parse", "--is-inside-work-tree"])
    if completed.returncode != 0:
        return _git_error("project is not a git repository", completed)
    if completed.stdout.strip().lower() != "true":
        return "project is not a git repository"
    return None


def check_clean_worktree(project_path: Path) -> Optional[str]:
    repository_error = ensure_git_repository(project_path)
    if repository_error:
        return repository_error

    completed = _run_git(project_path, ["git", "status", "--porcelain"])
    if completed.returncode != 0:
        return _git_error("failed to inspect git status", completed)
    if completed.stdout.strip():
        return "git worktree is not clean"
    return None


def collect_git_artifacts(project_path: Path, job_dir: Path) -> GitArtifactsResult:
    job_dir.mkdir(parents=True, exist_ok=True)

    status_file = job_dir / "git-status.txt"
    diff_unstaged_file = job_dir / "diff-unstaged.patch"
    diff_staged_file = job_dir / "diff-staged.patch"
    untracked_files_file = job_dir / "untracked-files.txt"
    combined_diff_file = job_dir / "diff.patch"

    commands = [
        (status_file, ["git", "status", "--short"]),
        (diff_unstaged_file, ["git", "diff"]),
        (diff_staged_file, ["git", "diff", "--cached"]),
        (untracked_files_file, ["git", "ls-files", "--others", "--exclude-standard"]),
    ]

    errors: list[str] = []
    for output_file, command in commands:
        completed = _run_git(project_path, command)
        content = completed.stdout
        if completed.stderr:
            content += "\n--- stderr ---\n"
            content += completed.stderr
        output_file.write_text(content, encoding="utf-8")
        if completed.returncode != 0:
            errors.append(_git_error(f"{' '.join(command)} failed", completed))

    _write_combined_git_diff(
        combined_diff_file=combined_diff_file,
        status_file=status_file,
        diff_unstaged_file=diff_unstaged_file,
        diff_staged_file=diff_staged_file,
        untracked_files_file=untracked_files_file,
    )

    return GitArtifactsResult(
        error_message="; ".join(errors) if errors else None,
        status_file=status_file,
        diff_unstaged_file=diff_unstaged_file,
        diff_staged_file=diff_staged_file,
        untracked_files_file=untracked_files_file,
        combined_diff_file=combined_diff_file,
    )


def save_git_diff(project_path: Path, diff_file: Path) -> Optional[str]:
    result = collect_git_artifacts(project_path, diff_file.parent)
    return result.error_message


def _run_git(project_path: Path, command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=str(project_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GIT_DIFF_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(
            command,
            returncode=127,
            stdout="",
            stderr="git command not found",
        )
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(
            command,
            returncode=124,
            stdout=exc.stdout or "",
            stderr=f"git command timed out after {GIT_DIFF_TIMEOUT_SECONDS} seconds",
        )


def _git_error(prefix: str, completed: subprocess.CompletedProcess[str]) -> str:
    detail = completed.stderr.strip() or completed.stdout.strip()
    if detail:
        return f"{prefix}: {detail}"
    return f"{prefix}: exit code {completed.returncode}"


def _write_combined_git_diff(
    *,
    combined_diff_file: Path,
    status_file: Path,
    diff_unstaged_file: Path,
    diff_staged_file: Path,
    untracked_files_file: Path,
) -> None:
    sections = [
        ("git status --short", status_file),
        ("git diff", diff_unstaged_file),
        ("git diff --cached", diff_staged_file),
        ("untracked files", untracked_files_file),
    ]
    parts = []
    for title, path in sections:
        parts.append(f"--- {title} ---\n")
        parts.append(path.read_text(encoding="utf-8", errors="replace"))
        if not parts[-1].endswith("\n"):
            parts.append("\n")
        parts.append("\n")
    combined_diff_file.write_text("".join(parts), encoding="utf-8")


def _stop_process_tree(process: subprocess.Popen[str], log) -> None:
    if platform.system().lower() == "windows":
        command = ["taskkill", "/PID", str(process.pid), "/T", "/F"]
        log.write(f"Running kill command: {' '.join(command)}\n")
        log.flush()
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            if completed.stdout:
                log.write(completed.stdout)
            if completed.stderr:
                log.write(completed.stderr)
            log.write(f"taskkill exit code: {completed.returncode}\n")
            log.flush()
            return
        except Exception as exc:  # noqa: BLE001
            log.write(f"ERROR: taskkill failed: {exc}\n")
            log.flush()

    log.write(f"Calling terminate for pid={process.pid}\n")
    log.flush()
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        log.write(f"Calling kill for pid={process.pid}\n")
        log.flush()
        process.kill()


def _append_log(log_file: Path, message: str) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8", errors="replace") as log:
        log.write(message)
