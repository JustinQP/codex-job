from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Iterable

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlmodel import Session

from backend.db import JOBS_DIR, get_session, init_db
from backend.schemas import ProjectCreate, ProjectRead, TaskCreate, TaskRead
from backend.services import project_service, task_service


@asynccontextmanager
async def lifespan(_: FastAPI) -> Iterable[None]:
    init_db()
    yield


app = FastAPI(
    title="Codex Remote Runner MVP",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/", include_in_schema=False)
def index() -> HTMLResponse:
    return HTMLResponse(
        """
        <!doctype html>
        <html>
          <head><meta charset="utf-8"><title>Codex Remote Runner</title></head>
          <body>
            <h1>Codex Remote Runner MVP</h1>
            <p>Use <a href="/docs">/docs</a> for the API documentation.</p>
          </body>
        </html>
        """
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/projects", response_model=ProjectRead)
def create_project(
    payload: ProjectCreate,
    session: Session = Depends(get_session),
):
    return project_service.create_project(session, payload)


@app.get("/projects", response_model=list[ProjectRead])
def list_projects(session: Session = Depends(get_session)):
    return project_service.list_projects(session)


@app.post("/tasks", response_model=TaskRead)
def create_task(
    payload: TaskCreate,
    session: Session = Depends(get_session),
):
    return task_service.create_task(session, payload)


@app.get("/tasks", response_model=list[TaskRead])
def list_tasks(session: Session = Depends(get_session)):
    return task_service.list_tasks(session)


@app.get("/tasks/{task_id}", response_model=TaskRead)
def get_task(task_id: int, session: Session = Depends(get_session)):
    return task_service.get_task_or_404(session, task_id)


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
def get_task_log(task_id: int, session: Session = Depends(get_session)):
    return _read_task_artifact(task_id, "log_file", session)


@app.get("/tasks/{task_id}/result", response_class=PlainTextResponse)
def get_task_result(task_id: int, session: Session = Depends(get_session)):
    return _read_task_artifact(task_id, "result_file", session)


@app.get("/tasks/{task_id}/diff", response_class=PlainTextResponse)
def get_task_diff(task_id: int, session: Session = Depends(get_session)):
    return _read_task_artifact(task_id, "diff_file", session)
