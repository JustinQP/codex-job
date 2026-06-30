from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, status
from sqlmodel import Session, select

from backend.db import JOBS_DIR
from backend.models import AgentCommand, AgentCommandStatus, Device, Project, Run, RunStatus, RunType, Workspace, utc_now
from backend.schemas import RunCreate
from backend.services import audit_service, agent_command_service, device_service, project_service, workspace_lock_service


RUN_TEMPLATES: dict[RunType, tuple[str, str]] = {
    RunType.PLAN: (
        "生成计划",
        "请基于以下目标生成一个可执行开发计划，包含范围、步骤、验证方式和风险：\n\n{goal}",
    ),
    RunType.IMPLEMENT: (
        "执行开发",
        "请基于以下目标进行最小必要实现，并完成自检：\n\n{goal}",
    ),
    RunType.REVIEW: (
        "代码审查",
        "请对当前项目中与以下目标相关的改动进行代码审查，优先指出 bug、风险和缺失测试：\n\n{goal}",
    ),
    RunType.TEST_FIX: (
        "测试修复",
        "请运行或分析相关测试，修复以下测试/验证问题，并说明结果：\n\n{goal}",
    ),
    RunType.DOCS: (
        "文档更新",
        "请根据以下目标更新必要文档，保持内容准确、简洁、可维护：\n\n{goal}",
    ),
    RunType.COMMIT: (
        "提交准备",
        "请检查当前改动，完成必要自检，并准备清晰的提交说明。不要自动 push：\n\n{goal}",
    ),
}

DEFAULT_SANDBOX = "workspace-write"


def _artifact_paths(run_id: int) -> tuple[Path, Path, Path]:
    job_dir = JOBS_DIR / str(run_id)
    return job_dir / "run.log", job_dir / "result.md", job_dir / "diff.patch"


def _assign_artifact_paths(run: Run) -> None:
    if run.id is None:
        raise ValueError("run id is required before assigning artifact paths")

    log_file, result_file, diff_file = _artifact_paths(run.id)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    run.log_file = str(log_file)
    run.result_file = str(result_file)
    run.diff_file = str(diff_file)
    run.updated_at = utc_now()


def create_run(session: Session, payload: RunCreate) -> Run:
    workspace = session.get(Workspace, payload.workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="workspace not found")
    if not workspace.enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="workspace is disabled")
    device_service.ensure_online_device(session, workspace.device_id)
    project = session.get(Project, payload.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    if not project.enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="project is disabled")
    project_service.ensure_project_workspace(session, project, workspace.id)
    requested_sandbox = payload.sandbox or project.default_sandbox or workspace.default_sandbox or DEFAULT_SANDBOX
    workspace_lock_service.ensure_workspace_available(
        session,
        workspace_id=workspace.id,
        sandbox=requested_sandbox,
    )

    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="prompt cannot be empty")
    run = _create_run_record(
        session,
        payload=payload,
        project=project,
        prompt=prompt,
        created_at=utc_now(),
        workspace_id=workspace.id,
        device_id=workspace.device_id,
    )
    if run.id is None:
        raise ValueError("run id is required")
    workspace_lock_service.acquire_workspace_lock(
        session,
        workspace_id=workspace.id,
        owner_type="run",
        owner_id=str(run.id),
        sandbox=run.sandbox,
    )
    try:
        command = agent_command_service.create_command(
            session,
            device_id=workspace.device_id,
            command_type="RUN_EXECUTE",
            aggregate_type="run",
            aggregate_id=str(run.id),
            idempotency_key=payload.client_request_id or f"run:{run.id}",
            workspace_id=workspace.id,
            payload={
                "run_id": run.id,
                "workspace_id": workspace.id,
                "workspace_key": workspace.workspace_key,
                "prompt": run.prompt,
                "timeout_seconds": run.timeout_seconds,
                "run_type": run.run_type.value,
                "model": run.model,
                "reasoning_effort": run.reasoning_effort,
                "sandbox": run.sandbox,
                "require_clean_worktree": workspace.require_clean_worktree,
            },
            commit=False,
        )
    except Exception:
        session.rollback()
        raise
    run.command_id = command.id
    audit_service.record_event(
        session,
        action="run.created",
        entity_type="run",
        entity_id=run.id,
        payload={"command_id": command.id, "workspace_id": workspace.id},
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def _create_run_record(
    session: Session,
    *,
    payload: RunCreate,
    project: Project,
    prompt: str,
    created_at: datetime,
    workspace_id: int,
    device_id: str,
) -> Run:
    run = Run(
        project_id=payload.project_id,
        prompt=prompt,
        run_type=payload.run_type,
        timeout_seconds=payload.timeout_seconds,
        model=payload.model or project.default_model,
        reasoning_effort=payload.reasoning_effort or project.default_reasoning_effort,
        sandbox=payload.sandbox or project.default_sandbox or DEFAULT_SANDBOX,
        status=RunStatus.PENDING,
        device_id=device_id,
        workspace_id=workspace_id,
        client_request_id=payload.client_request_id,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(run)
    session.flush()

    _assign_artifact_paths(run)
    session.add(run)
    session.flush()
    session.refresh(run)
    return run


def list_runs(
    session: Session,
    *,
    project_id: int | None = None,
    workspace_id: int | None = None,
    run_status: RunStatus | None = None,
    limit: int = 50,
) -> list[Run]:
    statement = select(Run)
    if project_id is not None:
        statement = statement.where(Run.project_id == project_id)
    if workspace_id is not None:
        statement = statement.where(Run.workspace_id == workspace_id)
    if run_status is not None:
        statement = statement.where(Run.status == run_status)
    statement = statement.order_by(Run.id.desc()).limit(limit)
    return list(session.exec(statement).all())


def get_run_or_404(session: Session, run_id: int) -> Run:
    run = session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
    return run


def rerun_run(session: Session, run_id: int) -> Run:
    original = get_run_or_404(session, run_id)
    if original.workspace_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="run is not bound to a workspace")
    payload = RunCreate(
        project_id=original.project_id,
        prompt=original.prompt,
        timeout_seconds=original.timeout_seconds,
        run_type=original.run_type,
        workspace_id=original.workspace_id,
        model=original.model,
        reasoning_effort=original.reasoning_effort,
        sandbox=original.sandbox,
    )
    return create_run(session, payload)


def request_cancel(session: Session, run_id: int) -> Run:
    run = get_run_or_404(session, run_id)
    if run.status == RunStatus.CANCELLED and run.cancel_requested:
        return run
    if run.status in {RunStatus.SUCCESS, RunStatus.FAILED, RunStatus.CANCELLED}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="run is already finished")
    run.cancel_requested = True
    run.updated_at = utc_now()
    if run.command_id:
        command = agent_command_service.request_cancel_command(session, command_id=run.command_id)
        if command.status == AgentCommandStatus.CANCELLED:
            run.status = RunStatus.CANCELLED
            run.finished_at = utc_now()
            run.lease_expires_at = None
            run.error_message = "run cancelled"
            workspace_lock_service.release_workspace_lock(session, owner_type="run", owner_id=str(run.id))
    if run.status == RunStatus.PENDING and not run.command_id:
        run.status = RunStatus.CANCELLED
        run.finished_at = utc_now()
        workspace_lock_service.release_workspace_lock(session, owner_type="run", owner_id=str(run.id))
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def mark_run_running(session: Session, *, command_id: str) -> Run | None:
    command = session.get(AgentCommand, command_id)
    if command is None or command.aggregate_type != "run":
        return None
    try:
        run_id = int(command.aggregate_id or "0")
    except ValueError:
        return None
    run = session.get(Run, run_id)
    if run is None or run.status != RunStatus.PENDING:
        return run
    now = utc_now()
    run.status = RunStatus.RUNNING
    run.started_at = now
    run.lease_expires_at = command.lease_expires_at
    run.updated_at = now
    session.add(run)
    audit_service.record_event(
        session,
        action="run.running",
        entity_type="run",
        entity_id=run.id,
        payload={"command_id": command.id},
    )
    session.commit()
    session.refresh(run)
    return run


def renew_run_lease_from_command(session: Session, *, command_id: str) -> Run | None:
    command = session.get(AgentCommand, command_id)
    if command is None or command.aggregate_type != "run":
        return None
    try:
        run_id = int(command.aggregate_id or "0")
    except ValueError:
        return None
    run = session.get(Run, run_id)
    if run is None or run.status not in {RunStatus.PENDING, RunStatus.RUNNING}:
        return run
    run.lease_expires_at = command.lease_expires_at
    run.updated_at = utc_now()
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def complete_run_command(session: Session, *, command_id: str) -> Run | None:
    command = session.get(AgentCommand, command_id)
    if command is None or command.aggregate_type != "run":
        return None
    try:
        run_id = int(command.aggregate_id or "0")
    except ValueError:
        return None
    run = session.get(Run, run_id)
    if run is None:
        return None
    now = utc_now()
    if command.status == AgentCommandStatus.SUCCESS:
        run.status = RunStatus.SUCCESS
        run.error_message = None
        run.exit_code = 0
    elif command.status == AgentCommandStatus.CANCELLED:
        run.status = RunStatus.CANCELLED
        run.error_message = command.last_error or "run cancelled"
        run.exit_code = -1
    elif command.status in {AgentCommandStatus.FAILED, AgentCommandStatus.EXPIRED}:
        run.status = RunStatus.FAILED
        run.error_message = command.last_error or f"RUN_EXECUTE ended with {command.status}"
        run.exit_code = -1
    else:
        return run
    if run.started_at is None:
        run.started_at = command.claimed_at or run.created_at
    run.finished_at = now
    run.lease_expires_at = None
    run.updated_at = now
    session.add(run)
    audit_service.record_event(
        session,
        action="run.completed",
        entity_type="run",
        entity_id=run.id,
        payload={"command_id": command.id, "status": run.status.value},
    )
    session.commit()
    session.refresh(run)
    return run


def to_run_read(run: Run, session: Session | None = None):
    from backend.schemas import RunRead

    if run.id is None:
        raise ValueError("run id is required")
    device = None
    workspace = None
    if session is not None:
        device = session.get(Device, run.device_id) if run.device_id else None
        workspace = session.get(Workspace, run.workspace_id) if run.workspace_id else None
    return RunRead(
        id=run.id,
        project_id=run.project_id,
        prompt=run.prompt,
        run_type=run.run_type,
        status=run.status,
        timeout_seconds=run.timeout_seconds,
        model=run.model,
        reasoning_effort=run.reasoning_effort,
        sandbox=run.sandbox,
        exit_code=run.exit_code,
        error_message=run.error_message,
        cancel_requested=run.cancel_requested,
        lease_expires_at=run.lease_expires_at,
        device_id=run.device_id,
        device_display_name=device.display_name if device else None,
        device_status=device.status if device else None,
        workspace_id=run.workspace_id,
        workspace_name=workspace.name if workspace else None,
        workspace_path_label=workspace.path_label if workspace else None,
        command_id=run.command_id,
        client_request_id=run.client_request_id,
        log_url=f"/runs/{run.id}/log",
        result_url=f"/runs/{run.id}/result",
        diff_url=f"/runs/{run.id}/diff",
        created_at=run.created_at,
        updated_at=run.updated_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


def to_artifacts_read(run: Run):
    from backend.schemas import RunArtifactsRead

    if run.id is None:
        raise ValueError("run id is required")
    return RunArtifactsRead(
        log_url=f"/runs/{run.id}/log",
        result_url=f"/runs/{run.id}/result",
        diff_url=f"/runs/{run.id}/diff",
        git_status_url=f"/runs/{run.id}/artifacts/git-status",
        report_url=f"/runs/{run.id}/artifacts/report",
    )


def list_run_templates():
    from backend.schemas import RunTemplateRead

    return [
        RunTemplateRead(run_type=run_type, title=title, template=template)
        for run_type, (title, template) in RUN_TEMPLATES.items()
    ]
