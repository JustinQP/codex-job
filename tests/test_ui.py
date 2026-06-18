from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from backend import main as backend_main
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
        backend_main,
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
    monkeypatch.setattr(backend_main, "FRONTEND_INDEX_HTML", index_html)

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


def test_mobile_console_escapes_inner_html_dynamic_fields() -> None:
    for client, session in make_client():
        del client, session
        html = mobile.mobile_console()

        assert "function escapeHtml(value)" in html
        assert 'replaceAll("<", "&lt;")' in html
        assert "${escapeHtml(p.name)}" in html
        assert "${escapeHtml(r.runner_id)}" in html
        assert "${escapeHtml(r.status)}" in html
        assert "${escapeHtml(r.hostname)}" in html
        assert "${escapeHtml(r.supported_models || \"\")}" in html
        assert "${escapeHtml(t.status)}" in html
        assert "${escapeHtml(t.task_type)}" in html
        assert "${escapeHtml(t.assigned_runner_id || t.runner_id || \"\")}" in html
        assert "${escapeHtml(task.model || \"\")}" in html
        assert "${escapeHtml(task.reasoning_effort || \"\")}" in html
        assert "${escapeHtml(task.sandbox || \"\")}" in html
        assert 'href="${escapeHtml(task.log_url)}"' in html
        assert 'href="${escapeHtml(task.result_url)}"' in html
        assert 'href="${escapeHtml(task.diff_url)}"' in html


def test_mobile_console_contains_app_server_session_block() -> None:
    for client, session in make_client():
        del client, session
        html = mobile.mobile_console()
        assert "开始一次 Codex 会话" in html
        assert "选择或新建会话后即可发送消息" in html
        assert 'class="bottom-nav"' in html
        assert 'data-tab="home"' in html
        assert 'data-tab="tasks"' in html
        assert 'data-tab="app"' in html
        assert 'data-tab="settings"' in html
        assert ">首页</button>" in html
        assert ">任务</button>" in html
        assert ">会话</button>" in html
        assert ">我的</button>" in html
        assert 'id="tab-home"' in html
        assert 'class="summary-card home-hero"' in html
        assert "Codex 工作台" in html
        assert "今日工作台：先看状态，再进入任务或会话。" in html
        assert 'id="homeCreateTask"' in html
        assert 'id="homeStatus"' in html
        assert 'id="homeRunning"' in html
        assert 'id="homeAlerts"' in html
        assert 'id="homeTasks"' in html
        assert 'id="homeThreads"' in html
        assert "function renderHome({" in html
        assert "function renderHomeAlerts({" in html
        assert "function renderHomeTasks(tasks)" in html
        assert "function renderHomeThreads(appThreads, appThreadsResult)" in html
        assert "async function loadHomeAppServerStatus(baseState)" in html
        assert "bridgeState.pending ? \"检查中\"" in html
        assert 'safeApi("/health")' in html
        assert 'safeApi("/app-server-bridge/health", {headers: headers()})' in html
        assert 'safeApi("/app-threads?limit=3", {headers: headers()})' in html
        assert "Runner 不再作为独立一级 Tab" not in html
        assert "运行诊断" in html
        assert 'id="toast"' in html
        assert "function showToast(message, type = \"info\")" in html
        assert "async function withButtonLoading(button, loadingText, fn)" in html
        assert "function classifyError(error)" in html
        assert "function showErrorSheet(error, context = \"\")" in html
        assert "function errorActionHtml(action)" in html
        assert "function bindErrorAction(action)" in html
        assert "function showBridgeHelpSheet()" in html
        assert "Token 无效或未保存" in html
        assert "App Server Bridge 不可用" in html
        assert "当前会话已有 Turn 正在运行" in html
        assert "网络请求失败" in html
        assert "error.code=${escapeHtml(info.code)}" in html
        assert "去保存 Token" in html
        assert "查看启动提示" in html
        assert "刷新页面状态" in html
        assert 'activeTab: "mobile.activeTab"' in html
        assert 'taskStatusFilter: "mobile.taskStatusFilter"' in html
        assert 'appThreadStatusFilter: "mobile.appThreadStatusFilter"' in html
        assert 'appIncludeArchived: "mobile.appIncludeArchived"' in html
        assert 'selectedAppThreadId: "mobile.selectedAppThreadId"' in html
        assert 'appSendMode: "mobile.appSendMode"' in html
        assert "function restoreInitialUiState()" in html
        assert "function readStoredNumber(key)" in html
        assert "function writeUiState(key, value)" in html
        assert "function removeUiState(key)" in html
        assert 'switchTab(activeTabName, false)' in html
        assert "document.visibilityState" in html
        assert "function startTaskAutoRefresh()" in html
        assert "function stopTaskAutoRefresh()" in html
        assert "function updateTaskAutoRefresh()" in html
        assert "async function refreshTasksForAutoRefresh()" in html
        assert "clearInterval(taskAutoRefreshTimer)" in html
        assert "if (taskAutoRefreshTimer) return;" in html
        assert "document.addEventListener(\"visibilitychange\", handleVisibilityChange)" in html
        assert "function isStaleBridgeThreadError(value)" in html
        assert "function showStaleBridgeThreadSheet(error)" in html
        assert "unknown bridge thread id" in html
        assert "会话需要重开" in html
        assert "Bridge 会话已失效" in html
        assert "重开当前会话" in html
        assert "历史 turns 会保留，但 App Server 上下文会从新的 thread 重新开始。" in html
        assert 'id="openCreateTaskSheet"' in html
        assert 'id="sheetBackdrop"' in html
        assert "function openSheet(title, contentHtml)" in html
        assert "function closeSheet()" in html
        assert "function renderCreateTaskSheet()" in html
        assert 'class="task-form-sheet"' in html
        assert "floating-action" in html
        assert "普通使用只需要选择项目、Prompt 和任务类型" in html
        assert "v1.6 mobile chat viewport POC" in html
        assert "--space-1: 4px" in html
        assert "--touch-min: 40px" in html
        assert "summary-card" in html
        assert "list-card" in html
        assert "detail-card" in html
        assert "btn-primary" in html
        assert "recovery-card" in html
        assert "page-header" in html
        assert "page-body" in html
        assert "page-footer" in html
        assert ".empty-state strong" in html
        assert ".empty-state button" in html
        assert "没有在线 Runner" in html
        assert "没有匹配任务" in html
        assert "还没有 App 会话" in html
        assert "暂无 AppThread" in html
        assert "还没有消息" in html
        assert "<h2>任务</h2>" in html
        assert 'id="taskStatusFilter"' in html
        assert 'id="taskStatusSegments"' in html
        assert 'class="segmented-control"' in html
        assert "任务状态筛选" in html
        assert '<option value="">全部</option>' in html
        assert '<option value="PENDING">PENDING</option>' in html
        assert '<option value="RUNNING">RUNNING</option>' in html
        assert '<option value="SUCCESS">SUCCESS</option>' in html
        assert '<option value="FAILED">FAILED</option>' in html
        assert '<option value="CANCELLED">CANCELLED</option>' in html
        assert 'id="taskFilterSummary"' in html
        assert "let tasksCache = []" in html
        assert "function selectedTaskStatusFilter()" in html
        assert "function renderTaskStatusSegments()" in html
        assert "function filterTasksByStatus(tasks)" in html
        assert "function renderFilteredTasks()" in html
        assert 'writeUiState(UI_STATE_KEYS.taskStatusFilter, document.getElementById("taskStatusFilter").value)' in html
        assert "renderHome({" in html
        assert "function renderTasks(tasks)" in html
        assert "function showTaskMore(id)" in html
        assert "async function rerunTask(id, button = null)" in html
        assert 'class="list-card task-card"' in html
        assert 'class="task-card-header"' in html
        assert 'class="meta-grid"' in html
        assert 'class="task-actions"' in html
        assert 'class="task-detail-grid"' in html
        assert 'class="detail-card"' in html
        assert "function taskTitleLine(task)" in html
        assert "<summary>技术参数</summary>" in html
        assert "<summary>更多操作</summary>" in html
        assert '<h3>log/result 预览</h3>' in html
        assert 'id="taskPreview"' in html
        assert "<summary>高级参数</summary>" in html
        assert "<summary>调试输出</summary>" in html
        assert 'id="tab-app" class="tab-page page app-console"' in html
        assert "#tab-app.app-console" in html
        assert "flex-direction: column" in html
        assert "overflow: hidden" in html
        assert "#tab-app.app-console.active { display: flex; }" in html
        assert 'class="page-header card app-current-card session-header"' in html
        assert 'class="page-body card app-main-panel message-list"' in html
        assert '<summary>AppThread 列表</summary>' not in html
        assert '<summary>事件摘要</summary>' in html
        assert 'class="app-hidden-state"' in html
        assert 'class="page-footer card app-composer session-composer"' in html
        assert "session-header" in html
        assert "message-list" in html
        assert "session-composer" in html
        assert ".session-title-area" in html
        assert ".session-subtitle" in html
        assert "min-height: 48px" in html
        assert "max-width: 58px" in html
        assert "box-shadow: none" in html
        assert "overflow-y: auto" in html
        assert 'id="appMessageHint"' in html
        assert 'id="appMessageCount" class="message-count empty"' in html
        assert 'id="sendModeToggle"' in html
        assert ".composer-meta" in html
        assert ".message-count.empty" in html
        assert ".composer-status-row" in html
        assert ".composer-input-row" in html
        assert ".send-mode-inline" in html
        assert ".send-mode-toggle-hidden" in html
        assert ".send-button" in html
        assert "max-height: 120px" in html
        assert "min-height: 44px" in html
        assert "function updateAppComposerState()" in html
        assert 'document.getElementById("appMessage").oninput = () =>' in html
        assert 'updateAppComposerState();' in html
        assert "function autoResizeComposer()" in html
        assert "function toggleAppSendMode()" in html
        assert "document.getElementById(\"sendModeToggle\").onclick = toggleAppSendMode" in html
        assert "function formatRelativeTime(value)" in html
        assert 'if (!value) return ""' in html
        assert 'return "刚刚"' in html
        assert "分钟前" in html
        assert "今天 ${time}" in html
        assert "padStart(2, \"0\")" in html
        assert "const updatedAt = formatRelativeTime(thread.updated_at)" in html
        assert "parts.push(`更新 ${updatedAt}`)" in html
        assert "parts.push(`更新 ${thread.updated_at}`)" not in html
        assert "count.textContent = rawMessage.length ? `${rawMessage.length} 字` : \"\"" in html
        assert 'count.classList.toggle("empty", rawMessage.length === 0)' in html
        assert "输入消息后即可发送" in html
        assert "请先新建或选择会话" in html
        assert "快速发送，后台等待回复" in html
        assert "等待回复，完成后返回" in html
        assert "快速发送" in html
        assert "等待回复" in html
        assert "正在等待回复，可以继续编辑，但暂时不能发送" in html
        assert 'class="chat-list message-flow"' in html
        assert "切换会话" in html
        assert "选择已有" in html
        assert "快速新建" in html
        assert "最近会话" in html
        assert "会话更多" in html
        assert "function renderAppThreadSwitcherSheet()" in html
        assert "async function showAppThreadSwitcher()" in html
        assert "function showAppSessionMore()" in html
        assert "function showAppTurnDetailSheet(turn)" in html
        assert "async function showAppEventsSheet(button = null)" in html
        assert "function showAppDebugSheet()" in html
        assert "function sendAppMessage()" in html
        assert "function persistSendMode()" in html
        assert 'id="sendAppMessage"' in html
        assert 'id="appSendAsync" type="checkbox" checked' in html
        assert "selectedSendMode()" in html
        assert "sendAsyncAppTurn()" in html
        assert "sendAppTurn()" in html
        assert 'document.getElementById("sendAppMessage").onclick' in html
        assert "function renderAppTurnConversation(turn)" in html
        assert "function selectAppTurn(turnId)" in html
        assert "function copyTurnMessageToComposer(turnId)" in html
        assert "function showTurnErrorSheet(turnId)" in html
        assert "function toggleTurnExpanded(turnId)" in html
        assert "function recoveryAdviceForTurn(turn)" in html
        assert "function scrollAppMessagesToBottom(force = false)" in html
        assert "scrollTarget.scrollTop = scrollTarget.scrollHeight" in html
        assert "function resumeActiveAppTurnPolling()" in html
        assert "let appTurnPollTargetId = null" in html
        assert "if (appTurnPollTimer && appTurnPollTargetId === turnId) return;" in html
        assert "let appTurnsCache = []" in html
        assert "let expandedAppTurnIds = new Set()" in html
        assert ".bubble-row.user" in html
        assert ".bubble-row.assistant" in html
        assert ".bubble.user" in html
        assert "max-width: 76%" in html
        assert ".bubble.assistant" in html
        assert "max-width: 94%" in html
        assert ".bubble.assistant.running" in html
        assert ".bubble.assistant.failed" in html
        assert ".assistant-message.collapsed" in html
        assert ".bubble-detail-hint" in html
        assert "点击查看详情" in html
        assert "这次回复失败" in html
        assert "复制重试" in html
        assert "查看错误" in html
        assert "展开全文" in html
        assert "收起" in html
        assert "失败恢复" in html
        assert "重开会话" in html
        assert ".app-composer" in html
        assert "检查 App Server Bridge" in html
        assert "appOutput" in html
        assert "查看最终回复" in html
        assert "查看事件摘要" in html
        assert ">重开</button>" in html
        assert ">关闭会话</button>" in html
        assert ">发送</button>" in html
        assert "刷新当前回复" in html
        assert "取消当前 Turn" in html
        assert "恢复卡住 turn" in html
        assert "状态筛选" in html
        assert "常用" in html
        assert "会话管理" in html
        assert "调试与维护" in html
        assert "清理归档" in html
        assert "清理 CLOSED" in html
        assert "清理 ERROR" in html
        assert "显示 archived" in html
        assert "archived" in html
        assert "appTurnStatus" in html
        assert "appEventsSummary" in html
        assert "CANCELLED" in html
        assert "正在等待 App Server 返回" in html
        assert "当前会话已关闭，请重开后继续" in html
        assert "item list-card thread-card selected" in html
        assert ".badge.active" in html
        assert ".badge.success" in html
        assert ".badge.pending" in html
        assert ".badge.running" in html
        assert ".badge.failed" in html
        assert ".badge.cancelled" in html
        assert ".badge.error" in html
        assert ".badge.closed" in html
        assert ".toast.success" in html
        assert ".toast.error" in html
        assert 'class="badge ${escapeHtml(className)}"' in html
        assert 'api("/app-server-bridge/health"' in html
        assert 'new URLSearchParams({limit: "20"})' in html
        assert 'api("/app-threads", {method: "POST"' in html
        assert 'api("/app-turns/recover-stale"' in html
        assert 'api("/app-threads/cleanup"' in html
        assert 'confirm(`确认将 CLOSED AppThread 标记为 archived？`)' in html
        assert 'confirm(`确认将 ERROR AppThread 标记为 archived？`)' in html
        assert 'confirm("确认将所有 PENDING/RUNNING AppTurn 标记为 FAILED？")' in html
        assert 'confirm(`确认取消 App Turn #${selectedAppTurnId}？`)' in html
        assert 'document.getElementById("appWaiting").textContent = "";' in html
        assert "const listedThread = appThreads.find(t => t.id === selectedAppThreadId);" in html
        assert 'String(t.title || "").startsWith("[archived]")' in html
        assert 'document.getElementById("appThreadsSheet")' in html
        assert "if (listedThread) selectedAppThread = listedThread;" in html
        assert "当前会话不在当前筛选结果中" in html
        assert "async function restoreSelectedAppThreadAfterLoad()" in html
        assert 'id="appThreadProject"' in html
        assert 'id="appThreadTitleInput"' in html
        assert "确认将 CLOSED AppThread 标记为 archived？" in html
        assert "确认将 ERROR AppThread 标记为 archived？" in html
        assert 'api(`/app-threads/${selectedAppThreadId}/turns`' in html
        assert 'api(`/app-threads/${selectedAppThreadId}/turns/async`' in html
        assert 'api(`/app-turns/${selectedAppTurnId}`' in html
        assert 'api(`/app-turns/${selectedAppTurnId}/cancel`' in html
        assert 'api(`/app-threads/${selectedAppThreadId}/final`' in html
        assert 'api(`/app-threads/${selectedAppThreadId}/events`' in html
        assert 'api(`/app-threads/${selectedAppThreadId}/reopen`' in html
        assert 'api(`/app-threads/${selectedAppThreadId}`, {method: "DELETE"' in html
        assert 'api("/tasks?limit=20"' in html
        assert 'api("/tasks", {method: "POST"' in html
        assert 'api(`/tasks/${id}`' in html
        assert 'api(`/tasks/${id}/cancel`' in html
        assert 'api(`/tasks/${id}/rerun`' in html
        assert 'confirm(`确认取消任务 #${id}？`)' in html
        assert 'api("/runners"' in html
        assert 'api("/task-templates"' in html
        assert "${escapeHtml(t.task_type)}" in html
        assert "${escapeHtml(t.assigned_runner_id || t.runner_id || \"\")}" in html
        assert "${escapeHtml(t.updated_at || \"\")}" in html
        assert "${escapeHtml(task.reasoning_effort || \"\")}" in html
        assert "${escapeHtml(task.sandbox || \"\")}" in html
        assert "${escapeHtml(task.timeout_seconds || \"\")}" in html
        assert "document.getElementById(\"taskPreview\").textContent = logText" in html
        assert "async function showTaskMore(id)" in html
        assert "<summary>更多操作</summary>" in html
        assert "重跑" in html
        assert "${escapeHtml(t.title)}" in html
        assert "${escapeHtml(t.status)}" in html
        assert "${escapeHtml(t.turn_count)}" in html
        assert "${escapeHtml(shortText(t.latest_assistant_final || \"\", 160))}" in html
        assert "last_error=${escapeHtml(t.last_error)}" in html
        assert "${escapeHtml(normalized)} ${escapeHtml(label)}" in html
        assert "${escapeHtml(turn.id)}" in html
        assert "statusBadge(turn.status)" in html
        assert "${escapeHtml(turn.duration_seconds ?? \"\")}" in html
        assert "${escapeHtml(turn.bridge_turn_id || \"\")}" in html
        assert "${escapeHtml(turn.created_at || \"\")}" in html
        assert "turn.assistant_final || turn.error_message || \"\"" in html
        assert "final.assistant_final ? escapeHtml(final.assistant_final)" in html
        assert "暂无 assistant_final" in html
        assert "const assistantText = turn.assistant_final || turn.error_message || \"\"" in html
        assert "<strong>total_events</strong>" in html
        assert "${escapeHtml(summary.total_events ?? 0)}" in html
        assert "<strong>has_error</strong>" in html
        assert "${escapeHtml(summary.has_error ?? false)}" in html
        assert "<strong>event_type_counts</strong>" in html
        assert "${escapeHtml(JSON.stringify(eventCounts))}" in html
        assert "<strong>assistant_text_preview</strong>" in html
        assert "${escapeHtml(summary.assistant_text_preview || \"\")}" in html


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
