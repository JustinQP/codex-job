from __future__ import annotations


def mobile_console() -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
{mobile_head()}
{mobile_body()}
{mobile_script()}
</html>"""


def mobile_head() -> str:
    return """<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Codex Mobile Console</title>
  <style>
    :root {
      --bg: #f3f5f8;
      --surface: #ffffff;
      --surface-soft: #f8fafc;
      --border: #d8dee8;
      --text: #172033;
      --muted: #64748b;
      --primary: #2563eb;
      --primary-strong: #1d4ed8;
      --secondary: #64748b;
      --danger: #dc2626;
      --danger-strong: #b91c1c;
      --success-bg: #dcfce7;
      --success-text: #166534;
      --info-bg: #dbeafe;
      --info-text: #1d4ed8;
      --error-bg: #fee2e2;
      --error-text: #991b1b;
      --warning-bg: #ffedd5;
      --warning-text: #9a3412;
      --closed-bg: #e5e7eb;
      --closed-text: #374151;
      --shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
    }
    header {
      position: sticky;
      top: 0;
      background: #111827;
      color: #fff;
      padding: 14px 16px 12px;
      z-index: 2;
      box-shadow: 0 2px 12px rgba(15, 23, 42, 0.18);
    }
    h1 { font-size: 18px; margin: 0; letter-spacing: 0; }
    h2 { font-size: 16px; margin: 0 0 10px; letter-spacing: 0; }
    h3 { font-size: 14px; margin: 0 0 8px; letter-spacing: 0; }
    p { margin: 0 0 10px; }
    main { padding: 14px 14px 88px; }
    label { display: grid; gap: 5px; margin: 8px 0; font-size: 13px; color: var(--text); }
    input, select, textarea, button {
      font: inherit;
      box-sizing: border-box;
      width: 100%;
    }
    input, select, textarea {
      min-height: 42px;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px;
      background: #fff;
      color: var(--text);
    }
    textarea { min-height: 118px; resize: vertical; line-height: 1.45; }
    button {
      min-height: 42px;
      border: 0;
      border-radius: 10px;
      padding: 10px 12px;
      background: var(--primary);
      color: #fff;
      font-weight: 650;
    }
    button:hover { background: var(--primary-strong); }
    button:disabled { opacity: 0.62; }
    button.secondary { background: var(--secondary); }
    button.danger { background: var(--danger); }
    button.danger:hover { background: var(--danger-strong); }
    button.ghost {
      background: var(--surface-soft);
      color: var(--text);
      border: 1px solid var(--border);
    }
    button.tab-button {
      min-height: 52px;
      border-radius: 0;
      background: transparent;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }
    button.tab-button.active {
      color: var(--primary);
      background: #eef4ff;
    }
    .top-subtitle { margin-top: 4px; color: #cbd5e1; font-size: 12px; }
    .tab-page { display: none; gap: 12px; }
    .tab-page.active { display: grid; }
    .app-console { padding-bottom: 154px; }
    .bottom-nav {
      position: fixed;
      left: 0;
      right: 0;
      bottom: 0;
      z-index: 3;
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      background: #fff;
      border-top: 1px solid var(--border);
      box-shadow: 0 -8px 24px rgba(15, 23, 42, 0.08);
    }
    .card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 14px;
      box-shadow: var(--shadow);
    }
    .card.soft { background: var(--surface-soft); box-shadow: none; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .stack { display: grid; gap: 8px; }
    .actions { display: grid; gap: 8px; }
    .muted { color: var(--muted); font-size: 12px; }
    .inline { display: flex; align-items: center; gap: 8px; }
    .inline input { width: auto; min-height: auto; }
    .item {
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px;
      background: var(--surface-soft);
    }
    .item.selected { border-left: 4px solid var(--primary); padding-left: 8px; }
    .empty-state {
      border: 1px dashed var(--border);
      border-radius: 10px;
      padding: 12px;
      background: var(--surface-soft);
      color: var(--muted);
      font-size: 13px;
    }
    .links { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
    .links a { color: var(--primary); text-decoration: none; font-size: 13px; font-weight: 650; }
    .task-card {
      display: grid;
      gap: 10px;
    }
    .task-card-header {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      align-items: flex-start;
    }
    .task-title {
      font-size: 16px;
      font-weight: 750;
    }
    .meta-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }
    .meta-cell {
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 8px;
      background: #fff;
      min-width: 0;
    }
    .meta-label {
      display: block;
      color: var(--muted);
      font-size: 11px;
      margin-bottom: 3px;
    }
    .meta-value {
      display: block;
      font-size: 13px;
      word-break: break-word;
    }
    .task-actions {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 6px;
    }
    .task-actions a,
    .task-actions button {
      min-height: 36px;
      border-radius: 8px;
      display: grid;
      place-items: center;
      text-align: center;
      text-decoration: none;
      font-size: 12px;
      font-weight: 750;
      padding: 7px 6px;
    }
    .task-actions a {
      border: 1px solid var(--border);
      background: #fff;
      color: var(--primary);
    }
    .task-actions button {
      background: var(--danger);
      color: #fff;
    }
    .task-detail-grid {
      display: grid;
      gap: 10px;
    }
    .detail-section {
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px;
      background: var(--surface-soft);
    }
    .detail-section h3 { margin-bottom: 8px; }
    .preview-block {
      margin-top: 8px;
      max-height: 220px;
      overflow: auto;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 750;
      background: var(--closed-bg);
      color: var(--closed-text);
    }
    .badge.active, .badge.success { background: var(--success-bg); color: var(--success-text); }
    .badge.pending, .badge.running { background: var(--info-bg); color: var(--info-text); }
    .badge.error, .badge.failed { background: var(--error-bg); color: var(--error-text); }
    .badge.closed, .badge.cancelled { background: var(--closed-bg); color: var(--closed-text); }
    .badge.warning { background: var(--warning-bg); color: var(--warning-text); }
    .app-current-card {
      position: sticky;
      top: 62px;
      z-index: 1;
    }
    .app-current-layout {
      display: grid;
      gap: 10px;
    }
    .app-current-title {
      font-size: 17px;
      font-weight: 750;
      margin-bottom: 4px;
    }
    .app-current-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      align-items: center;
      margin: 8px 0;
    }
    .final-preview {
      margin-top: 8px;
      border-left: 3px solid var(--primary);
      padding: 8px 10px;
      background: #eef4ff;
      border-radius: 8px;
      font-size: 13px;
      line-height: 1.45;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .error-line {
      margin-top: 8px;
      padding: 8px 10px;
      border-radius: 8px;
      background: var(--error-bg);
      color: var(--error-text);
      font-size: 13px;
      word-break: break-word;
    }
    .app-toolbar {
      display: grid;
      gap: 8px;
    }
    .thread-list-details[open] {
      background: var(--surface);
    }
    .thread-list-tools {
      display: grid;
      gap: 8px;
      margin-top: 10px;
    }
    .app-main-panel {
      display: grid;
      gap: 10px;
    }
    .chat-list {
      display: grid;
      gap: 12px;
    }
    .chat-turn {
      display: grid;
      gap: 6px;
    }
    .bubble-row {
      display: flex;
      width: 100%;
    }
    .bubble-row.user { justify-content: flex-end; }
    .bubble-row.assistant { justify-content: flex-start; }
    .bubble {
      max-width: 86%;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 10px;
      line-height: 1.45;
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 13px;
    }
    .bubble.user {
      background: var(--primary);
      color: #fff;
      border-color: var(--primary);
      border-bottom-right-radius: 4px;
    }
    .bubble.user .muted { color: #dbeafe; }
    .bubble.assistant {
      background: var(--surface);
      border-bottom-left-radius: 4px;
      box-shadow: 0 4px 14px rgba(15, 23, 42, 0.06);
    }
    .bubble.assistant.pending,
    .bubble.assistant.running {
      background: var(--info-bg);
      border-color: #93c5fd;
    }
    .bubble.assistant.failed,
    .bubble.assistant.error {
      background: var(--error-bg);
      border-color: #fecaca;
      color: var(--error-text);
    }
    .bubble.assistant.cancelled,
    .bubble.assistant.closed {
      background: var(--closed-bg);
      border-color: #cbd5e1;
      color: var(--closed-text);
    }
    .turn-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      align-items: center;
      margin-bottom: 6px;
    }
    .loading-card {
      margin: 6px 0;
      border-radius: 8px;
      padding: 8px;
      background: rgba(37, 99, 235, 0.1);
      color: var(--info-text);
      font-weight: 700;
    }
    .app-composer {
      position: sticky;
      bottom: 64px;
      z-index: 2;
      box-shadow: 0 -8px 24px rgba(15, 23, 42, 0.12);
    }
    .app-composer textarea { min-height: 96px; }
    .summary-grid {
      display: grid;
      gap: 6px;
      font-size: 13px;
      word-break: break-word;
    }
    details {
      border: 1px solid var(--border);
      border-radius: 10px;
      background: var(--surface-soft);
      padding: 10px;
    }
    details summary { font-weight: 700; color: var(--text); }
    details > *:not(summary) { margin-top: 8px; }
    pre {
      white-space: pre-wrap;
      word-break: break-word;
      background: #0f172a;
      color: #e5e7eb;
      padding: 10px;
      border-radius: 8px;
      max-height: 260px;
      overflow: auto;
      margin: 0;
    }
    .toast {
      position: fixed;
      left: 14px;
      right: 14px;
      bottom: 72px;
      z-index: 4;
      display: none;
      padding: 12px;
      border-radius: 12px;
      box-shadow: var(--shadow);
      font-size: 13px;
      background: #111827;
      color: #fff;
    }
    .toast.show { display: block; }
    .toast.success { background: #166534; }
    .toast.error { background: #991b1b; }
    .toast.warning { background: #9a3412; }
    .toast.info { background: #1d4ed8; }
    @media (min-width: 760px) {
      main { max-width: 920px; margin: 0 auto; }
      .actions { grid-template-columns: repeat(3, 1fr); }
      .task-actions { grid-template-columns: repeat(5, max-content); }
    }
  </style>
</head>"""


def mobile_body() -> str:
    return """<body>
<header>
  <h1>Codex Mobile Console</h1>
  <div class="top-subtitle">Codex Remote Runner + App Server Sidecar</div>
</header>
<div id="toast" class="toast" role="status" aria-live="polite"></div>
<main>
  <section id="tab-tasks" class="tab-page active" data-tab-page="tasks">
    <div class="card">
      <h2>快速创建任务</h2>
      <label>项目 <select id="project"></select></label>
      <label>任务类型 <select id="taskType"></select></label>
      <label>Prompt <textarea id="prompt" placeholder="输入受控目标或 GOAL 任务"></textarea></label>
      <button id="createTask">提交任务</button>
      <details>
        <summary>高级参数</summary>
        <label>Runner <select id="runner"></select></label>
        <div class="row">
          <label>模型
            <select id="model">
              <option value="">项目默认</option>
              <option value="default">default</option>
              <option value="gpt-5">gpt-5</option>
              <option value="gpt-5-codex">gpt-5-codex</option>
            </select>
          </label>
          <label>推理难度
            <select id="reasoning">
              <option value="">项目默认</option>
              <option value="default">default</option>
              <option value="low">low</option>
              <option value="medium">medium</option>
              <option value="high">high</option>
            </select>
          </label>
        </div>
        <div class="row">
          <label>Sandbox
            <select id="sandbox">
              <option value="workspace-write">workspace-write</option>
              <option value="read-only">read-only</option>
              <option value="danger-full-access">danger-full-access</option>
            </select>
          </label>
          <label>Timeout 秒 <input id="timeoutSeconds" type="number" min="30" max="21600" value="7200"></label>
        </div>
      </details>
      <p class="muted">主线 Runner/codex exec 任务链路。普通使用只需要选择项目、任务类型并填写 Prompt。</p>
    </div>

    <div class="card">
      <div class="row">
        <h2>最近任务</h2>
        <button id="refresh" class="secondary">刷新任务</button>
      </div>
      <div id="tasks" class="stack"></div>
    </div>

    <div class="card">
      <div class="row">
        <h2>任务详情</h2>
        <button id="clearOutput" class="ghost">清空预览</button>
      </div>
      <div id="taskDetail" class="stack"></div>
      <details>
        <summary>调试输出</summary>
        <pre id="output"></pre>
      </details>
    </div>
  </section>

  <section id="tab-app" class="tab-page app-console" data-tab-page="app">
    <div class="card">
      <h2>App Server 会话</h2>
      <p class="muted">App Server 会话为 sidecar POC；不替代 Runner/codex exec 主链路。</p>
      <div class="row">
        <button id="checkAppBridge" class="secondary">检查 App Server Bridge</button>
        <button id="refreshAppThreads" class="secondary">刷新 App Threads</button>
      </div>
      <div id="appBridgeStatus" class="muted"></div>
    </div>

    <div class="card app-current-card">
      <div class="row">
        <h2>当前 AppThread</h2>
        <button id="createAppThread" class="secondary">新建</button>
      </div>
      <div id="appThreadCurrent" class="item">当前 App Thread: 未选择</div>
      <label>App Thread 标题 <input id="appThreadTitle" placeholder="App Thread 标题"></label>
      <div class="row">
        <button id="reopenAppThread" class="secondary">重开</button>
        <button id="closeAppThread" class="danger">关闭</button>
      </div>
      <button id="recoverStaleTurns" class="secondary">恢复卡住 turn</button>
    </div>

    <details class="thread-list-details">
      <summary>AppThread 列表</summary>
      <div class="thread-list-tools">
        <div class="row">
          <label>Thread 状态筛选
            <select id="appThreadStatusFilter">
              <option value="">全部</option>
              <option value="ACTIVE">ACTIVE</option>
              <option value="ERROR">ERROR</option>
              <option value="CLOSED">CLOSED</option>
            </select>
          </label>
          <label class="inline"><input id="appIncludeArchived" type="checkbox"> 显示 archived</label>
        </div>
        <div class="row">
          <button id="cleanupClosedThreads" class="secondary">清理 CLOSED</button>
          <button id="cleanupErrorThreads" class="secondary">清理 ERROR</button>
        </div>
      </div>
      <div id="appThreads" class="stack"></div>
    </details>

    <div class="card app-main-panel">
      <h2>会话</h2>
      <div class="row">
        <button id="loadAppFinal" class="secondary">查看 App Final</button>
        <button id="loadAppTurns" class="secondary">刷新会话</button>
      </div>
      <div class="row">
        <button id="refreshAppTurn" class="secondary">刷新当前 Turn</button>
        <button id="cancelAppTurn" class="danger">取消当前 Turn</button>
      </div>
      <div id="appThreadFinal" class="item"></div>
      <div id="appTurnStatus" class="item"></div>
      <div id="appTurns" class="chat-list"></div>
      <details>
        <summary>事件摘要</summary>
        <button id="loadAppEvents" class="secondary">查看 App Events</button>
        <div id="appEventsSummary" class="summary-grid"></div>
      </details>
      <details>
        <summary>调试输出</summary>
        <pre id="appOutput"></pre>
      </details>
    </div>

    <div class="card app-composer">
      <label>发送消息 <textarea id="appMessage" placeholder="发送到当前 App Thread 的消息"></textarea></label>
      <div id="appWaiting" class="muted"></div>
      <div class="row">
        <button id="sendAppTurn">同步发送</button>
        <button id="sendAsyncAppTurn">异步发送</button>
      </div>
    </div>
  </section>

  <section id="tab-runner" class="tab-page" data-tab-page="runner">
    <div class="card">
      <div class="row">
        <div>
          <h2>Runner</h2>
          <p class="muted">查看 Runner 在线状态、hostname、pid 和 supported_models。</p>
        </div>
        <button id="refreshRunners" class="secondary">刷新 Runner</button>
      </div>
      <div id="runners" class="stack"></div>
    </div>
  </section>

  <section id="tab-settings" class="tab-page" data-tab-page="settings">
    <div class="card">
      <h2>API Token</h2>
      <label>Token <input id="token" type="password" placeholder="X-API-Token"></label>
      <button id="saveToken" class="secondary">保存 Token</button>
      <p class="muted">Token 保存在当前浏览器 localStorage。</p>
    </div>
    <div class="card">
      <h2>设置</h2>
      <div class="item">
        <strong>当前版本</strong><br>
        <span class="muted">v1.1.2 mobile UI/UX POC</span>
      </div>
      <div class="item">
        <strong>Backend 地址</strong><br>
        <span class="muted">默认使用当前 origin，入口为 /mobile。</span>
      </div>
      <div class="item">
        <strong>Bridge sidecar</strong><br>
        <span class="muted">App Server Bridge 独立运行，不替代 Runner/codex exec 主链路。</span>
      </div>
    </div>
    <div class="card">
      <h2>Smoke 命令</h2>
      <pre>$env:API_TOKEN="dev-token"
python .\\scripts\\smoke_app_server_flow.py --base-url http://127.0.0.1:8000 --project-path F:\\JustinKing\\codex-job --async-turn</pre>
    </div>
    <div class="card">
      <h2>当前限制</h2>
      <p class="muted">不支持 SSE、审批 UI、diff UI；App Server 仍是 experimental sidecar POC。</p>
    </div>
  </section>
</main>

<nav class="bottom-nav" aria-label="Mobile tabs">
  <button class="tab-button active" data-tab="tasks">任务</button>
  <button class="tab-button" data-tab="app">App 会话</button>
  <button class="tab-button" data-tab="runner">Runner</button>
  <button class="tab-button" data-tab="settings">设置</button>
</nav>"""


def mobile_script() -> str:
    return """<script>
const tokenInput = document.getElementById("token");
const output = document.getElementById("output");
const appOutput = document.getElementById("appOutput");
const toast = document.getElementById("toast");
const APP_WAITING_TEXT = "正在等待 App Server 返回，请不要刷新页面。";
const APP_TURN_TERMINAL_STATUSES = ["SUCCESS", "FAILED", "CANCELLED"];
let selectedAppThreadId = null;
let selectedAppThread = null;
let selectedAppTurnId = null;
let appTurnPollTimer = null;
let appThreadsCache = [];
let appTurnsCache = [];
let toastTimer = null;
tokenInput.value = localStorage.getItem("apiToken") || "";

function headers(json = false) {
  const h = {};
  const token = localStorage.getItem("apiToken") || "";
  if (token) h["X-API-Token"] = token;
  if (json) h["Content-Type"] = "application/json";
  return h;
}

function log(text) {
  output.textContent = text;
}

function appLog(text) {
  appOutput.textContent = text;
}

function showToast(message, type = "info") {
  toast.textContent = String(message || "");
  toast.className = `toast show ${type}`;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.className = "toast";
  }, 2600);
}

async function withButtonLoading(button, loadingText, fn) {
  const target = typeof button === "string" ? document.getElementById(button) : button;
  const originalText = target ? target.textContent : "";
  if (target) {
    target.disabled = true;
    target.textContent = loadingText || "处理中...";
  }
  try {
    const result = await fn();
    return result;
  } catch (err) {
    showToast(String(err), "error");
    appLog(String(err));
    return null;
  } finally {
    if (target) {
      target.disabled = false;
      target.textContent = originalText;
    }
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return response.json();
  return response.text();
}

function switchTab(tabName) {
  document.querySelectorAll("[data-tab-page]").forEach(page => {
    page.classList.toggle("active", page.dataset.tabPage === tabName);
  });
  document.querySelectorAll("[data-tab]").forEach(button => {
    button.classList.toggle("active", button.dataset.tab === tabName);
  });
}

async function loadAll() {
  const [projects, runners, tasks, templates] = await Promise.all([
    api("/projects", {headers: headers()}),
    api("/runners", {headers: headers()}),
    api("/tasks?limit=20", {headers: headers()}),
    api("/task-templates", {headers: headers()}),
  ]);
  renderProjects(projects);
  renderRunners(runners);
  renderTasks(tasks);
  renderTaskTypes(templates);
  try {
    await loadAppThreadList();
  } catch (err) {
    appLog(String(err));
  }
}

function renderProjects(projects) {
  document.getElementById("project").innerHTML = projects
    .filter(p => p.enabled)
    .map(p => `<option value="${escapeHtml(p.id)}">${escapeHtml(p.name)}</option>`)
    .join("");
}

function renderTaskTypes(templates) {
  document.getElementById("taskType").innerHTML = templates
    .map(t => `<option value="${escapeHtml(t.task_type)}">${escapeHtml(t.task_type)}</option>`)
    .join("");
}

function renderRunners(runners) {
  document.getElementById("runner").innerHTML =
    `<option value="">自动 / 项目默认</option>` +
    runners.map(r => `<option value="${escapeHtml(r.runner_id)}">${escapeHtml(r.runner_id)} (${escapeHtml(r.status)})</option>`).join("");
  document.getElementById("runners").innerHTML = runners.map(r => `
    <div class="item">
      <strong>${escapeHtml(r.runner_id)}</strong> ${statusBadge(r.status)}<br>
      <span class="muted">${escapeHtml(r.hostname)} pid=${escapeHtml(r.pid)} models=${escapeHtml(r.supported_models || "")}</span>
    </div>`).join("");
}

function renderTasks(tasks) {
  document.getElementById("tasks").innerHTML = tasks.length
    ? tasks.map(t => `
      <div class="item task-card">
        <div class="task-card-header">
          <div>
            <div class="task-title">#${escapeHtml(t.id)} ${escapeHtml(t.task_type)}</div>
            <span class="muted">project=${escapeHtml(t.project_id)}</span>
          </div>
          ${statusBadge(t.status)}
        </div>
        <div class="meta-grid">
          <div class="meta-cell"><span class="meta-label">runner</span><span class="meta-value">${escapeHtml(t.assigned_runner_id || t.runner_id || "")}</span></div>
          <div class="meta-cell"><span class="meta-label">model</span><span class="meta-value">${escapeHtml(t.model || "")}</span></div>
          <div class="meta-cell"><span class="meta-label">created_at</span><span class="meta-value">${escapeHtml(t.created_at || "")}</span></div>
          <div class="meta-cell"><span class="meta-label">updated_at</span><span class="meta-value">${escapeHtml(t.updated_at || "")}</span></div>
        </div>
        <div class="task-actions">
          <a href="#" onclick="showTask(${escapeHtml(t.id)});return false;">详情</a>
          <a href="${escapeHtml(t.log_url)}" target="_blank">log</a>
          <a href="${escapeHtml(t.result_url)}" target="_blank">result</a>
          <a href="${escapeHtml(t.diff_url)}" target="_blank">diff</a>
          <button class="danger" onclick="cancelTask(${escapeHtml(t.id)}, this)">取消</button>
        </div>
      </div>`).join("")
    : `<div class="empty-state">暂无任务。</div>`;
}

async function createTask() {
  const payload = {
    project_id: Number(document.getElementById("project").value),
    prompt: document.getElementById("prompt").value,
    task_type: document.getElementById("taskType").value,
    timeout_seconds: Number(document.getElementById("timeoutSeconds").value) || 7200,
    assigned_runner_id: document.getElementById("runner").value || null,
    model: document.getElementById("model").value || null,
    reasoning_effort: document.getElementById("reasoning").value || null,
    sandbox: document.getElementById("sandbox").value || "workspace-write",
  };
  const task = await api("/tasks", {method: "POST", headers: headers(true), body: JSON.stringify(payload)});
  document.getElementById("prompt").value = "";
  await loadAll();
  await showTask(task.id);
  showToast(`已创建任务 #${task.id}`, "success");
}

async function showTask(id) {
  const task = await api(`/tasks/${id}`, {headers: headers()});
  document.getElementById("taskDetail").innerHTML = `
    <div class="task-detail-grid">
      <div class="detail-section">
        <h3>基本信息</h3>
        <div class="task-card-header">
          <div>
            <div class="task-title">#${escapeHtml(task.id)} ${escapeHtml(task.task_type || "")}</div>
            <span class="muted">project=${escapeHtml(task.project_id)}</span>
          </div>
          ${statusBadge(task.status)}
        </div>
      </div>
      <div class="detail-section">
        <h3>参数</h3>
        <div class="meta-grid">
          <div class="meta-cell"><span class="meta-label">runner</span><span class="meta-value">${escapeHtml(task.assigned_runner_id || task.runner_id || "")}</span></div>
          <div class="meta-cell"><span class="meta-label">model</span><span class="meta-value">${escapeHtml(task.model || "")}</span></div>
          <div class="meta-cell"><span class="meta-label">reasoning_effort</span><span class="meta-value">${escapeHtml(task.reasoning_effort || "")}</span></div>
          <div class="meta-cell"><span class="meta-label">sandbox</span><span class="meta-value">${escapeHtml(task.sandbox || "")}</span></div>
          <div class="meta-cell"><span class="meta-label">timeout_seconds</span><span class="meta-value">${escapeHtml(task.timeout_seconds || "")}</span></div>
          <div class="meta-cell"><span class="meta-label">updated_at</span><span class="meta-value">${escapeHtml(task.updated_at || "")}</span></div>
        </div>
      </div>
      <div class="detail-section">
        <h3>操作链接</h3>
        <div class="task-actions">
          <a href="${escapeHtml(task.log_url)}" target="_blank">log</a>
          <a href="${escapeHtml(task.result_url)}" target="_blank">result</a>
          <a href="${escapeHtml(task.diff_url)}" target="_blank">diff</a>
          <button class="danger" onclick="cancelTask(${escapeHtml(task.id)}, this)">取消</button>
        </div>
      </div>
      <div class="detail-section">
        <h3>log/result 预览</h3>
        <p class="muted">优先展示 log 预览；result 和 diff 保持链接打开，本版本不做 diff UI。</p>
        <pre id="taskPreview" class="preview-block"></pre>
      </div>
    </div>`;
  try {
    const logText = await api(task.log_url, {headers: headers()});
    document.getElementById("taskPreview").textContent = logText;
    log(logText);
  } catch (err) {
    const errorText = String(err);
    document.getElementById("taskPreview").textContent = errorText;
    log(errorText);
  }
}

async function cancelTask(id, button = null) {
  if (!confirm(`确认取消任务 #${id}？`)) return null;
  return withButtonLoading(button, "处理中...", async () => {
    await api(`/tasks/${id}/cancel`, {method: "POST", headers: headers()});
    await loadAll();
    await showTask(id);
    showToast(`已请求取消任务 #${id}`, "warning");
  });
}

async function checkAppServerBridge() {
  const health = await api("/app-server-bridge/health", {headers: headers()});
  document.getElementById("appBridgeStatus").innerHTML =
    `status=${escapeHtml(health.status || "")} mode=${escapeHtml(health.mode || "")} sandbox=${escapeHtml(health.sandbox || "")} threads=${escapeHtml(health.threads ?? "")}`;
  appLog(JSON.stringify(health, null, 2));
  showToast("Bridge 检查完成", "success");
}

async function loadAppThreadList() {
  const params = new URLSearchParams({limit: "20"});
  const statusFilter = document.getElementById("appThreadStatusFilter").value;
  if (statusFilter) params.set("status", statusFilter);
  if (document.getElementById("appIncludeArchived").checked) params.set("include_archived", "true");
  const appThreads = await api(`/app-threads?${params.toString()}`, {headers: headers()});
  renderAppThreads(appThreads);
  return appThreads;
}

function updateSelectedAppThreadDisplay() {
  const target = document.getElementById("appThreadCurrent");
  if (!selectedAppThreadId) {
    target.innerHTML = `<div class="empty-state">当前 App Thread: 未选择。请先新建或从 AppThread 列表选择。</div>`;
    updateAppActionState();
    return;
  }
  const title = selectedAppThread ? selectedAppThread.title : "";
  const status = selectedAppThread ? selectedAppThread.status : "";
  const turnCount = selectedAppThread ? selectedAppThread.turn_count : "";
  const latestFinal = selectedAppThread ? selectedAppThread.latest_assistant_final : "";
  const lastError = selectedAppThread ? selectedAppThread.last_error : "";
  const updatedAt = selectedAppThread ? selectedAppThread.updated_at : "";
  target.innerHTML = `
    <div class="app-current-layout">
      <div>
        <div class="app-current-title">${escapeHtml(title || "App Thread")}</div>
        <div class="app-current-meta">
          <span class="muted">id=#${escapeHtml(selectedAppThreadId)}</span>
          ${statusBadge(status)}
          <span class="muted">turn_count=${escapeHtml(turnCount ?? 0)}</span>
        </div>
        <span class="muted">updated=${escapeHtml(updatedAt || "")}</span>
        <div class="final-preview">
          <strong>latest final preview</strong><br>
          ${latestFinal ? escapeHtml(shortText(latestFinal, 260)) : `<span class="muted">暂无 assistant final</span>`}
        </div>
        ${lastError ? `<div class="error-line">last_error=${escapeHtml(lastError)}</div>` : ""}
      </div>
    </div>`;
  updateAppActionState();
}

function shortText(value, maxLength = 180) {
  const text = String(value || "");
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength)}...`;
}

function normalizedStatus(status) {
  return String(status || "").toUpperCase();
}

function statusClass(status) {
  const normalized = normalizedStatus(status).toLowerCase();
  return normalized || "unknown";
}

function statusBadge(status) {
  const normalized = normalizedStatus(status);
  const labelMap = {
    ACTIVE: "正常",
    SUCCESS: "成功",
    PENDING: "等待",
    RUNNING: "运行中",
    ERROR: "错误",
    FAILED: "失败",
    CLOSED: "已关闭",
    CANCELLED: "已取消",
    WARNING: "警告",
  };
  const classMap = {
    ACTIVE: "active",
    SUCCESS: "success",
    PENDING: "pending",
    RUNNING: "running",
    ERROR: "error",
    FAILED: "failed",
    CLOSED: "closed",
    CANCELLED: "cancelled",
    WARNING: "warning",
  };
  const label = labelMap[normalized] || normalized || "UNKNOWN";
  const className = classMap[normalized] || "";
  return `<span class="badge ${escapeHtml(className)}">${escapeHtml(normalized)} ${escapeHtml(label)}</span>`;
}

function updateAppActionState() {
  const sendButton = document.getElementById("sendAppTurn");
  const asyncButton = document.getElementById("sendAsyncAppTurn");
  const threadButtons = [
    "loadAppTurns",
    "refreshAppTurn",
    "cancelAppTurn",
    "loadAppFinal",
    "loadAppEvents",
    "reopenAppThread",
    "closeAppThread",
  ];
  const status = selectedAppThread ? selectedAppThread.status : "";
  const hasThread = Boolean(selectedAppThreadId);
  sendButton.disabled = !hasThread || status === "CLOSED";
  asyncButton.disabled = !hasThread || status === "CLOSED";
  threadButtons.forEach(id => {
    const button = document.getElementById(id);
    if (button) button.disabled = !hasThread;
  });
  if (status === "CLOSED") {
    document.getElementById("appWaiting").textContent = "当前 App Thread 已关闭，请先重开。";
  } else if (["当前 App Thread 已关闭，请先重开。", ""].includes(document.getElementById("appWaiting").textContent)) {
    document.getElementById("appWaiting").textContent = "";
  }
}

function renderAppTurnStatus(turn) {
  selectedAppTurnId = turn.id;
  const status = normalizedStatus(turn.status);
  const isRunning = ["PENDING", "RUNNING"].includes(status);
  const message = turn.assistant_final || turn.error_message || "";
  const messageHtml = message
    ? `<span>${escapeHtml(message)}</span>`
    : `<span class="muted">等待 assistant_final</span>`;
  document.getElementById("appTurnStatus").innerHTML = `
    <strong>当前 App Turn: #${escapeHtml(turn.id)}</strong> ${statusBadge(turn.status)}<br>
    <span class="muted">duration_seconds=${escapeHtml(turn.duration_seconds ?? "")} bridge_turn=${escapeHtml(turn.bridge_turn_id || "")}</span><br>
    ${isRunning ? `<div class="loading-card">${escapeHtml(APP_WAITING_TEXT)}</div>` : ""}
    ${messageHtml}`;
}

function renderAppThreads(appThreads) {
  appThreadsCache = appThreads;
  if (selectedAppThreadId) {
    const listedThread = appThreads.find(t => t.id === selectedAppThreadId);
    if (listedThread) selectedAppThread = listedThread;
  }
  updateSelectedAppThreadDisplay();
  if (!appThreads.length) {
    document.getElementById("appThreads").innerHTML = `<div class="empty-state">暂无 AppThread。</div>`;
    return;
  }
  document.getElementById("appThreads").innerHTML = appThreads.map(t => `
    <div class="${selectedAppThreadId === t.id ? "item selected" : "item"}">
      <strong>#${escapeHtml(t.id)}</strong> ${escapeHtml(t.title)}<br>
      ${String(t.title || "").startsWith("[archived]") ? `<span class="muted">archived</span><br>` : ""}
      ${statusBadge(t.status)}<br>
      <span class="muted">project=${escapeHtml(t.project_id)} status=${escapeHtml(t.status)} turns=${escapeHtml(t.turn_count)} updated=${escapeHtml(t.updated_at)}</span><br>
      <span>${escapeHtml(shortText(t.latest_assistant_final || "", 160))}</span>
      ${t.last_error ? `<br><span class="muted">last_error=${escapeHtml(t.last_error)}</span>` : ""}
      <div class="links">
        <a href="#" onclick="selectAppThread(${escapeHtml(t.id)});return false;">选择</a>
      </div>
    </div>`).join("");
}

async function createAppThread() {
  const payload = {
    project_id: Number(document.getElementById("project").value),
    title: document.getElementById("appThreadTitle").value || null,
  };
  const appThread = await api("/app-threads", {method: "POST", headers: headers(true), body: JSON.stringify(payload)});
  selectedAppThreadId = appThread.id;
  selectedAppThread = appThread;
  await loadAll();
  showToast(`已创建 App Thread #${appThread.id}`, "success");
  appLog(`已创建 App Thread #${appThread.id}`);
}

function selectAppThread(id) {
  selectedAppThreadId = id;
  selectedAppThread = appThreadsCache.find(t => t.id === id) || null;
  updateSelectedAppThreadDisplay();
  renderAppThreads(appThreadsCache);
  loadAppTurns().catch(err => {
    showToast(String(err), "error");
    appLog(String(err));
  });
}

async function sendAppTurn() {
  if (!selectedAppThreadId) throw new Error("请先选择 App Thread");
  if (selectedAppThread && selectedAppThread.status === "CLOSED") {
    throw new Error("当前 App Thread 已关闭，请先重开。");
  }
  const message = document.getElementById("appMessage").value.trim();
  if (!message) throw new Error("App Turn message 不能为空");
  const waiting = document.getElementById("appWaiting");
  waiting.textContent = APP_WAITING_TEXT;
  appLog(APP_WAITING_TEXT);
  try {
    const appTurn = await api(`/app-threads/${selectedAppThreadId}/turns`, {
      method: "POST",
      headers: headers(true),
      body: JSON.stringify({message}),
    });
    document.getElementById("appMessage").value = "";
    await loadAppThreadList();
    await loadAppTurns();
    await loadAppFinal();
    renderAppTurnStatus(appTurn);
    showToast(`App Turn #${appTurn.id} ${appTurn.status}`, "success");
    appLog(`App Turn #${appTurn.id} ${appTurn.status}`);
  } finally {
    waiting.textContent = "";
  }
}

async function sendAsyncAppTurn() {
  if (!selectedAppThreadId) throw new Error("请先选择 App Thread");
  if (selectedAppThread && selectedAppThread.status === "CLOSED") {
    throw new Error("当前 App Thread 已关闭，请先重开。");
  }
  const message = document.getElementById("appMessage").value.trim();
  if (!message) throw new Error("App Turn message 不能为空");
  const waiting = document.getElementById("appWaiting");
  waiting.textContent = APP_WAITING_TEXT;
  try {
    const appTurn = await api(`/app-threads/${selectedAppThreadId}/turns/async`, {
      method: "POST",
      headers: headers(true),
      body: JSON.stringify({message}),
    });
    document.getElementById("appMessage").value = "";
    await loadAppThreadList();
    await loadAppTurns();
    renderAppTurnStatus(appTurn);
    showToast(`已提交 App Turn #${appTurn.id}`, "info");
    appLog(`已提交 App Turn #${appTurn.id}，状态 ${appTurn.status}`);
    startAppTurnPolling(appTurn.id);
  } catch (err) {
    waiting.textContent = "";
    throw err;
  }
}

function startAppTurnPolling(turnId) {
  stopAppTurnPolling();
  selectedAppTurnId = turnId;
  appTurnPollTimer = setInterval(() => {
    refreshCurrentAppTurn().catch(err => {
      stopAppTurnPolling();
      document.getElementById("appWaiting").textContent = "";
      showToast(String(err), "error");
      appLog(String(err));
    });
  }, 2000);
}

function stopAppTurnPolling() {
  if (appTurnPollTimer) {
    clearInterval(appTurnPollTimer);
    appTurnPollTimer = null;
  }
}

async function refreshCurrentAppTurn() {
  if (!selectedAppTurnId) throw new Error("请先提交或选择 App Turn");
  const turn = await api(`/app-turns/${selectedAppTurnId}`, {headers: headers()});
  renderAppTurnStatus(turn);
  if (APP_TURN_TERMINAL_STATUSES.includes(turn.status)) {
    stopAppTurnPolling();
    await loadAppTurns();
    await loadAppThreadList();
    document.getElementById("appWaiting").textContent = "";
    if (turn.status === "SUCCESS") {
      await loadAppFinal();
      showToast("App Turn 已完成", "success");
    } else {
      showToast(turn.error_message || "App Turn failed", turn.status === "CANCELLED" ? "warning" : "error");
      appLog(turn.error_message || "App Turn failed");
    }
  } else {
    document.getElementById("appWaiting").textContent = APP_WAITING_TEXT;
    await loadAppTurns();
  }
  return turn;
}

async function cancelCurrentAppTurn() {
  if (!selectedAppTurnId) throw new Error("请先提交或选择 App Turn");
  if (!confirm(`确认取消 App Turn #${selectedAppTurnId}？`)) return null;
  stopAppTurnPolling();
  const turn = await api(`/app-turns/${selectedAppTurnId}/cancel`, {
    method: "POST",
    headers: headers(),
  });
  renderAppTurnStatus(turn);
  await loadAppTurns();
  await loadAppThreadList();
  document.getElementById("appWaiting").textContent = "";
  showToast(`已取消 App Turn #${turn.id}`, "warning");
  appLog(`已取消 App Turn #${turn.id}`);
  return turn;
}

async function reopenAppThread() {
  if (!selectedAppThreadId) throw new Error("请先选择 App Thread");
  const reopened = await api(`/app-threads/${selectedAppThreadId}/reopen`, {
    method: "POST",
    headers: headers(),
  });
  selectedAppThread = reopened;
  await loadAppThreadList();
  updateSelectedAppThreadDisplay();
  showToast("已重开 App Thread", "success");
  appLog(`已重开 App Thread，新 bridge_thread_id=${reopened.bridge_thread_id || ""}`);
}

async function loadAppTurns() {
  if (!selectedAppThreadId) throw new Error("请先选择 App Thread");
  const turns = await api(`/app-threads/${selectedAppThreadId}/turns?limit=100`, {headers: headers()});
  appTurnsCache = turns;
  document.getElementById("appTurns").innerHTML = turns.length
    ? turns.map(renderAppTurnConversation).join("")
    : `<div class="empty-state">暂无 AppTurn。请在底部输入消息后发送。</div>`;
}

function selectAppTurn(turnId) {
  const turn = appTurnsCache.find(item => item.id === turnId);
  if (!turn) return;
  renderAppTurnStatus(turn);
}

function renderAppTurnConversation(turn) {
  const status = normalizedStatus(turn.status);
  const pending = ["PENDING", "RUNNING"].includes(status);
  const failed = ["FAILED", "ERROR"].includes(status);
  const cancelled = status === "CANCELLED";
  const assistantText = turn.assistant_final || turn.error_message || "";
  const assistantFallback = pending
    ? APP_WAITING_TEXT
    : cancelled
      ? "App Turn 已取消。"
      : failed
        ? "App Turn 失败，暂无错误详情。"
        : "暂无 assistant_final";
  const assistantBody = assistantText || assistantFallback;
  const eventSummary = renderEventSummaryInline(turn.event_summary);
  return `
    <div class="chat-turn" onclick="selectAppTurn(${escapeHtml(turn.id)})">
      <div class="bubble-row user">
        <div class="bubble user">
          <div class="muted">user_message · #${escapeHtml(turn.id)}</div>
          ${escapeHtml(turn.user_message || "")}
        </div>
      </div>
      <div class="bubble-row assistant">
        <div class="bubble assistant ${escapeHtml(statusClass(turn.status))}">
          <div class="turn-meta">
            ${statusBadge(turn.status)}
            <span class="muted">created=${escapeHtml(turn.created_at)}</span>
            <span class="muted">duration_seconds=${escapeHtml(turn.duration_seconds ?? "")}</span>
          </div>
          ${pending ? `<div class="loading-card">${escapeHtml(APP_WAITING_TEXT)}</div>` : ""}
          ${eventSummary}
          ${escapeHtml(assistantBody)}
        </div>
      </div>
    </div>`;
}

async function loadAppFinal() {
  if (!selectedAppThreadId) throw new Error("请先选择 App Thread");
  const final = await api(`/app-threads/${selectedAppThreadId}/final`, {headers: headers()});
  document.getElementById("appThreadFinal").innerHTML =
    `<strong>assistant_final</strong><br>${final.assistant_final ? escapeHtml(final.assistant_final) : `<span class="muted">暂无 assistant_final</span>`}`;
  return final;
}

async function loadAppEvents() {
  if (!selectedAppThreadId) throw new Error("请先选择 App Thread");
  const events = await api(`/app-threads/${selectedAppThreadId}/events`, {headers: headers()});
  renderAppEventsSummary(events);
  appLog(JSON.stringify(events, null, 2));
  return events;
}

function renderEventSummaryInline(summary) {
  if (!summary) return "";
  return `<span class="muted">events=${escapeHtml(summary.total_events ?? "")} has_error=${escapeHtml(summary.has_error ?? "")}</span><br>`;
}

function renderAppEventsSummary(events) {
  const summary = events ? events.event_summary : null;
  if (!summary) {
    document.getElementById("appEventsSummary").innerHTML = `<span class="muted">无事件摘要</span>`;
    return;
  }
  const eventCounts = summary.event_type_counts || {};
  const errors = Array.isArray(summary.errors) ? summary.errors : [];
  document.getElementById("appEventsSummary").innerHTML = `
    <div><strong>total_events</strong><br>${escapeHtml(summary.total_events ?? 0)}</div>
    <div><strong>has_error</strong><br>${escapeHtml(summary.has_error ?? false)}</div>
    <div><strong>event_type_counts</strong><br>${escapeHtml(JSON.stringify(eventCounts))}</div>
    <div><strong>assistant_text_preview</strong><br>${escapeHtml(summary.assistant_text_preview || "")}</div>
    <div><strong>errors</strong><br>${escapeHtml(JSON.stringify(errors))}</div>
    <span class="muted">latest_turn_id=${escapeHtml(events.latest_turn_id ?? "")}</span>`;
}

async function recoverStaleAppTurns() {
  if (!confirm("确认将所有 PENDING/RUNNING AppTurn 标记为 FAILED？")) return null;
  const result = await api("/app-turns/recover-stale", {method: "POST", headers: headers()});
  appLog(JSON.stringify(result, null, 2));
  await loadAppThreadList();
  if (selectedAppThreadId) {
    await loadAppTurns();
  }
  showToast(`已恢复 ${result.recovered_count ?? 0} 个 stale turn`, "success");
  return result;
}

async function cleanupAppThreads(status) {
  if (status === "CLOSED" && !confirm(`确认将 CLOSED AppThread 标记为 archived？`)) return null;
  if (status === "ERROR" && !confirm(`确认将 ERROR AppThread 标记为 archived？`)) return null;
  const result = await api("/app-threads/cleanup", {
    method: "POST",
    headers: headers(true),
    body: JSON.stringify({status, limit: 50}),
  });
  appLog(JSON.stringify(result, null, 2));
  await loadAppThreadList();
  showToast(`已清理 ${result.archived_count ?? 0} 个 ${status} AppThread`, "success");
  return result;
}

async function closeAppThread() {
  if (!selectedAppThreadId) throw new Error("请先选择 App Thread");
  if (!confirm("确认关闭当前 App Thread？")) return;
  await api(`/app-threads/${selectedAppThreadId}`, {method: "DELETE", headers: headers()});
  selectedAppThreadId = null;
  selectedAppThread = null;
  selectedAppTurnId = null;
  stopAppTurnPolling();
  document.getElementById("appThreadFinal").textContent = "";
  document.getElementById("appEventsSummary").textContent = "";
  document.getElementById("appTurnStatus").textContent = "";
  document.getElementById("appTurns").innerHTML = "";
  showToast("已关闭 App Thread", "warning");
  appLog("已关闭 App Thread");
  await loadAll();
}

document.querySelectorAll("[data-tab]").forEach(button => {
  button.onclick = () => switchTab(button.dataset.tab);
});
document.getElementById("saveToken").onclick = () => withButtonLoading("saveToken", "处理中...", async () => {
  localStorage.setItem("apiToken", tokenInput.value);
  await loadAll();
  showToast("Token 已保存", "success");
});
document.getElementById("createTask").onclick = () => withButtonLoading("createTask", "处理中...", createTask);
document.getElementById("refresh").onclick = () => withButtonLoading("refresh", "处理中...", async () => {
  await loadAll();
  showToast("已刷新", "success");
});
document.getElementById("refreshRunners").onclick = () => withButtonLoading("refreshRunners", "处理中...", async () => {
  const runners = await api("/runners", {headers: headers()});
  renderRunners(runners);
  showToast("Runner 已刷新", "success");
});
document.getElementById("clearOutput").onclick = () => log("");
document.getElementById("checkAppBridge").onclick = () => withButtonLoading("checkAppBridge", "处理中...", checkAppServerBridge);
document.getElementById("refreshAppThreads").onclick = () => withButtonLoading("refreshAppThreads", "处理中...", async () => {
  await loadAppThreadList();
  showToast("App Threads 已刷新", "success");
});
document.getElementById("appThreadStatusFilter").onchange = () => loadAppThreadList().catch(err => {
  showToast(String(err), "error");
  appLog(String(err));
});
document.getElementById("appIncludeArchived").onchange = () => loadAppThreadList().catch(err => {
  showToast(String(err), "error");
  appLog(String(err));
});
document.getElementById("cleanupClosedThreads").onclick = () => withButtonLoading("cleanupClosedThreads", "处理中...", () => cleanupAppThreads("CLOSED"));
document.getElementById("cleanupErrorThreads").onclick = () => withButtonLoading("cleanupErrorThreads", "处理中...", () => cleanupAppThreads("ERROR"));
document.getElementById("recoverStaleTurns").onclick = () => withButtonLoading("recoverStaleTurns", "处理中...", recoverStaleAppTurns);
document.getElementById("createAppThread").onclick = () => withButtonLoading("createAppThread", "处理中...", createAppThread);
document.getElementById("sendAppTurn").onclick = () => withButtonLoading("sendAppTurn", "处理中...", sendAppTurn);
document.getElementById("sendAsyncAppTurn").onclick = () => withButtonLoading("sendAsyncAppTurn", "处理中...", sendAsyncAppTurn);
document.getElementById("loadAppTurns").onclick = () => withButtonLoading("loadAppTurns", "处理中...", async () => {
  await loadAppTurns();
  showToast("Turns 已刷新", "success");
});
document.getElementById("refreshAppTurn").onclick = () => withButtonLoading("refreshAppTurn", "处理中...", refreshCurrentAppTurn);
document.getElementById("cancelAppTurn").onclick = () => withButtonLoading("cancelAppTurn", "处理中...", cancelCurrentAppTurn);
document.getElementById("loadAppFinal").onclick = () => withButtonLoading("loadAppFinal", "处理中...", async () => {
  await loadAppFinal();
  showToast("Final 已刷新", "success");
});
document.getElementById("loadAppEvents").onclick = () => withButtonLoading("loadAppEvents", "处理中...", async () => {
  await loadAppEvents();
  showToast("Events 已刷新", "success");
});
document.getElementById("reopenAppThread").onclick = () => withButtonLoading("reopenAppThread", "处理中...", reopenAppThread);
document.getElementById("closeAppThread").onclick = () => withButtonLoading("closeAppThread", "处理中...", closeAppThread);
loadAll().catch(err => {
  showToast(String(err), "error");
  log(String(err));
});
</script>
</body>"""
