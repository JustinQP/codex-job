from __future__ import annotations


def mobile_console() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Codex Mobile Console</title>
  <style>
    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f7fa; color: #1f2933; }
    header { position: sticky; top: 0; background: #111827; color: #fff; padding: 14px 16px; z-index: 1; }
    main { padding: 14px; display: grid; gap: 14px; }
    section { background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; }
    h1 { font-size: 18px; margin: 0; }
    h2 { font-size: 15px; margin: 0 0 10px; }
    label { display: grid; gap: 5px; margin: 8px 0; font-size: 13px; }
    input, select, textarea, button { font: inherit; box-sizing: border-box; width: 100%; }
    input, select, textarea { border: 1px solid #cbd5e1; border-radius: 6px; padding: 9px; background: #fff; }
    textarea { min-height: 120px; resize: vertical; }
    button { border: 0; border-radius: 6px; padding: 10px; background: #2563eb; color: #fff; }
    button.secondary { background: #64748b; }
    button.danger { background: #c2410c; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .stack { display: grid; gap: 8px; }
    .muted { color: #64748b; font-size: 12px; }
    .inline { display: flex; align-items: center; gap: 8px; }
    .inline input { width: auto; }
    .item { border-top: 1px solid #e5e7eb; padding: 9px 0; }
    .item:first-child { border-top: 0; }
    .item.selected { border-left: 4px solid #2563eb; padding-left: 8px; }
    .links { display: flex; gap: 8px; flex-wrap: wrap; }
    .links a { color: #2563eb; text-decoration: none; font-size: 13px; }
    .badge { display: inline-block; padding: 2px 6px; border-radius: 999px; font-size: 12px; background: #e5e7eb; }
    .badge.active { background: #dcfce7; color: #166534; }
    .badge.error { background: #fee2e2; color: #991b1b; }
    .badge.closed { background: #e5e7eb; color: #374151; }
    pre { white-space: pre-wrap; word-break: break-word; background: #0f172a; color: #e5e7eb; padding: 10px; border-radius: 6px; max-height: 260px; overflow: auto; }
  </style>
</head>
<body>
<header><h1>Codex Mobile Console</h1></header>
<main>
  <section>
    <h2>API Token</h2>
    <label>Token <input id="token" type="password" placeholder="X-API-Token"></label>
    <button id="saveToken" class="secondary">保存 Token</button>
    <p class="muted">Token 保存在当前浏览器 localStorage。</p>
  </section>

  <section>
    <h2>创建任务</h2>
    <label>项目 <select id="project"></select></label>
    <label>Runner <select id="runner"></select></label>
    <div class="row">
      <label>任务类型 <select id="taskType"></select></label>
      <label>Sandbox
        <select id="sandbox">
          <option value="workspace-write">workspace-write</option>
          <option value="read-only">read-only</option>
          <option value="danger-full-access">danger-full-access</option>
        </select>
      </label>
    </div>
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
    <label>Prompt <textarea id="prompt" placeholder="输入受控目标或 GOAL 任务"></textarea></label>
    <button id="createTask">提交任务</button>
    <p class="muted">当前目标模式只提交一次受控任务，不做无限自主迭代。</p>
  </section>

  <section>
    <div class="row">
      <button id="refresh" class="secondary">刷新</button>
      <button id="clearOutput" class="secondary">清空输出</button>
    </div>
  </section>

  <section>
    <h2>Runner</h2>
    <div id="runners" class="stack"></div>
  </section>

  <section>
    <h2>最近任务</h2>
    <div id="tasks" class="stack"></div>
  </section>

  <section>
    <h2>任务详情</h2>
    <div id="taskDetail"></div>
    <pre id="output"></pre>
  </section>

  <section>
    <h2>App Server 会话</h2>
    <div class="row">
      <button id="checkAppBridge" class="secondary">检查 App Server Bridge</button>
      <button id="refreshAppThreads" class="secondary">刷新 App Threads</button>
    </div>
    <div id="appBridgeStatus" class="muted"></div>
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
    <label>App Thread 标题 <input id="appThreadTitle" placeholder="App Thread 标题"></label>
    <button id="createAppThread">创建 App Thread</button>
    <div id="appThreadCurrent" class="muted">当前 App Thread: 未选择</div>
    <div id="appThreads" class="stack"></div>
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
    <button id="reopenAppThread" class="secondary">重开当前 App Thread</button>
    <button id="closeAppThread" class="danger">关闭当前 App Thread</button>
    <div id="appThreadFinal" class="item"></div>
    <div id="appEventsSummary" class="item"></div>
    <div id="appTurnStatus" class="item"></div>
    <div id="appTurns" class="stack"></div>
    <pre id="appOutput"></pre>
  </section>
</main>

<script>
const tokenInput = document.getElementById("token");
const output = document.getElementById("output");
const appOutput = document.getElementById("appOutput");
const APP_WAITING_TEXT = "正在等待 App Server 返回，请不要刷新页面。";
const APP_TURN_TERMINAL_STATUSES = ["SUCCESS", "FAILED", "CANCELLED"];
let selectedAppThreadId = null;
let selectedAppThread = null;
let selectedAppTurnId = null;
let appTurnPollTimer = null;
let appThreadsCache = [];
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
      <strong>${escapeHtml(r.runner_id)}</strong> ${escapeHtml(r.status)}<br>
      <span class="muted">${escapeHtml(r.hostname)} pid=${escapeHtml(r.pid)} models=${escapeHtml(r.supported_models || "")}</span>
    </div>`).join("");
}

function renderTasks(tasks) {
  document.getElementById("tasks").innerHTML = tasks.map(t => `
    <div class="item">
      <strong>#${escapeHtml(t.id)}</strong> ${escapeHtml(t.status)} ${escapeHtml(t.task_type)}<br>
      <span class="muted">project=${escapeHtml(t.project_id)} runner=${escapeHtml(t.assigned_runner_id || t.runner_id || "")} model=${escapeHtml(t.model || "")}</span>
      <div class="links">
        <a href="#" onclick="showTask(${escapeHtml(t.id)});return false;">详情</a>
        <a href="${escapeHtml(t.log_url)}" target="_blank">log</a>
        <a href="${escapeHtml(t.result_url)}" target="_blank">result</a>
        <a href="${escapeHtml(t.diff_url)}" target="_blank">diff</a>
      </div>
    </div>`).join("");
}

async function createTask() {
  const payload = {
    project_id: Number(document.getElementById("project").value),
    prompt: document.getElementById("prompt").value,
    task_type: document.getElementById("taskType").value,
    assigned_runner_id: document.getElementById("runner").value || null,
    model: document.getElementById("model").value || null,
    reasoning_effort: document.getElementById("reasoning").value || null,
    sandbox: document.getElementById("sandbox").value || "workspace-write",
  };
  const task = await api("/tasks", {method: "POST", headers: headers(true), body: JSON.stringify(payload)});
  document.getElementById("prompt").value = "";
  await loadAll();
  await showTask(task.id);
}

async function showTask(id) {
  const task = await api(`/tasks/${id}`, {headers: headers()});
  document.getElementById("taskDetail").innerHTML = `
    <div class="item">
      <strong>#${escapeHtml(task.id)}</strong> ${escapeHtml(task.status)}<br>
      <span class="muted">model=${escapeHtml(task.model || "")} reasoning=${escapeHtml(task.reasoning_effort || "")} sandbox=${escapeHtml(task.sandbox || "")}</span>
      <div class="links">
        <a href="${escapeHtml(task.log_url)}" target="_blank">log</a>
        <a href="${escapeHtml(task.result_url)}" target="_blank">result</a>
        <a href="${escapeHtml(task.diff_url)}" target="_blank">diff</a>
      </div>
      <button class="danger" onclick="cancelTask(${escapeHtml(task.id)})">取消任务</button>
    </div>`;
  try {
    log(await api(task.log_url, {headers: headers()}));
  } catch (err) {
    log(String(err));
  }
}

async function cancelTask(id) {
  await api(`/tasks/${id}/cancel`, {method: "POST", headers: headers()});
  await loadAll();
  await showTask(id);
}

async function checkAppServerBridge() {
  const health = await api("/app-server-bridge/health", {headers: headers()});
  document.getElementById("appBridgeStatus").innerHTML =
    `status=${escapeHtml(health.status || "")} mode=${escapeHtml(health.mode || "")} sandbox=${escapeHtml(health.sandbox || "")} threads=${escapeHtml(health.threads ?? "")}`;
  appLog(JSON.stringify(health, null, 2));
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
  const labelMap = {ACTIVE: "正常", ERROR: "错误", CLOSED: "已关闭"};
  const classMap = {ACTIVE: "active", ERROR: "error", CLOSED: "closed"};
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
    <strong>当前 App Turn: #${escapeHtml(turn.id)}</strong> ${escapeHtml(turn.status)}<br>
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
  appLog(`已创建 App Thread #${appThread.id}`);
}

function selectAppThread(id) {
  selectedAppThreadId = id;
  selectedAppThread = appThreadsCache.find(t => t.id === id) || null;
  updateSelectedAppThreadDisplay();
  renderAppThreads(appThreadsCache);
  loadAppTurns().catch(err => appLog(String(err)));
}

async function sendAppTurn() {
  if (!selectedAppThreadId) throw new Error("请先选择 App Thread");
  if (selectedAppThread && selectedAppThread.status === "CLOSED") {
    throw new Error("当前 App Thread 已关闭，请先重开。");
  }
  const message = document.getElementById("appMessage").value.trim();
  if (!message) throw new Error("App Turn message 不能为空");
  const sendButton = document.getElementById("sendAppTurn");
  const waiting = document.getElementById("appWaiting");
  sendButton.disabled = true;
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
    appLog(`App Turn #${appTurn.id} ${appTurn.status}`);
  } finally {
    sendButton.disabled = false;
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
  appLog(`已提交 App Turn #${appTurn.id}，状态 ${appTurn.status}`);
  startAppTurnPolling(appTurn.id);
}

function startAppTurnPolling(turnId) {
  stopAppTurnPolling();
  selectedAppTurnId = turnId;
  appTurnPollTimer = setInterval(() => {
    refreshCurrentAppTurn().catch(err => {
      stopAppTurnPolling();
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
    } else {
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
  appLog(`已重开 App Thread，新 bridge_thread_id=${reopened.bridge_thread_id || ""}`);
}

async function loadAppTurns() {
  if (!selectedAppThreadId) throw new Error("请先选择 App Thread");
  const turns = await api(`/app-threads/${selectedAppThreadId}/turns?limit=100`, {headers: headers()});
  document.getElementById("appTurns").innerHTML = turns.map(t => `
    <div class="item">
      <strong>#${escapeHtml(t.id)}</strong> ${escapeHtml(t.status)}<br>
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
    document.getElementById("appEventsSummary").innerHTML = "<strong>event_summary</strong><br><span class=\"muted\">无事件摘要</span>";
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
  const result = await api("/app-turns/recover-stale", {method: "POST", headers: headers()});
  appLog(JSON.stringify(result, null, 2));
  await loadAppThreadList();
  if (selectedAppThreadId) {
    await loadAppTurns();
  }
  return result;
}

async function cleanupAppThreads(status) {
  const result = await api("/app-threads/cleanup", {
    method: "POST",
    headers: headers(true),
    body: JSON.stringify({status, limit: 50}),
  });
  appLog(JSON.stringify(result, null, 2));
  await loadAppThreadList();
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
  appLog("已关闭 App Thread");
  await loadAll();
}

document.getElementById("saveToken").onclick = () => {
  localStorage.setItem("apiToken", tokenInput.value);
  loadAll().catch(err => log(String(err)));
};
document.getElementById("createTask").onclick = () => createTask().catch(err => log(String(err)));
document.getElementById("refresh").onclick = () => loadAll().catch(err => log(String(err)));
document.getElementById("clearOutput").onclick = () => log("");
document.getElementById("checkAppBridge").onclick = () => checkAppServerBridge().catch(err => appLog(String(err)));
document.getElementById("refreshAppThreads").onclick = () => loadAppThreadList().catch(err => appLog(String(err)));
document.getElementById("appThreadStatusFilter").onchange = () => loadAppThreadList().catch(err => appLog(String(err)));
document.getElementById("appIncludeArchived").onchange = () => loadAppThreadList().catch(err => appLog(String(err)));
document.getElementById("cleanupClosedThreads").onclick = () => cleanupAppThreads("CLOSED").catch(err => appLog(String(err)));
document.getElementById("cleanupErrorThreads").onclick = () => cleanupAppThreads("ERROR").catch(err => appLog(String(err)));
document.getElementById("recoverStaleTurns").onclick = () => recoverStaleAppTurns().catch(err => appLog(String(err)));
document.getElementById("createAppThread").onclick = () => createAppThread().catch(err => appLog(String(err)));
document.getElementById("sendAppTurn").onclick = () => sendAppTurn().catch(err => appLog(String(err)));
document.getElementById("sendAsyncAppTurn").onclick = () => sendAsyncAppTurn().catch(err => appLog(String(err)));
document.getElementById("loadAppTurns").onclick = () => loadAppTurns().catch(err => appLog(String(err)));
document.getElementById("refreshAppTurn").onclick = () => refreshCurrentAppTurn().catch(err => appLog(String(err)));
document.getElementById("cancelAppTurn").onclick = () => cancelCurrentAppTurn().catch(err => appLog(String(err)));
document.getElementById("loadAppFinal").onclick = () => loadAppFinal().catch(err => appLog(String(err)));
document.getElementById("loadAppEvents").onclick = () => loadAppEvents().catch(err => appLog(String(err)));
document.getElementById("reopenAppThread").onclick = () => reopenAppThread().catch(err => appLog(String(err)));
document.getElementById("closeAppThread").onclick = () => closeAppThread().catch(err => appLog(String(err)));
loadAll().catch(err => log(String(err)));
</script>
</body>
</html>"""
