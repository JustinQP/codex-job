from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path
from urllib.parse import parse_qs
from typing import Iterable

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from sqlmodel import Session

from backend.db import JOBS_DIR, get_session, init_db
from backend.models import TaskStatus, TaskType
from backend.schemas import (
    AppThreadCreate,
    AppThreadEventsRead,
    AppThreadFinalRead,
    AppThreadRead,
    AppThreadUpdate,
    AppTurnCreate,
    AppTurnRead,
    ProjectCreate,
    ProjectRead,
    RunnerHeartbeat,
    RunnerRead,
    RunnerRegister,
    RunnerTaskArtifactsUpload,
    RunnerTaskCancelState,
    RunnerTaskClaimRequest,
    RunnerTaskClaimResponse,
    RunnerTaskFinishRequest,
    RunnerTaskLogUpload,
    TaskArtifactsRead,
    TaskCreate,
    TaskRead,
    TaskTemplateRead,
)
from backend.services import app_thread_service, project_service, runner_service, task_service
from backend.services.app_server_bridge_client import AppServerBridgeError, get_default_client
from backend import mobile, ui


@asynccontextmanager
async def lifespan(_: FastAPI) -> Iterable[None]:
    init_db()
    yield


app = FastAPI(
    title="Codex Remote Runner MVP",
    version="0.8.1",
    lifespan=lifespan,
)


def require_api_token(x_api_token: str | None = Header(default=None)) -> None:
    expected = os.environ.get("API_TOKEN")
    if not expected:
        return
    if x_api_token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid API token",
        )


@app.get("/", include_in_schema=False)
def index(
    project_id: int | None = None,
    status: TaskStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
) -> HTMLResponse:
    projects = project_service.list_projects(session)
    tasks = task_service.list_tasks(
        session,
        project_id=project_id,
        task_status=status,
        limit=limit,
    )
    return HTMLResponse(
        ui.dashboard(
            projects=projects,
            tasks=tasks,
            selected_project_id=project_id,
            selected_status=status,
            limit=limit,
        )
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/app-server-bridge/health")
def app_server_bridge_health(_: None = Depends(require_api_token)):
    try:
        return get_default_client().get_health()
    except AppServerBridgeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unavailable",
                "error": exc.message,
                "code": exc.code,
                "step": exc.step,
            },
        ) from exc


@app.get("/mobile", include_in_schema=False)
def mobile_console() -> HTMLResponse:
    return HTMLResponse(mobile.mobile_console())


@app.get("/app-threads", response_model=list[AppThreadRead])
def list_app_threads(
    project_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return [
        app_thread_service.to_app_thread_read(session, app_thread)
        for app_thread in app_thread_service.list_app_threads(
            session,
            project_id=project_id,
            limit=limit,
        )
    ]


@app.post("/app-threads", response_model=AppThreadRead)
def create_app_thread(
    payload: AppThreadCreate,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    app_thread = app_thread_service.create_app_thread(session, payload)
    return app_thread_service.to_app_thread_read(session, app_thread)


@app.get("/app-threads/{app_thread_id}", response_model=AppThreadRead)
def get_app_thread(
    app_thread_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    app_thread = app_thread_service.get_app_thread_or_404(session, app_thread_id)
    return app_thread_service.to_app_thread_read(session, app_thread)


@app.patch("/app-threads/{app_thread_id}", response_model=AppThreadRead)
def rename_app_thread(
    app_thread_id: int,
    payload: AppThreadUpdate,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    app_thread = app_thread_service.rename_app_thread(session, app_thread_id, payload)
    return app_thread_service.to_app_thread_read(session, app_thread)


@app.delete("/app-threads/{app_thread_id}", response_model=AppThreadRead)
def close_app_thread(
    app_thread_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    app_thread = app_thread_service.close_app_thread(session, app_thread_id)
    return app_thread_service.to_app_thread_read(session, app_thread)


@app.post("/app-threads/{app_thread_id}/turns", response_model=AppTurnRead)
def send_app_turn(
    app_thread_id: int,
    payload: AppTurnCreate,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    app_turn = app_thread_service.send_app_turn(session, app_thread_id, payload)
    return app_thread_service.to_app_turn_read(app_turn)


@app.get("/app-threads/{app_thread_id}/turns", response_model=list[AppTurnRead])
def list_app_turns(
    app_thread_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return [
        app_thread_service.to_app_turn_read(app_turn)
        for app_turn in app_thread_service.list_app_turns(session, app_thread_id)
    ]


@app.get("/app-threads/{app_thread_id}/final", response_model=AppThreadFinalRead)
def get_app_thread_final(
    app_thread_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return app_thread_service.get_app_thread_final(session, app_thread_id)


@app.get("/app-threads/{app_thread_id}/events", response_model=AppThreadEventsRead)
def get_app_thread_events(
    app_thread_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return app_thread_service.get_app_thread_events(session, app_thread_id)


@app.post("/projects", response_model=ProjectRead)
def create_project(
    payload: ProjectCreate,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    project = project_service.create_project(session, payload)
    return project_service.to_project_read(project)


@app.get("/projects", response_model=list[ProjectRead])
def list_projects(
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return [
        project_service.to_project_read(project)
        for project in project_service.list_projects(session)
    ]


@app.post("/tasks", response_model=TaskRead)
def create_task(
    payload: TaskCreate,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    task = task_service.create_task(session, payload)
    return task_service.to_task_read(task)


@app.get("/tasks", response_model=list[TaskRead])
def list_tasks(
    project_id: int | None = None,
    status: TaskStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    tasks = task_service.list_tasks(
        session,
        project_id=project_id,
        task_status=status,
        limit=limit,
    )
    return [task_service.to_task_read(task) for task in tasks]


@app.get("/tasks/{task_id}", response_model=TaskRead)
def get_task(
    task_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    task = task_service.get_task_or_404(session, task_id)
    return task_service.to_task_read(task)


@app.post("/tasks/{task_id}/rerun", response_model=TaskRead)
def rerun_task(
    task_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    task = task_service.rerun_task(session, task_id)
    return task_service.to_task_read(task)


@app.post("/tasks/{task_id}/cancel", response_model=TaskRead)
def cancel_task(
    task_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    task = task_service.request_cancel(session, task_id)
    return task_service.to_task_read(task)


@app.get("/tasks/{task_id}/artifacts", response_model=TaskArtifactsRead)
def get_task_artifacts(
    task_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    task = task_service.get_task_or_404(session, task_id)
    return task_service.to_artifacts_read(task)


@app.get("/task-templates", response_model=list[TaskTemplateRead])
def list_task_templates(_: None = Depends(require_api_token)):
    return task_service.list_task_templates()


@app.post("/runners/register", response_model=RunnerRead)
def register_runner(
    payload: RunnerRegister,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return runner_service.register_runner(session, payload)


@app.post("/runner/register", response_model=RunnerRead)
def runner_register(
    payload: RunnerRegister,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return runner_service.register_runner(session, payload)


@app.post("/runners/heartbeat", response_model=RunnerRead)
def runner_heartbeat(
    payload: RunnerHeartbeat,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return runner_service.heartbeat(session, payload)


@app.post("/runner/heartbeat", response_model=RunnerRead)
def runner_http_heartbeat(
    payload: RunnerHeartbeat,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return runner_service.heartbeat(session, payload)


@app.get("/runners", response_model=list[RunnerRead])
def list_runners(
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return runner_service.list_runners(session)


@app.post("/runner/tasks/claim", response_model=RunnerTaskClaimResponse | None)
def runner_claim_task(
    payload: RunnerTaskClaimRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return runner_service.claim_task(session, payload.runner_id)


@app.post("/runner/tasks/{task_id}/log")
def runner_upload_task_log(
    task_id: int,
    payload: RunnerTaskLogUpload,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return runner_service.upload_task_log(session, task_id, payload)


@app.post("/runner/tasks/{task_id}/artifacts")
def runner_upload_task_artifacts(
    task_id: int,
    payload: RunnerTaskArtifactsUpload,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return runner_service.upload_task_artifacts(session, task_id, payload)


@app.post("/runner/tasks/{task_id}/finish", response_model=TaskRead)
def runner_finish_task(
    task_id: int,
    payload: RunnerTaskFinishRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    task = runner_service.finish_task(session, task_id, payload)
    return task_service.to_task_read(task)


@app.get("/runner/tasks/{task_id}/cancel-state", response_model=RunnerTaskCancelState)
def runner_get_cancel_state(
    task_id: int,
    runner_id: str,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    task = runner_service.get_cancel_state(session, task_id, runner_id)
    return RunnerTaskCancelState(
        task_id=task.id,
        cancel_requested=task.cancel_requested,
        status=task.status,
    )


@app.get("/ui/tasks/{task_id}", include_in_schema=False)
def task_detail(
    task_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    task = task_service.get_task_or_404(session, task_id)
    return HTMLResponse(ui.task_detail(task))


@app.post("/ui/tasks", include_in_schema=False)
async def create_task_from_form(
    request: Request,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    form = await _read_urlencoded_form(request)
    payload = TaskCreate(
        project_id=int(_required_form_value(form, "project_id")),
        prompt=_required_form_value(form, "prompt"),
        timeout_seconds=int(_required_form_value(form, "timeout_seconds")),
        task_type=TaskType(_optional_form_value(form, "task_type") or TaskType.IMPLEMENT),
    )
    task = task_service.create_task(session, payload)
    return RedirectResponse(
        url=f"/ui/tasks/{task.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.post("/ui/tasks/{task_id}/rerun", include_in_schema=False)
def rerun_task_from_form(
    task_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    task = task_service.rerun_task(session, task_id)
    return RedirectResponse(
        url=f"/ui/tasks/{task.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.post("/ui/tasks/{task_id}/cancel", include_in_schema=False)
def cancel_task_from_form(
    task_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    task = task_service.request_cancel(session, task_id)
    return RedirectResponse(
        url=f"/ui/tasks/{task.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


async def _read_urlencoded_form(request: Request) -> dict[str, list[str]]:
    body = await request.body()
    return parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)


def _required_form_value(form: dict[str, list[str]], name: str) -> str:
    values = form.get(name)
    if not values or not values[0].strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"missing form field: {name}",
        )
    return values[0].strip()


def _optional_form_value(form: dict[str, list[str]], name: str) -> str | None:
    values = form.get(name)
    if not values or not values[0].strip():
        return None
    return values[0].strip()


def _read_task_artifact(task_id: int, attr_name: str, session: Session) -> str:
    task = task_service.get_task_or_404(session, task_id)
    raw_path = getattr(task, attr_name)
    if not raw_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="artifact path is not available",
        )

    path = Path(raw_path).resolve()
    jobs_root = JOBS_DIR.resolve()
    try:
        path.relative_to(jobs_root)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="artifact path is outside jobs directory",
        ) from exc

    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="artifact file not found",
        )
    return path.read_text(encoding="utf-8", errors="replace")


@app.get("/tasks/{task_id}/log", response_class=PlainTextResponse)
def get_task_log(
    task_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return _read_task_artifact(task_id, "log_file", session)


@app.get("/tasks/{task_id}/result", response_class=PlainTextResponse)
def get_task_result(
    task_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return _read_task_artifact(task_id, "result_file", session)


@app.get("/tasks/{task_id}/diff", response_class=PlainTextResponse)
def get_task_diff(
    task_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    return _read_task_artifact(task_id, "diff_file", session)


@app.get("/tasks/{task_id}/artifacts/git-status", response_class=PlainTextResponse)
def get_task_git_status(
    task_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    task = task_service.get_task_or_404(session, task_id)
    if not task.diff_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="artifact path is not available",
        )
    git_status_path = Path(task.diff_file).resolve().parent / "git-status.txt"
    return _read_artifact_path(git_status_path)


@app.get("/tasks/{task_id}/artifacts/report", response_class=PlainTextResponse)
def get_task_report(
    task_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    task = task_service.get_task_or_404(session, task_id)
    if not task.diff_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="artifact path is not available",
        )
    report_path = Path(task.diff_file).resolve().parent / "task-report.md"
    return _read_artifact_path(report_path)


def _read_artifact_path(path: Path) -> str:
    path = path.resolve()
    jobs_root = JOBS_DIR.resolve()
    try:
        path.relative_to(jobs_root)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="artifact path is outside jobs directory",
        ) from exc
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="artifact file not found",
        )
    return path.read_text(encoding="utf-8", errors="replace")
