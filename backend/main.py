from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Iterable
import traceback

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from backend.db import engine, get_session, init_db
from backend.routers import agent, app_threads, devices, projects, runs, ui, workspaces
from backend.routers.ui import frontend_build_missing_page
from backend import db
from backend.services import app_thread_service


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
async def lifespan(app_instance: FastAPI) -> Iterable[None]:
    if get_session not in app_instance.dependency_overrides:
        init_db()
        try:
            with Session(engine) as session:
                app_thread_service.recover_stale_app_turns(session)
        except Exception:
            traceback.print_exc()
    yield


app = FastAPI(
    title="Codex Job Control Plane",
    version="2.0.0",
    lifespan=lifespan,
)
app.mount(
    "/assets",
    StaticFiles(directory=FRONTEND_ASSETS_DIR, check_dir=False),
    name="frontend_assets",
)

app.include_router(ui.router)
app.include_router(agent.router)
app.include_router(app_threads.router)
app.include_router(devices.router)
app.include_router(projects.router)
app.include_router(workspaces.router)
app.include_router(runs.router)
sync_router_settings()
