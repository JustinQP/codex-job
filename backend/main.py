from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Iterable
import traceback

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from backend.db import engine, init_db
from backend.dependencies import require_api_token
from backend.routers import app_threads, projects, runners, tasks, ui
from backend.routers.app_threads import _sse_event
from backend.routers.tasks import _read_task_artifact
from backend.routers.ui import frontend_build_missing_page
from backend import db
from backend.services import app_thread_service
from backend.services.app_server_bridge_client import get_default_client


ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST_DIR = ROOT_DIR / "frontend" / "dist"
FRONTEND_INDEX_HTML = FRONTEND_DIST_DIR / "index.html"
FRONTEND_ASSETS_DIR = FRONTEND_DIST_DIR / "assets"

ui.FRONTEND_INDEX_HTML = FRONTEND_INDEX_HTML
JOBS_DIR = db.JOBS_DIR


def sync_router_settings() -> None:
    ui.FRONTEND_INDEX_HTML = FRONTEND_INDEX_HTML
    db.JOBS_DIR = JOBS_DIR


@asynccontextmanager
async def lifespan(_: FastAPI) -> Iterable[None]:
    init_db()
    try:
        with Session(engine) as session:
            app_thread_service.recover_stale_app_turns(session)
    except Exception:
        traceback.print_exc()
    yield


app = FastAPI(
    title="Codex Remote Runner MVP",
    version="1.0.0",
    lifespan=lifespan,
)
app.mount(
    "/assets",
    StaticFiles(directory=FRONTEND_ASSETS_DIR, check_dir=False),
    name="frontend_assets",
)

app.include_router(ui.router)
app.include_router(app_threads.router)
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(runners.router)
sync_router_settings()
