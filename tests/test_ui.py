from __future__ import annotations

from collections.abc import Generator
import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from backend import main as backend_main
import backend.routers.ui as ui_router
from backend import mobile, ui
from backend.db import get_session
from backend.main import app
from backend.models import Project, Task, TaskStatus, utc_now


def make_client() -> Generator[tuple[TestClient, Session], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    session = Session(engine)

    def override_get_session() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(app) as client:
            yield client, session
    finally:
        app.dependency_overrides.clear()
        session.close()


def add_project(session: Session) -> Project:
    project = Project(
        name="demo",
        path="E:\\demo",
        enabled=True,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def add_task(session: Session, project_id: int) -> Task:
    task = Task(
        project_id=project_id,
        prompt="old prompt",
        status=TaskStatus.FAILED,
        timeout_seconds=120,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def test_dashboard_renders_projects_and_tasks() -> None:
    for client, session in make_client():
        project = add_project(session)
        task = add_task(session, project.id)

        response = client.get("/")

        assert response.status_code == 200
        assert "创建任务" in response.text
        assert "项目列表" in response.text
        assert f"/ui/tasks/{task.id}" in response.text


def test_mobile_console_returns_build_missing_page_when_dist_absent(monkeypatch) -> None:
    monkeypatch.setattr(
        ui_router,
        "FRONTEND_INDEX_HTML",
        Path("missing-frontend-dist-index.html"),
    )
    for client, session in make_client():
        del session
        response = client.get("/mobile")

        assert response.status_code == 200
        assert "Frontend build not found." in response.text
        assert "cd frontend" in response.text
        assert "npm install" in response.text
        assert "npm run build" in response.text


def test_mobile_console_returns_frontend_dist_index_when_present(
    monkeypatch,
    tmp_path,
) -> None:
    index_html = tmp_path / "frontend" / "dist" / "index.html"
    index_html.parent.mkdir(parents=True)
    index_html.write_text(
        '<!doctype html><html><body><div id="root">Codex Mobile Console</div></body></html>',
        encoding="utf-8",
    )
    monkeypatch.setattr(ui_router, "FRONTEND_INDEX_HTML", index_html)

    for client, session in make_client():
        del session
        response = client.get("/mobile")

        assert response.status_code == 200
        assert "Codex Mobile Console" in response.text
        assert "Frontend build not found." not in response.text


def test_mobile_console_assets_mount_is_configured() -> None:
    routes = {getattr(route, "path", ""): route for route in backend_main.app.routes}

    assert "/assets" in routes
    assert backend_main.FRONTEND_ASSETS_DIR == backend_main.FRONTEND_DIST_DIR / "assets"


def test_frontend_v17_design_system_and_shell_exist() -> None:
    root = Path("frontend/src")
    assert (root / "styles/tokens.css").exists()
    assert (root / "styles/base.css").exists()
    assert (root / "styles/components.css").exists()
    assert (root / "styles/session.css").exists()
    assert (root / "styles/tasks.css").exists()
    assert (root / "styles/app.css").exists()

    tokens = (root / "styles/tokens.css").read_text(encoding="utf-8")
    assert "--space-1" in tokens
    assert "--space-2" in tokens
    assert "--radius-sm" in tokens
    assert "--radius-md" in tokens
    assert "--touch-min" in tokens
    assert "--bottom-nav-height" in tokens
    assert "--composer-height" in tokens

    app = (root / "App.tsx").read_text(encoding="utf-8")
    assert 'useLocalStorage(UI_STATE_KEYS.activeTab, "app")' in app
    assert 'home: "app"' in app
    assert 'tasks: "runs"' in app
    assert "setActiveTab(currentTab)" in app
    assert "currentTab === \"app\"" in app
    assert "currentTab === \"projects\"" in app
    assert "currentTab === \"runs\"" in app
    assert "currentTab === \"settings\"" in app
    assert "HomePage" not in app

    assert (root / "components/layout/BottomNav.tsx").exists()
    bottom_nav = (root / "components/layout/BottomNav.tsx").read_text(encoding="utf-8")
    assert "会话" in bottom_nav
    assert "项目" in bottom_nav
    assert "运行" in bottom_nav
    assert "我的" in bottom_nav
    assert "任务" not in bottom_nav
    assert (root / "components/layout/Sheet.tsx").exists()
    assert (root / "components/layout/Toast.tsx").exists()
    assert (root / "components/common/Badge.tsx").exists()
    assert (root / "components/common/Button.tsx").exists()
    assert (root / "components/common/EmptyState.tsx").exists()
    assert (root / "components/common/ErrorSheet.tsx").exists()
    assert (root / "components/common/RecoveryCard.tsx").exists()


def test_frontend_v17_api_client_and_state_exist() -> None:
    root = Path("frontend/src")
    types = (root / "api/types.ts").read_text(encoding="utf-8")
    assert "export type Project" in types
    assert "export type Runner" in types
    assert "export type Task" in types
    assert "export type TaskTemplate" in types
    assert "export type AppThread" in types
    assert "export type AppTurn" in types
    assert "export type Device" in types
    assert "export type Workspace" in types
    assert "export type BridgeHealth" in types

    client = (root / "api/client.ts").read_text(encoding="utf-8")
    assert '"X-API-Token"' in client
    assert '"Content-Type"' in client
    assert "application/json" in client
    assert "fetch(path" in client

    assert (root / "api/tasks.ts").exists()
    assert (root / "api/appThreads.ts").exists()
    assert (root / "api/runners.ts").exists()
    assert (root / "api/projects.ts").exists()
    assert (root / "api/devices.ts").exists()
    assert (root / "api/workspaces.ts").exists()
    devices_api = (root / "api/devices.ts").read_text(encoding="utf-8")
    assert 'apiRequest<Device[]>("/devices")' in devices_api
    workspaces_api = (root / "api/workspaces.ts").read_text(encoding="utf-8")
    assert 'apiRequest<Workspace[]>(`/workspaces${query}`)' in workspaces_api

    storage = (root / "state/storage.ts").read_text(encoding="utf-8")
    assert 'API_TOKEN_KEY = "apiToken"' in storage
    assert 'activeTab: "mobile.activeTab"' in storage
    assert 'taskStatusFilter: "mobile.taskStatusFilter"' in storage
    assert 'appThreadStatusFilter: "mobile.appThreadStatusFilter"' in storage
    assert 'appIncludeArchived: "mobile.appIncludeArchived"' in storage
    assert 'currentProjectId: "mobile.currentProjectId"' in storage
    assert 'currentDeviceId: "mobile.currentDeviceId"' in storage
    assert 'currentWorkspaceId: "mobile.currentWorkspaceId"' in storage
    assert 'selectedAppThreadId: "mobile.selectedAppThreadId"' in storage
    assert 'appSendMode: "mobile.appSendMode"' in storage

    assert (root / "hooks/useLocalStorage.ts").exists()
    assert (root / "hooks/useToast.ts").exists()
    assert (root / "hooks/usePolling.ts").exists()


def test_frontend_v17_pages_are_migrated_to_react() -> None:
    root = Path("frontend/src")
    projects = (root / "components/projects/ProjectsPage.tsx").read_text(encoding="utf-8")
    assert "listDevices()" in projects
    assert "listWorkspaces(effectiveDevice.device_id)" in projects
    assert "listProjects()" in projects
    assert "listAppThreads({ limit: 5, projectId: effectiveProject.id })" in projects
    assert "listTasks({ limit: 5, projectId: effectiveProject.id })" in projects
    assert "UI_STATE_KEYS.currentProjectId" in projects
    assert "UI_STATE_KEYS.currentDeviceId" in projects
    assert "UI_STATE_KEYS.currentWorkspaceId" in projects
    assert 'setCurrentWorkspaceIdText("")' in projects
    assert 'setSelectedThreadIdText("")' in projects
    assert "setActiveTab(\"app\")" in projects
    assert "设备" in projects
    assert "Workspace" in projects
    assert "当前工作空间" in projects
    assert "Bridge cwd" in projects

    runs = (root / "components/runs/RunsPage.tsx").read_text(encoding="utf-8")
    assert "listDevices()" in runs
    assert "deviceDisabledReason(currentDevice)" in runs
    assert "listTasks({ limit: 20, projectId: effectiveProjectId })" in runs
    assert "UI_STATE_KEYS.currentProjectId" in runs
    assert "UI_STATE_KEYS.currentDeviceId" in runs
    assert "cancelTask(run.id)" in runs
    assert "rerunTask(run.id)" in runs
    assert "rerunDisabledReason" in runs
    assert "UI_STATE_KEYS.taskStatusFilter" in runs
    assert "usePolling(loadRuns" in runs
    assert "运行记录" in runs
    assert "新建任务" not in runs

    session = (root / "components/session/SessionPage.tsx").read_text(encoding="utf-8")
    assert "listDevices()" in session
    assert "deviceDisabledReason(currentDevice)" in session
    assert "listAppThreads({" in session
    assert "projectId: effectiveProjectId" in session
    assert "createAppThread(effectiveProjectId, title)" in session
    assert "UI_STATE_KEYS.currentProjectId" in session
    assert "UI_STATE_KEYS.currentDeviceId" in session
    assert "createDisabledReason={executionDisabledReason}" in session
    assert "listAppTurns(selectedThreadId)" in session
    assert "sendAsyncAppTurn" in session
    assert "sendAppTurn" in session
    assert "cancelAppTurn(runningTurn.id)" in session
    assert "reopenAppThread(selectedThreadId)" in session
    assert "getAppThreadFinal(selectedThreadId)" in session
    assert "getAppThreadEvents(selectedThreadId)" in session
    assert "recoverStaleAppTurns()" in session
    assert "cleanupAppThreads(status)" in session

    settings = (root / "components/settings/SettingsPage.tsx").read_text(encoding="utf-8")
    assert "API_TOKEN_KEY" in settings
    assert "getBridgeHealth()" in settings
    assert "listRunners()" in settings
    assert "recoverStaleAppTurns()" in settings
    assert "cleanupAppThreads(status)" in settings

    device_utils = (root / "utils/device.ts").read_text(encoding="utf-8")
    assert "当前设备离线，只能查看历史，不能新建执行" in device_utils
    assert "当前设备已停用，不能新建执行" in device_utils


def test_frontend_v17_docs_and_scripts_are_documented() -> None:
    package_json = json.loads(Path("frontend/package.json").read_text(encoding="utf-8"))
    assert package_json["scripts"]["build"] == "tsc --noEmit && vite build"
    assert package_json["scripts"]["typecheck"] == "tsc --noEmit"
    assert package_json["scripts"]["dev"] == "vite"

    readme = Path("README.md").read_text(encoding="utf-8", errors="replace")
    assert "Mobile Frontend current iteration: v1.8 conversation-first" in readme
    assert "会话 / 项目 / 运行 / 我的" in readme
    assert "运行是底层 Task / Runner 执行记录" in readme
    assert "frontend/src/api" in readme
    assert "/mobile" in readme
    assert "/assets/*" in readme

    plan = Path("docs/mobile-v1.7-frontend-split-plan.md").read_text(
        encoding="utf-8",
        errors="replace",
    )
    assert "v1.7.5" in plan
    assert "python -m compileall backend runner scripts poc/app_server" in plan
    assert "npm run build" in plan


def test_frontend_v176_regression_fixes_exist() -> None:
    root = Path("frontend/src")
    composer = (root / "components/session/Composer.tsx").read_text(encoding="utf-8")
    assert "disabledReason" in composer
    assert 'disabled ? "请选择会话后发送消息"' not in composer
    assert '"同步"' not in composer
    assert "快速发送" in composer
    assert "等待回复" in composer

    switcher = (root / "components/session/ThreadSwitcherSheet.tsx").read_text(encoding="utf-8")
    assert "AppThread 状态筛选" in switcher
    assert '"ACTIVE"' in switcher
    assert '"ERROR"' in switcher
    assert '"CLOSED"' in switcher
    assert "includeArchived" in switcher
    assert "onIncludeArchivedChange" in switcher
    assert "显示 archived" in switcher

    session = (root / "components/session/SessionPage.tsx").read_text(encoding="utf-8")
    assert "getAppThread(selectedThreadId)" in session
    assert "setSelectedThreadIdText(\"\")" in session
    assert "UI_STATE_KEYS.appThreadStatusFilter" in session
    assert "UI_STATE_KEYS.appIncludeArchived" in session
    assert "status: appThreadStatusFilter || undefined" in session
    assert "includeArchived" in session
    assert "请先新建或选择会话" in session
    assert "当前会话已关闭，请重开后继续" in session
    assert "正在等待回复，可以继续编辑，但暂时不能发送" in session
    assert "messageListRef" in session
    assert "shouldStickToBottomRef" in session
    assert "forceScrollAfterSendRef" in session
    assert "distanceToBottom < 96" in session
    assert "streamAppTurn" in session
    assert "startTurnStream(turn.id)" in session
    assert "assistant_delta" in session
    assert "window.requestAnimationFrame" in session
    assert "onReopenThread={handleReopen}" in session

    app_threads_api = (root / "api/appThreads.ts").read_text(encoding="utf-8")
    assert "export async function streamAppTurn" in app_threads_api
    assert "/stream" in app_threads_api
    assert "apiHeaders(false)" in app_threads_api

    header = (root / "components/session/SessionHeader.tsx").read_text(encoding="utf-8")
    assert 'className="session-header-main selected"' in header

    session_css = (root / "styles/session.css").read_text(encoding="utf-8")
    assert ".session-header-main.selected" in session_css
    assert "grid-template-columns: minmax(0, 1fr) auto" in session_css

    bubble = (root / "components/session/MessageBubble.tsx").read_text(encoding="utf-8")
    assert "#{turn.id}" not in bubble
    assert "点击查看详情" not in bubble
    assert "展开全文" in bubble
    assert "收起" in bubble
    assert "unknown bridge thread id" in bubble
    assert "canRecoverByReopen" in bubble
    assert "重开会话" in bubble
    assert "onReopenThread" in bubble

    message_list = (root / "components/session/MessageList.tsx").read_text(encoding="utf-8")
    assert "onReopenThread" in message_list

    task_card = (root / "components/tasks/TaskCard.tsx").read_text(encoding="utf-8")
    assert 'className="task-more-actions"' in task_card
    assert "<summary>更多</summary>" in task_card

    readme = Path("README.md").read_text(encoding="utf-8", errors="replace")
    assert "Mobile UI 当前迭代：v1.2" not in readme
    assert "Mobile Frontend current iteration: v1.8 conversation-first" in readme
    assert "frontend/dist/index.html" in readme

    start_script = Path("scripts/start_app_server_stack.ps1").read_text(encoding="utf-8")
    assert "[switch]$BuildFrontend" in start_script
    assert "frontend\\dist\\index.html" in start_script
    assert "cd frontend" in start_script
    assert "npm install" in start_script
    assert "npm run build" in start_script


def test_legacy_mobile_module_is_frontend_hosting_helper() -> None:
    html = mobile.mobile_console()

    assert "Frontend build not found." in html
    assert "cd frontend" in html
    assert "npm install" in html
    assert "npm run build" in html
    assert "function escapeHtml(value)" not in html
    assert "function renderHome" not in html
    assert "function renderAppTurnConversation" not in html


def test_backend_mobile_py_no_longer_contains_embedded_app() -> None:
    source = Path("backend/mobile.py").read_text(encoding="utf-8")

    assert "def mobile_styles" not in source
    assert "def mobile_home_tab" not in source
    assert "def mobile_tasks_tab" not in source
    assert "def mobile_app_tab" not in source
    assert "def mobile_settings_tab" not in source
    assert "def mobile_script" not in source
    assert len(source.splitlines()) < 80
def test_create_task_form_redirects_to_detail() -> None:
    for client, session in make_client():
        project = add_project(session)

        response = client.post(
            "/ui/tasks",
            data={
                "project_id": str(project.id),
                "prompt": "new prompt",
                "timeout_seconds": "60",
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"].startswith("/ui/tasks/")


def test_rerun_form_redirects_to_new_task_detail() -> None:
    for client, session in make_client():
        project = add_project(session)
        task = add_task(session, project.id)

        response = client.post(
            f"/ui/tasks/{task.id}/rerun",
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] != f"/ui/tasks/{task.id}"


def test_cancel_form_redirects_to_task_detail() -> None:
    for client, session in make_client():
        project = add_project(session)
        task = Task(
            project_id=project.id,
            prompt="cancel from ui",
            status=TaskStatus.PENDING,
            timeout_seconds=120,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(task)
        session.commit()
        session.refresh(task)

        response = client.post(
            f"/ui/tasks/{task.id}/cancel",
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == f"/ui/tasks/{task.id}"


def test_task_detail_auto_refreshes_running_task() -> None:
    task = Task(
        id=1,
        project_id=1,
        prompt="running",
        status=TaskStatus.RUNNING,
        created_at=utc_now(),
        updated_at=utc_now(),
    )

    html = ui.task_detail(task)

    assert '<meta http-equiv="refresh" content="5">' in html


def test_task_detail_does_not_auto_refresh_terminal_task() -> None:
    task = Task(
        id=1,
        project_id=1,
        prompt="done",
        status=TaskStatus.SUCCESS,
        created_at=utc_now(),
        updated_at=utc_now(),
    )

    html = ui.task_detail(task)

    assert 'http-equiv="refresh"' not in html
