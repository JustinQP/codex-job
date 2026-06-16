from __future__ import annotations

import os
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from runner.config import GIT_DIFF_TIMEOUT_SECONDS


@dataclass
class CodexExecutionResult:
    exit_code: int
    timed_out: bool
    error_message: Optional[str]
    codex_bin: Optional[str]


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

    command = [
        codex_bin,
        "exec",
        "--cd",
        str(project_path),
        "--sandbox",
        "workspace-write",
        "--output-last-message",
        str(result_file),
        prompt,
    ]

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

        def stream_output() -> None:
            if process.stdout is None:
                return
            for line in process.stdout:
                log.write(line)
                log.flush()

        stream_thread = threading.Thread(target=stream_output, daemon=True)
        stream_thread.start()

        timed_out = False
        try:
            exit_code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            exit_code = -1
            log.write(f"\nERROR: task timed out after {timeout_seconds} seconds\n")
            log.flush()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                log.write("ERROR: process did not exit cleanly after kill\n")
                log.flush()

        stream_thread.join(timeout=5)
        log.write(f"\nCodex exit code: {exit_code}\n")
        log.flush()

    error_message = None
    if timed_out:
        error_message = f"task timed out after {timeout_seconds} seconds"
    elif exit_code != 0:
        error_message = f"codex exited with code {exit_code}"

    return CodexExecutionResult(
        exit_code=exit_code,
        timed_out=timed_out,
        error_message=error_message,
        codex_bin=codex_bin,
    )


def save_git_diff(project_path: Path, diff_file: Path) -> Optional[str]:
    diff_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        completed = subprocess.run(
            ["git", "diff"],
            cwd=str(project_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GIT_DIFF_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        message = "git command not found"
        diff_file.write_text(f"ERROR: {message}\n", encoding="utf-8")
        return message
    except subprocess.TimeoutExpired:
        message = f"git diff timed out after {GIT_DIFF_TIMEOUT_SECONDS} seconds"
        diff_file.write_text(f"ERROR: {message}\n", encoding="utf-8")
        return message

    if completed.returncode == 0:
        diff_file.write_text(completed.stdout, encoding="utf-8")
        return None

    content = completed.stdout
    if completed.stderr:
        content += "\n--- git diff stderr ---\n"
        content += completed.stderr
    diff_file.write_text(content, encoding="utf-8")
    return f"git diff exited with code {completed.returncode}"


def _append_log(log_file: Path, message: str) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8", errors="replace") as log:
        log.write(message)
