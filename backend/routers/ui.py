from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlmodel import Session

from backend import ui
from backend.config import get_settings
from backend.db import get_session
from backend.dependencies import require_api_token
from backend.models import TaskStatus, TaskType
from backend.schemas import TaskCreate
from backend.services import app_thread_service, project_service, task_service
from backend.services.app_server_bridge_client import AppServerBridgeError, get_default_client


FRONTEND_INDEX_HTML = Path("missing-frontend-dist-index.html")

router = APIRouter()


def frontend_build_missing_page() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Frontend build not found</title>
  <style>
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      background: #f3f5f8;
      color: #172033;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    main {
      width: min(92vw, 680px);
      padding: 24px;
      border: 1px solid #d8dee8;
      border-radius: 14px;
      background: #fff;
      box-shadow: 0 10px 28px rgb(15 23 42 / 8%);
    }
    h1 { margin-top: 0; font-size: 24px; }
    p { color: #526070; line-height: 1.55; }
    pre {
      overflow-x: auto;
      padding: 12px;
      border-radius: 10px;
      background: #0f172a;
      color: #e5e7eb;
    }
  </style>
</head>
<body>
  <main>
    <h1>Frontend build not found.</h1>
    <p>The /mobile page is now served from frontend/dist. Build the frontend first:</p>
    <pre>cd frontend
npm install
npm run build</pre>
  </main>
</body>
</html>"""


@router.get("/", include_in_schema=False)
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


@router.get("/health")
def health() -> dict[str, str | bool]:
    settings = get_settings()
    return {
        "status": "ok",
        "agent_command_mode": settings.agent_command_mode,
        "execution_mode": settings.execution_mode,
    }


@router.get("/app-server-bridge/health")
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


@router.get("/mobile", include_in_schema=False)
def mobile_console():
    if FRONTEND_INDEX_HTML.exists():
        return FileResponse(FRONTEND_INDEX_HTML)
    return HTMLResponse(frontend_build_missing_page())


@router.get("/ui/tasks/{task_id}", include_in_schema=False)
def task_detail(
    task_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_api_token),
):
    task = task_service.get_task_or_404(session, task_id)
    return HTMLResponse(ui.task_detail(task))


@router.post("/ui/tasks", include_in_schema=False)
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


@router.post("/ui/tasks/{task_id}/rerun", include_in_schema=False)
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


@router.post("/ui/tasks/{task_id}/cancel", include_in_schema=False)
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
