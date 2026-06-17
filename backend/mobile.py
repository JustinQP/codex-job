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
    .links { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
    .links a { color: var(--primary); text-decoration: none; font-size: 13px; font-weight: 650; }
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
      <button id="createTask">提交任务</button>
      <p class="muted">主线 Runner/codex exec 任务链路。当前目标模式只提交一次受控任务。</p>
    </div>

    <div class="card">
      <div class="row">
        <button id="refresh" class="secondary">刷新任务</button>
        <button id="clearOutput" class="ghost">清空输出</button>
      </div>
    </div>

    <div class="card">
      <h2>最近任务</h2>
      <div id="tasks" class="stack"></div>
    </div>

    <div class="card">
      <h2>任务详情</h2>
      <div id="taskDetail" class="stack"></div>
      <details>
        <summary>调试输出</summary>
        <pre id="output"></pre>
      </details>
    </div>
  </section>

  <section id="tab-app" class="tab-page" data-tab-page="app">
    <div class="card">
      <h2>App Server 会话</h2>
      <p class="muted">App Server 会话为 sidecar POC：支持同步/异步 turn、轮询、本地取消、reopen、recover-stale、筛选与 archived 清理；不替代 Runner/codex exec 主链路。</p>
      <div class="row">
        <button id="checkAppBridge" class="secondary">检查 App Server Bridge</button>
        <button id="refreshAppThreads" class="secondary">刷新 App Threads</button>
      </div>
      <div id="appBridgeStatus" class="muted"></div>
    </div>

    <div class="card">
      <h2>当前 AppThread</h2>
      <div id="appThreadCurrent" class="item">当前 App Thread: 未选择</div>
      <label>App Thread 标题 <input id="appThreadTitle" placeholder="App Thread 标题"></label>
      <button id="createAppThread">创建 App Thread</button>
    </div>

    <div class="card">
      <h2>AppThread 列表</h2>
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
      <button id="recoverStaleTurns" class="secondary">恢复卡住的 App Turn</button>
      <div id="appThreads" class="stack"></div>
    </div>

    <div class="card">
      <h2>AppTurn 操作</h2>
      <label>App Turn Message <textarea id="appMessage" placeholder="发送到当前 App Thread 的消息"></textarea></label>
      <div id="appWaiting" class="muted"></div>
      <div class="row">
        <button id="sendAppTurn">发送 App Turn</button>
        <button id="sendAsyncAppTurn">异步发送 App Turn</button>
      </div>
      <div class="row">
        <button id="loadAppTurns" class="secondary">查看 Turns</button>
        <button id="refreshAppTurn" class="secondary">刷新当前 Turn</button>
      </div>
      <button id="cancelAppTurn" class="danger">取消当前 Turn</button>
      <div class="row">
        <button id="loadAppFinal" class="secondary">查看 App Final</button>
        <button id="loadAppEvents" class="secondary">查看 App Events</button>
      </div>
      <div class="row">
        <button id="reopenAppThread" class="secondary">重开当前 App Thread</button>
        <button id="closeAppThread" class="danger">关闭当前 App Thread</button>
      </div>
      <div id="appThreadFinal" class="item"></div>
      <div id="appEventsSummary" class="item"></div>
      <div id="appTurnStatus" class="item"></div>
      <div id="appTurns" class="stack"></div>
      <details>
        <summary>调试输出</summary>
        <pre id="appOutput"></pre>
      </details>
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
        <span class="muted">v1.1.0 mobile layout POC</span>
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
  document.getElementById("tasks").innerHTML = tasks.map(t => `
    <div class="item">
      <strong>#${escapeHtml(t.id)}</strong> ${statusBadge(t.status)} ${escapeHtml(t.task_type)}<br>
      <span class="muted">project=${escapeHtml(t.project_id)} runner=${escapeHtml(t.assigned_runner_id || t.runner_id || "")} model=${escapeHtml(t.model || "")}</span>
      <div class="links">
        <a href="#" onclick="showTask(${escapeHtml(t.id)});return false;">详情</a>
        <a href="${escapeHtml(t.log_url)}" target="_blank">log</a>
        <a href="${escapeHtml(t.result_url)}" target="_blank">result</a>
        <a href="${escapeHtml(t.diff_url)}" target="_blank">diff</a>
        <a href="#" onclick="cancelTask(${escapeHtml(t.id)}, this);return false;">取消</a>
      </div>
    </div>`).join("");
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
    <div class="item">
      <strong>#${escapeHtml(task.id)}</strong> ${statusBadge(task.status)}<br>
      <span class="muted">model=${escapeHtml(task.model || "")} reasoning=${escapeHtml(task.reasoning_effort || "")} sandbox=${escapeHtml(task.sandbox || "")}</span>
      <div class="links">
        <a href="${escapeHtml(task.log_url)}" target="_blank">log</a>
        <a href="${escapeHtml(task.result_url)}" target="_blank">result</a>
        <a href="${escapeHtml(task.diff_url)}" target="_blank">diff</a>
      </div>
      <button class="danger" onclick="cancelTask(${escapeHtml(task.id)}, this)">取消任务</button>
    </div>`;
  try {
    log(await api(task.log_url, {headers: headers()}));
  } catch (err) {
    log(String(err));
  }
}

async function cancelTask(id, button = null) {
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
    target.textContent = "当前 App Thread: 未选择";
    updateAppActionState();
    return;
  }
  const title = selectedAppThread ? selectedAppThread.title : "";
  const status = selectedAppThread ? selectedAppThread.status : "";
  const lastError = selectedAppThread ? selectedAppThread.last_error : "";
  target.innerHTML =
    `当前 App Thread: #${escapeHtml(selectedAppThreadId)} ${escapeHtml(title)} ${statusBadge(status)} ${lastError ? "last_error=" + escapeHtml(lastError) : ""}`;
  updateAppActionState();
}

function statusBadge(status) {
  const normalized = String(status || "").toUpperCase();
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
  const status = selectedAppThread ? selectedAppThread.status : "";
  sendButton.disabled = status === "CLOSED";
  asyncButton.disabled = status === "CLOSED";
  if (status === "CLOSED") {
    document.getElementById("appWaiting").textContent = "当前 App Thread 已关闭，请先重开。";
  } else if (document.getElementById("appWaiting").textContent === "当前 App Thread 已关闭，请先重开。") {
    document.getElementById("appWaiting").textContent = "";
  }
}

function renderAppTurnStatus(turn) {
  selectedAppTurnId = turn.id;
  document.getElementById("appTurnStatus").innerHTML = `
    <strong>当前 App Turn: #${escapeHtml(turn.id)}</strong> ${statusBadge(turn.status)}<br>
    <span class="muted">duration_seconds=${escapeHtml(turn.duration_seconds ?? "")} bridge_turn=${escapeHtml(turn.bridge_turn_id || "")}</span><br>
    <span>${escapeHtml(turn.assistant_final || turn.error_message || "")}</span>`;
}

function renderAppThreads(appThreads) {
  appThreadsCache = appThreads;
  if (selectedAppThreadId && !appThreads.some(t => t.id === selectedAppThreadId)) {
    selectedAppThreadId = null;
    selectedAppThread = null;
  } else if (selectedAppThreadId) {
    selectedAppThread = appThreads.find(t => t.id === selectedAppThreadId) || selectedAppThread;
  }
  updateSelectedAppThreadDisplay();
  document.getElementById("appThreads").innerHTML = appThreads.map(t => `
    <div class="${selectedAppThreadId === t.id ? "item selected" : "item"}">
      <strong>#${escapeHtml(t.id)}</strong> ${escapeHtml(t.title)}<br>
      ${String(t.title || "").startsWith("[archived]") ? `<span class="muted">archived</span><br>` : ""}
      ${statusBadge(t.status)}<br>
      <span class="muted">project=${escapeHtml(t.project_id)} status=${escapeHtml(t.status)} turns=${escapeHtml(t.turn_count)} updated=${escapeHtml(t.updated_at)}</span><br>
      <span>${escapeHtml(t.latest_assistant_final || "")}</span>
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
  const appTurn = await api(`/app-threads/${selectedAppThreadId}/turns/async`, {
    method: "POST",
    headers: headers(true),
    body: JSON.stringify({message}),
  });
  document.getElementById("appMessage").value = "";
  renderAppTurnStatus(appTurn);
  showToast(`已提交 App Turn #${appTurn.id}`, "info");
  appLog(`已提交 App Turn #${appTurn.id}，状态 ${appTurn.status}`);
  startAppTurnPolling(appTurn.id);
}

function startAppTurnPolling(turnId) {
  stopAppTurnPolling();
  selectedAppTurnId = turnId;
  appTurnPollTimer = setInterval(() => {
    refreshCurrentAppTurn().catch(err => {
      stopAppTurnPolling();
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
    if (turn.status === "SUCCESS") {
      await loadAppFinal();
      showToast("App Turn 已完成", "success");
    } else {
      showToast(turn.error_message || "App Turn failed", turn.status === "CANCELLED" ? "warning" : "error");
      appLog(turn.error_message || "App Turn failed");
    }
  }
  return turn;
}

async function cancelCurrentAppTurn() {
  if (!selectedAppTurnId) throw new Error("请先提交或选择 App Turn");
  stopAppTurnPolling();
  const turn = await api(`/app-turns/${selectedAppTurnId}/cancel`, {
    method: "POST",
    headers: headers(),
  });
  renderAppTurnStatus(turn);
  await loadAppTurns();
  await loadAppThreadList();
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
  document.getElementById("appTurns").innerHTML = turns.map(t => `
    <div class="item">
      <strong>#${escapeHtml(t.id)}</strong> ${statusBadge(t.status)}<br>
      <span class="muted">created=${escapeHtml(t.created_at)} duration_seconds=${escapeHtml(t.duration_seconds ?? "")} bridge_turn=${escapeHtml(t.bridge_turn_id || "")}</span><br>
      ${renderEventSummaryInline(t.event_summary)}
      <span>${escapeHtml(t.assistant_final || t.error_message || "")}</span>
    </div>`).join("");
}

async function loadAppFinal() {
  if (!selectedAppThreadId) throw new Error("请先选择 App Thread");
  const final = await api(`/app-threads/${selectedAppThreadId}/final`, {headers: headers()});
  document.getElementById("appThreadFinal").innerHTML =
    `<strong>assistant_final</strong><br>${escapeHtml(final.assistant_final || "")}`;
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
    document.getElementById("appEventsSummary").innerHTML = `<strong>event_summary</strong><br><span class="muted">无事件摘要</span>`;
    return;
  }
  const eventCounts = summary.event_type_counts || {};
  const errors = Array.isArray(summary.errors) ? summary.errors : [];
  document.getElementById("appEventsSummary").innerHTML = `
    <strong>event_summary</strong><br>
    <span class="muted">latest_turn_id=${escapeHtml(events.latest_turn_id ?? "")}</span><br>
    total_events=${escapeHtml(summary.total_events ?? 0)}<br>
    has_error=${escapeHtml(summary.has_error ?? false)}<br>
    event_type_counts=${escapeHtml(JSON.stringify(eventCounts))}<br>
    assistant_text_preview=${escapeHtml(summary.assistant_text_preview || "")}<br>
    errors=${escapeHtml(JSON.stringify(errors))}`;
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
