from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, status
from sqlmodel import Session, select

from backend.db import JOBS_DIR
from backend.models import AgentCommandStatus, Device, DeviceStatus, Project, RunnerRecord, Task, TaskStatus, TaskType, Workspace, utc_now
from backend.schemas import RunCreate, TaskCreate
from backend.services import agent_command_service, workspace_lock_service


TASK_TEMPLATES: dict[TaskType, tuple[str, str]] = {
    TaskType.PLAN: (
        "生成计划",
        "请基于以下目标生成一个可执行开发计划，包含范围、步骤、验证方式和风险：\n\n{goal}",
    ),
    TaskType.IMPLEMENT: (
        "执行开发",
        "请基于以下目标进行最小必要实现，并完成自检：\n\n{goal}",
    ),
    TaskType.REVIEW: (
        "代码审查",
        "请对当前项目中与以下目标相关的改动进行代码审查，优先指出 bug、风险和缺失测试：\n\n{goal}",
    ),
    TaskType.TEST_FIX: (
        "测试修复",
        "请运行或分析相关测试，修复以下测试/验证问题，并说明结果：\n\n{goal}",
    ),
    TaskType.DOCS: (
        "文档更新",
        "请根据以下目标更新必要文档，保持内容准确、简洁、可维护：\n\n{goal}",
    ),
    TaskType.COMMIT: (
        "提交准备",
        "请检查当前改动，完成必要自检，并准备清晰的提交说明。不要自动 push：\n\n{goal}",
    ),
}

DEFAULT_SANDBOX = "workspace-write"


def _artifact_paths(task_id: int) -> tuple[Path, Path, Path]:
    job_dir = JOBS_DIR / str(task_id)
    return job_dir / "run.log", job_dir / "result.md", job_dir / "diff.patch"


def _assign_artifact_paths(task: Task) -> None:
    if task.id is None:
        raise ValueError("task id is required before assigning artifact paths")

    log_file, result_file, diff_file = _artifact_paths(task.id)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    task.log_file = str(log_file)
    task.result_file = str(result_file)
    task.diff_file = str(diff_file)
    task.updated_at = utc_now()


def create_task(session: Session, payload: TaskCreate) -> Task:
    project = session.get(Project, payload.project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="project not found",
        )
    if not project.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project is disabled",
        )
    assigned_runner_id = payload.assigned_runner_id or project.default_runner_id
    if assigned_runner_id and session.get(RunnerRecord, assigned_runner_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"assigned runner not found: {assigned_runner_id}",
        )

    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="prompt cannot be empty",
        )

    now = utc_now()
    task = Task(
        project_id=payload.project_id,
        prompt=prompt,
        task_type=payload.task_type,
        timeout_seconds=payload.timeout_seconds,
        model=payload.model or project.default_model,
        reasoning_effort=(
            payload.reasoning_effort or project.default_reasoning_effort
        ),
        sandbox=payload.sandbox or project.default_sandbox or DEFAULT_SANDBOX,
        status=TaskStatus.PENDING,
        assigned_runner_id=assigned_runner_id,
        client_request_id=payload.client_request_id,
        created_at=now,
        updated_at=now,
    )
    session.add(task)
    session.commit()
    session.refresh(task)

    _assign_artifact_paths(task)
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def create_run(session: Session, payload: RunCreate) -> Task:
    workspace = session.get(Workspace, payload.workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="workspace not found",
        )
    if not workspace.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="workspace is disabled",
        )
    from backend.models import Device

    device = session.get(Device, workspace.device_id)
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="device not found",
        )
    if device.status == DeviceStatus.DISABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="device is disabled",
        )
    if device.status != DeviceStatus.ONLINE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="device is offline",
        )
    project = session.get(Project, payload.project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="project not found",
        )
    requested_sandbox = payload.sandbox or project.default_sandbox or DEFAULT_SANDBOX
    workspace_lock_service.ensure_workspace_available(
        session,
        workspace_id=workspace.id,
        sandbox=requested_sandbox,
    )

    task = create_task(session, payload)
    task.workspace_id = workspace.id
    task.device_id = workspace.device_id
    task.client_request_id = payload.client_request_id
    session.add(task)
    session.commit()
    session.refresh(task)
    if task.id is None:
        raise ValueError("task id is required")
    workspace_lock_service.acquire_workspace_lock(
        session,
        workspace_id=workspace.id,
        owner_type="run",
        owner_id=str(task.id),
        sandbox=task.sandbox,
    )
    try:
        command = agent_command_service.create_command(
            session,
            device_id=workspace.device_id,
            command_type="RUN_EXECUTE",
            aggregate_type="task",
            aggregate_id=str(task.id),
            idempotency_key=payload.client_request_id or f"run:{task.id}",
            workspace_id=workspace.id,
            payload={
                "task_id": task.id,
                "workspace_id": workspace.id,
                "workspace_key": workspace.workspace_key,
                "prompt": task.prompt,
                "timeout_seconds": task.timeout_seconds,
                "task_type": task.task_type.value,
                "model": task.model,
                "reasoning_effort": task.reasoning_effort,
                "sandbox": task.sandbox,
                "require_clean_worktree": workspace.require_clean_worktree,
            },
        )
    except Exception:
        workspace_lock_service.release_workspace_lock(
            session,
            owner_type="run",
            owner_id=str(task.id),
        )
        raise
    task.command_id = command.id
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def list_tasks(
    session: Session,
    *,
    project_id: int | None = None,
    workspace_id: int | None = None,
    task_status: TaskStatus | None = None,
    limit: int = 50,
) -> list[Task]:
    statement = select(Task)
    if project_id is not None:
        statement = statement.where(Task.project_id == project_id)
    if workspace_id is not None:
        statement = statement.where(Task.workspace_id == workspace_id)
    if task_status is not None:
        statement = statement.where(Task.status == task_status)
    statement = statement.order_by(Task.id.desc()).limit(limit)
    return list(session.exec(statement).all())


def get_task_or_404(session: Session, task_id: int) -> Task:
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="task not found",
        )
    return task


def rerun_task(session: Session, task_id: int) -> Task:
    original = get_task_or_404(session, task_id)
    payload = TaskCreate(
        project_id=original.project_id,
        prompt=original.prompt,
        timeout_seconds=original.timeout_seconds,
        task_type=original.task_type,
        assigned_runner_id=original.assigned_runner_id,
        model=original.model,
        reasoning_effort=original.reasoning_effort,
        sandbox=original.sandbox,
        workspace_id=original.workspace_id,
        client_request_id=None,
    )
    if original.workspace_id is not None:
        run_payload = RunCreate(
            project_id=payload.project_id,
            prompt=payload.prompt,
            timeout_seconds=payload.timeout_seconds,
            task_type=payload.task_type,
            assigned_runner_id=payload.assigned_runner_id,
            workspace_id=original.workspace_id,
            model=payload.model,
            reasoning_effort=payload.reasoning_effort,
            sandbox=payload.sandbox,
        )
        return create_run(session, run_payload)
    return create_task(session, payload)


def request_cancel(session: Session, task_id: int) -> Task:
    task = get_task_or_404(session, task_id)
    if task.status == TaskStatus.CANCELLED and task.cancel_requested:
        return task
    if task.status in {TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.CANCELLED}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="task is already finished",
        )
    task.cancel_requested = True
    task.updated_at = utc_now()
    if task.command_id:
        command = agent_command_service.request_cancel_command(
            session,
            command_id=task.command_id,
        )
        if command.status == AgentCommandStatus.CANCELLED:
            task.status = TaskStatus.CANCELLED
            task.finished_at = utc_now()
            task.lease_expires_at = None
            task.error_message = "task cancelled"
            workspace_lock_service.release_workspace_lock(
                session,
                owner_type="run",
                owner_id=str(task.id),
            )
    if task.status == TaskStatus.PENDING:
        task.status = TaskStatus.CANCELLED
        task.finished_at = utc_now()
        workspace_lock_service.release_workspace_lock(
            session,
            owner_type="run",
            owner_id=str(task.id),
        )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def to_task_read(task: Task, session: Session | None = None):
    from backend.schemas import TaskRead

    if task.id is None:
        raise ValueError("task id is required")
    device = None
    workspace = None
    if session is not None:
        device = session.get(Device, task.device_id) if task.device_id else None
        workspace = session.get(Workspace, task.workspace_id) if task.workspace_id else None
    return TaskRead(
        id=task.id,
        project_id=task.project_id,
        prompt=task.prompt,
        task_type=task.task_type,
        status=task.status,
        timeout_seconds=task.timeout_seconds,
        model=task.model,
        reasoning_effort=task.reasoning_effort,
        sandbox=task.sandbox,
        exit_code=task.exit_code,
        error_message=task.error_message,
        cancel_requested=task.cancel_requested,
        assigned_runner_id=task.assigned_runner_id,
        runner_id=task.runner_id,
        runner_pid=task.runner_pid,
        lease_expires_at=task.lease_expires_at,
        device_id=task.device_id,
        device_display_name=device.display_name if device else None,
        device_status=device.status if device else None,
        workspace_id=task.workspace_id,
        workspace_name=workspace.name if workspace else None,
        workspace_path_label=workspace.path_label if workspace else None,
        command_id=task.command_id,
        client_request_id=task.client_request_id,
        log_url=f"/tasks/{task.id}/log",
        result_url=f"/tasks/{task.id}/result",
        diff_url=f"/tasks/{task.id}/diff",
        created_at=task.created_at,
        updated_at=task.updated_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
    )


def to_artifacts_read(task: Task):
    from backend.schemas import TaskArtifactsRead

    if task.id is None:
        raise ValueError("task id is required")
    return TaskArtifactsRead(
        log_url=f"/tasks/{task.id}/log",
        result_url=f"/tasks/{task.id}/result",
        diff_url=f"/tasks/{task.id}/diff",
        git_status_url=f"/tasks/{task.id}/artifacts/git-status",
        report_url=f"/tasks/{task.id}/artifacts/report",
    )


def list_task_templates():
    from backend.schemas import TaskTemplateRead

    return [
        TaskTemplateRead(task_type=task_type, title=title, template=template)
        for task_type, (title, template) in TASK_TEMPLATES.items()
    ]
