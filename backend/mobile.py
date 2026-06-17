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
    .tasks-page { padding-bottom: 86px; }
    .home-hero {
      display: grid;
      gap: 10px;
      background: #111827;
      color: #fff;
      border-color: #111827;
    }
    .home-hero h2 { color: #fff; }
    .home-hero .muted { color: #cbd5e1; }
    .status-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }
    .status-card {
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px;
      background: var(--surface);
      min-width: 0;
    }
    .status-card.warning {
      border-color: #fed7aa;
      background: var(--warning-bg);
      color: var(--warning-text);
    }
    .status-card.error {
      border-color: #fecaca;
      background: var(--error-bg);
      color: var(--error-text);
    }
    .status-value {
      display: block;
      margin-top: 4px;
      font-size: 18px;
      font-weight: 800;
      word-break: break-word;
    }
    .activity-card {
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px;
      background: var(--surface-soft);
    }
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
      display: grid;
      gap: 8px;
    }
    .empty-state strong {
      color: var(--text);
      font-size: 14px;
    }
    .empty-state button {
      width: auto;
      justify-self: start;
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
      grid-template-columns: repeat(3, minmax(0, 1fr));
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
    .floating-action {
      position: fixed;
      left: 14px;
      right: 14px;
      bottom: 64px;
      z-index: 2;
      box-shadow: 0 -8px 24px rgba(15, 23, 42, 0.12);
    }
    .sheet-backdrop {
      position: fixed;
      inset: 0;
      z-index: 5;
      display: none;
      background: rgba(15, 23, 42, 0.42);
    }
    .sheet-backdrop.show { display: block; }
    .sheet {
      position: absolute;
      left: 0;
      right: 0;
      bottom: 0;
      max-height: 88vh;
      overflow: auto;
      background: var(--surface);
      border-radius: 16px 16px 0 0;
      padding: 14px;
      box-shadow: 0 -14px 32px rgba(15, 23, 42, 0.18);
    }
    .sheet-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
    }
    .sheet-header h2 { margin: 0; }
    .sheet-close {
      width: auto;
      min-width: 42px;
      background: var(--surface-soft);
      color: var(--text);
      border: 1px solid var(--border);
    }
    .task-form-sheet,
    .task-detail-sheet {
      display: grid;
      gap: 10px;
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
    .app-session-header {
      display: grid;
      gap: 10px;
    }
    .app-session-title-row {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
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
    .app-session-actions {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 8px;
    }
    .app-session-actions button {
      min-width: 92px;
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
    .app-hidden-state {
      display: none;
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
      cursor: pointer;
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
    .bubble-detail-hint {
      display: block;
      margin-top: 6px;
      color: var(--muted);
      font-size: 11px;
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
    .composer-meta {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      color: var(--muted);
      font-size: 12px;
      min-height: 18px;
    }
    .send-mode-row {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr);
      align-items: center;
      gap: 8px;
    }
    .send-mode-toggle {
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 0;
      min-height: 42px;
      padding: 0 10px;
      border: 1px solid var(--border);
      border-radius: 10px;
      background: var(--surface-soft);
      color: var(--text);
      white-space: nowrap;
    }
    .send-mode-toggle input {
      width: auto;
      min-height: auto;
      margin: 0;
    }
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
      .task-actions { grid-template-columns: repeat(3, max-content); }
      .floating-action { left: calc(50% - 446px); right: calc(50% - 446px); }
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
  <section id="tab-home" class="tab-page active" data-tab-page="home">
    <div class="card home-hero">
      <h2>Codex 工作台</h2>
      <p class="muted">先看状态，再进入任务或会话。</p>
      <button id="homeCreateTask">新建任务</button>
    </div>

    <div id="homeAlerts" class="stack"></div>

    <div class="card">
      <h2>系统状态</h2>
      <div id="homeStatus" class="status-grid"></div>
    </div>

    <div class="card">
      <h2>最近任务</h2>
      <div id="homeTasks" class="stack"></div>
    </div>

    <div class="card">
      <h2>最近会话</h2>
      <div id="homeThreads" class="stack"></div>
    </div>
  </section>

  <section id="tab-tasks" class="tab-page tasks-page" data-tab-page="tasks">
    <div class="card">
      <div class="row">
        <h2>任务</h2>
        <button id="refresh" class="secondary">刷新任务</button>
      </div>
      <label>任务状态筛选
        <select id="taskStatusFilter">
          <option value="">全部</option>
          <option value="PENDING">PENDING</option>
          <option value="RUNNING">RUNNING</option>
          <option value="SUCCESS">SUCCESS</option>
          <option value="FAILED">FAILED</option>
          <option value="CANCELLED">CANCELLED</option>
        </select>
      </label>
      <div id="taskFilterSummary" class="muted"></div>
      <div id="tasks" class="stack"></div>
    </div>
    <button id="openCreateTaskSheet" class="floating-action">新建任务</button>
  </section>

  <section id="tab-app" class="tab-page app-console" data-tab-page="app">
    <div class="card app-current-card">
      <div id="appThreadCurrent" class="item">当前 App Thread: 未选择</div>
    </div>

    <div class="card app-main-panel">
      <div id="appTurnStatus" class="item app-hidden-state"></div>
      <div id="appTurns" class="chat-list"></div>
    </div>

    <div class="card app-composer">
      <label>发送消息 <textarea id="appMessage" placeholder="发送到当前 App Thread 的消息"></textarea></label>
      <div class="composer-meta">
        <span id="appMessageHint">请选择会话后发送消息</span>
        <span id="appMessageCount">0 字</span>
      </div>
      <div id="appWaiting" class="muted"></div>
      <div class="send-mode-row">
        <label class="send-mode-toggle"><input id="appSendAsync" type="checkbox" checked> 异步</label>
        <button id="sendAppMessage">发送</button>
      </div>
    </div>

    <div class="app-hidden-state" aria-hidden="true">
      <label>App Thread 标题 <input id="appThreadTitle" placeholder="App Thread 标题"></label>
      <select id="appThreadStatusFilter">
        <option value="">全部</option>
        <option value="ACTIVE">ACTIVE</option>
        <option value="ERROR">ERROR</option>
        <option value="CLOSED">CLOSED</option>
      </select>
      <label class="inline"><input id="appIncludeArchived" type="checkbox"> 显示 archived</label>
      <div id="appThreads" class="stack"></div>
      <div id="appThreadFinal" class="item"></div>
      <div id="appEventsSummary" class="summary-grid"></div>
      <pre id="appOutput"></pre>
      <button id="checkAppBridge" class="secondary">检查 App Server Bridge</button>
      <button id="refreshAppThreads" class="secondary">刷新 App Threads</button>
      <button id="createAppThread" class="secondary">新建</button>
      <button id="loadAppFinal" class="secondary">查看 App Final</button>
      <button id="loadAppTurns" class="secondary">刷新会话</button>
      <button id="refreshAppTurn" class="secondary">刷新当前 Turn</button>
      <button id="cancelAppTurn" class="danger">取消当前 Turn</button>
      <button id="loadAppEvents" class="secondary">查看 App Events</button>
      <button id="reopenAppThread" class="secondary">重开</button>
      <button id="closeAppThread" class="danger">关闭</button>
      <button id="recoverStaleTurns" class="secondary">恢复卡住 turn</button>
      <button id="cleanupClosedThreads" class="secondary">清理 CLOSED</button>
      <button id="cleanupErrorThreads" class="secondary">清理 ERROR</button>
      <button id="sendAppTurn">同步发送</button>
      <button id="sendAsyncAppTurn">异步发送</button>
      <div id="appBridgeStatus" class="muted"></div>
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
      <div class="row">
        <div>
          <h2>运行诊断</h2>
          <p class="muted">查看 Runner 在线状态、hostname、pid 和 supported_models。</p>
        </div>
        <button id="refreshRunners" class="secondary">刷新 Runner</button>
      </div>
      <div id="runners" class="stack"></div>
    </div>

    <div class="card">
      <h2>设置</h2>
      <div class="item">
        <strong>当前版本</strong><br>
        <span class="muted">v1.2 mobile app UI/UX POC</span>
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

<div id="sheetBackdrop" class="sheet-backdrop" role="dialog" aria-modal="true" aria-hidden="true">
  <div class="sheet">
    <div class="sheet-header">
      <h2 id="sheetTitle">面板</h2>
      <button id="closeSheet" class="sheet-close" aria-label="关闭">关闭</button>
    </div>
    <div id="sheetContent"></div>
  </div>
</div>

<nav class="bottom-nav" aria-label="Mobile tabs">
  <button class="tab-button active" data-tab="home">首页</button>
  <button class="tab-button" data-tab="tasks">任务</button>
  <button class="tab-button" data-tab="app">会话</button>
  <button class="tab-button" data-tab="settings">我的</button>
</nav>"""


def mobile_script() -> str:
    return """<script>
const tokenInput = document.getElementById("token");
const appOutput = document.getElementById("appOutput");
const toast = document.getElementById("toast");
const sheetBackdrop = document.getElementById("sheetBackdrop");
const sheetTitle = document.getElementById("sheetTitle");
const sheetContent = document.getElementById("sheetContent");
const APP_WAITING_TEXT = "正在等待 App Server 返回，请不要刷新页面。";
const APP_TURN_TERMINAL_STATUSES = ["SUCCESS", "FAILED", "CANCELLED"];
const UI_STATE_KEYS = {
  activeTab: "mobile.activeTab",
  taskStatusFilter: "mobile.taskStatusFilter",
  appThreadStatusFilter: "mobile.appThreadStatusFilter",
  appIncludeArchived: "mobile.appIncludeArchived",
  selectedAppThreadId: "mobile.selectedAppThreadId",
  appSendMode: "mobile.appSendMode",
};
const VALID_TABS = ["home", "tasks", "app", "settings"];
const TASK_ACTIVE_STATUSES = ["PENDING", "RUNNING"];
const TASK_AUTO_REFRESH_MS = 5000;
let activeTabName = "home";
let selectedAppThreadId = null;
let selectedAppThread = null;
let selectedAppThreadMissingFromList = false;
let selectedAppTurnId = null;
let appTurnPollTimer = null;
let appTurnPollTargetId = null;
let taskAutoRefreshTimer = null;
let taskAutoRefreshWarningShown = false;
let appThreadsCache = [];
let appTurnsCache = [];
let homeAppThreadsCache = [];
let tasksCache = [];
let projectsCache = [];
let runnersCache = [];
let taskTemplatesCache = [];
let homeStateCache = null;
let toastTimer = null;
tokenInput.value = (localStorage.getItem("apiToken") || "").trim();

function headers(json = false) {
  const h = {};
  const token = (localStorage.getItem("apiToken") || "").trim();
  if (token) h["X-API-Token"] = token;
  if (json) h["Content-Type"] = "application/json";
  return h;
}

function log(text) {
  const output = document.getElementById("output");
  if (output) output.textContent = text;
}

function appLog(text) {
  appOutput.textContent = text;
}

function readUiState(key, fallback = "") {
  return localStorage.getItem(key) ?? fallback;
}

function writeUiState(key, value) {
  localStorage.setItem(key, String(value ?? ""));
}

function removeUiState(key) {
  localStorage.removeItem(key);
}

function restoreInitialUiState() {
  const storedTab = readUiState(UI_STATE_KEYS.activeTab, "home");
  activeTabName = VALID_TABS.includes(storedTab) ? storedTab : "home";
  document.getElementById("taskStatusFilter").value = readUiState(UI_STATE_KEYS.taskStatusFilter, "");
  document.getElementById("appThreadStatusFilter").value = readUiState(UI_STATE_KEYS.appThreadStatusFilter, "");
  document.getElementById("appIncludeArchived").checked = readUiState(UI_STATE_KEYS.appIncludeArchived, "false") === "true";
  selectedAppThreadId = readStoredNumber(UI_STATE_KEYS.selectedAppThreadId);
  const sendMode = readUiState(UI_STATE_KEYS.appSendMode, "async");
  document.getElementById("appSendAsync").checked = sendMode !== "sync";
  switchTab(activeTabName, false);
}

function readStoredNumber(key) {
  const rawValue = readUiState(key, "");
  const value = Number(rawValue);
  return Number.isFinite(value) && value > 0 ? value : null;
}

function showToast(message, type = "info") {
  toast.textContent = String(message || "");
  toast.className = `toast show ${type}`;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.className = "toast";
  }, 2600);
}

function errorText(value) {
  return String(value && value.message ? value.message : value || "");
}

function classifyError(error) {
  const text = errorText(error);
  const lower = text.toLowerCase();
  if (lower.includes("unknown bridge thread id")) {
    return {
      code: "stale_bridge_thread",
      title: "会话需要重开",
      message: "Bridge 或 App Server 重启后，旧会话已经不在 sidecar 内存中。",
      primaryAction: "reopen_app_thread",
    };
  }
  if (lower.includes("401") || lower.includes("invalid api token") || lower.includes("unauthorized")) {
    return {
      code: "token_invalid",
      title: "Token 无效或未保存",
      message: "请到「我的」页重新保存 API Token。",
      primaryAction: "open_settings_token",
    };
  }
  if (lower.includes("503") || lower.includes("bridge") && (lower.includes("unavailable") || lower.includes("refused") || lower.includes("failed"))) {
    return {
      code: "bridge_unavailable",
      title: "App Server Bridge 不可用",
      message: "请确认 App Server Bridge sidecar 已启动，并检查 Backend 中的 Bridge 配置。",
      primaryAction: "open_bridge_help",
    };
  }
  if (lower.includes("409") || lower.includes("conflict") || lower.includes("turn") && lower.includes("running")) {
    return {
      code: "turn_conflict",
      title: "当前会话已有 Turn 正在运行",
      message: "请先刷新当前 Turn，等待完成，或取消当前 Turn 后再发送。",
      primaryAction: "refresh_current_turn",
    };
  }
  if (lower.includes("app thread") && lower.includes("closed")) {
    return {
      code: "app_thread_closed",
      title: "App Thread 已关闭",
      message: "当前会话已关闭，需要重开后才能继续发送。",
      primaryAction: "reopen_app_thread",
    };
  }
  if (lower.includes("failed to fetch") || lower.includes("networkerror") || lower.includes("network failed")) {
    return {
      code: "network_failed",
      title: "网络请求失败",
      message: "请确认后端服务仍在运行，并检查手机与电脑是否在同一可信网络。",
      primaryAction: "refresh_all",
    };
  }
  if (lower.includes("cancel") && (lower.includes("not allowed") || lower.includes("terminal"))) {
    return {
      code: "cancel_not_allowed",
      title: "当前状态不能取消",
      message: "任务或 Turn 已经结束，无法再次取消。",
      primaryAction: "refresh_all",
    };
  }
  return {
    code: "unknown",
    title: "操作失败",
    message: "请查看错误详情，必要时刷新页面后重试。",
    primaryAction: "refresh_all",
  };
}

function showErrorSheet(error, context = "") {
  const info = classifyError(error);
  const text = errorText(error);
  openSheet(info.title, `
    <div class="task-detail-sheet">
      <div class="detail-section">
        <h3>恢复建议</h3>
        <p>${escapeHtml(info.message)}</p>
        <p class="muted">error.code=${escapeHtml(info.code)}${context ? ` step=${escapeHtml(context)}` : ""}</p>
      </div>
      <div class="detail-section">
        <h3>下一步</h3>
        <div id="errorActions" class="task-actions">${errorActionHtml(info.primaryAction)}</div>
      </div>
      <details>
        <summary>错误详情</summary>
        <pre>${escapeHtml(text)}</pre>
      </details>
    </div>`);
  bindErrorAction(info.primaryAction);
}

function errorActionHtml(action) {
  if (action === "open_settings_token") return `<button id="errorGoSettings" class="secondary">去保存 Token</button>`;
  if (action === "open_bridge_help") return `<button id="errorBridgeHelp" class="secondary">查看启动提示</button>`;
  if (action === "reopen_app_thread") {
    return selectedAppThreadId
      ? `<button id="errorReopenThread" class="secondary">重开当前会话</button>`
      : `<button id="errorSwitchThread" class="secondary">选择或新建会话</button>`;
  }
  if (action === "refresh_current_turn") return `<button id="errorRefreshTurn" class="secondary">刷新当前 Turn</button><button id="errorCancelTurn" class="danger">取消当前 Turn</button>`;
  return `<button id="errorRefreshAll" class="secondary">刷新页面状态</button>`;
}

function bindErrorAction(action) {
  const bind = (id, handler) => {
    const button = document.getElementById(id);
    if (button) button.onclick = handler;
  };
  bind("errorGoSettings", () => {
    closeSheet();
    switchTab("settings");
    tokenInput.focus();
  });
  bind("errorBridgeHelp", () => {
    closeSheet();
    switchTab("settings");
    showBridgeHelpSheet();
  });
  bind("errorReopenThread", () => withButtonLoading("errorReopenThread", "处理中...", async () => {
    await reopenAppThread();
    closeSheet();
  }));
  bind("errorSwitchThread", () => {
    closeSheet();
    showAppThreadSwitcher();
  });
  bind("errorRefreshTurn", () => withButtonLoading("errorRefreshTurn", "处理中...", refreshCurrentAppTurn));
  bind("errorCancelTurn", () => withButtonLoading("errorCancelTurn", "处理中...", cancelCurrentAppTurn));
  bind("errorRefreshAll", () => withButtonLoading("errorRefreshAll", "处理中...", loadAll));
}

function showBridgeHelpSheet() {
  openSheet("Bridge 启动提示", `
    <div class="task-detail-sheet">
      <div class="detail-section">
        <h3>本机启动</h3>
        <pre>$env:APP_SERVER_BRIDGE_TOKEN="dev-token"
python .\\poc\\app_server\\app_server_bridge.py --host 127.0.0.1 --port 8766</pre>
      </div>
      <p class="muted">仅限可信局域网试用，不要公网暴露。</p>
    </div>`);
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
    if (isStaleBridgeThreadError(err)) {
      showStaleBridgeThreadSheet(err);
    } else {
      showErrorSheet(err, target ? target.id || target.textContent : "");
    }
    return null;
  } finally {
    if (target) {
      target.disabled = false;
      target.textContent = originalText;
    }
    updateAppComposerState();
  }
}

function isStaleBridgeThreadError(value) {
  const text = String(value && value.message ? value.message : value || "").toLowerCase();
  return text.includes("unknown bridge thread id");
}

function showStaleBridgeThreadSheet(error) {
  document.getElementById("appWaiting").textContent = "";
  const errorText = String(error && error.message ? error.message : error || "");
  const actionHtml = selectedAppThreadId
    ? `<button id="reopenStaleAppThread" class="secondary">重开当前会话</button>`
    : `<button class="secondary" disabled>请先选择会话</button>`;
  openSheet("会话需要重开", `
    <div class="task-detail-sheet">
      <div class="detail-section">
        <h3>Bridge 会话已失效</h3>
        <p>Bridge 或 App Server 重启后，旧的 bridge_thread_id 只保存在后端数据库中，App Server 进程内的 thread 已经不存在。</p>
        <p class="muted">可以重开当前 AppThread。历史 turns 会保留，但 App Server 上下文会从新的 thread 重新开始。</p>
      </div>
      <div class="detail-section">
        <h3>恢复操作</h3>
        ${actionHtml}
      </div>
      <details>
        <summary>错误详情</summary>
        <pre>${escapeHtml(errorText)}</pre>
      </details>
    </div>`);
  const reopenButton = document.getElementById("reopenStaleAppThread");
  if (reopenButton) {
    reopenButton.onclick = () => withButtonLoading("reopenStaleAppThread", "处理中...", async () => {
      await reopenAppThread();
      closeSheet();
      if (selectedAppThreadId) {
        await loadAppTurns();
      }
    });
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

function switchTab(tabName, persist = true) {
  const nextTab = VALID_TABS.includes(tabName) ? tabName : "home";
  activeTabName = nextTab;
  if (persist) writeUiState(UI_STATE_KEYS.activeTab, nextTab);
  document.querySelectorAll("[data-tab-page]").forEach(page => {
    page.classList.toggle("active", page.dataset.tabPage === nextTab);
  });
  document.querySelectorAll("[data-tab]").forEach(button => {
    button.classList.toggle("active", button.dataset.tab === nextTab);
  });
  updateTaskAutoRefresh();
}

function openSheet(title, contentHtml) {
  sheetTitle.textContent = title;
  sheetContent.innerHTML = contentHtml;
  sheetBackdrop.classList.add("show");
  sheetBackdrop.setAttribute("aria-hidden", "false");
}

function closeSheet() {
  sheetBackdrop.classList.remove("show");
  sheetBackdrop.setAttribute("aria-hidden", "true");
  sheetContent.innerHTML = "";
}

function renderCreateTaskSheet() {
  openSheet("新建任务", `
    <div class="task-form-sheet">
      <label>项目 <select id="project"></select></label>
      <label>Prompt <textarea id="prompt" placeholder="输入受控目标或 GOAL 任务"></textarea></label>
      <label>任务类型 <select id="taskType"></select></label>
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
      <p class="muted">主线 Runner/codex exec 任务链路。普通使用只需要选择项目、Prompt 和任务类型。</p>
    </div>`);
  loadFormOptions();
  document.getElementById("createTask").onclick = () => withButtonLoading("createTask", "处理中...", createTask);
  document.getElementById("prompt").focus();
}

async function loadAll() {
  const [healthResult, projects, runners, tasks, templates] = await Promise.all([
    safeApi("/health"),
    api("/projects", {headers: headers()}),
    api("/runners", {headers: headers()}),
    api("/tasks?limit=20", {headers: headers()}),
    api("/task-templates", {headers: headers()}),
  ]);
  renderProjects(projects);
  renderRunners(runners);
  tasksCache = tasks;
  renderFilteredTasks();
  renderTaskTypes(templates);
  homeStateCache = {
    healthResult,
    runners,
    tasks,
  };
  renderHome({
    healthResult,
    runners,
    tasks,
  });
  loadHomeAppServerStatus({healthResult, runners, tasks}).catch(err => {
    renderHome({
      healthResult,
      runners,
      tasks,
      bridgeResult: {ok: false, error: String(err)},
      appThreadsResult: {ok: false, error: String(err)},
    });
  });
  try {
    await loadAppThreadList();
    await restoreSelectedAppThreadAfterLoad();
  } catch (err) {
    appLog(String(err));
  }
  updateTaskAutoRefresh();
}

async function safeApi(path, options = {}) {
  try {
    return {ok: true, data: await api(path, options)};
  } catch (err) {
    return {ok: false, error: String(err)};
  }
}

function renderProjects(projects) {
  projectsCache = projects;
  const target = document.getElementById("project");
  if (!target) return;
  target.innerHTML = projects
    .filter(p => p.enabled)
    .map(p => `<option value="${escapeHtml(p.id)}">${escapeHtml(p.name)}</option>`)
    .join("");
}

function renderTaskTypes(templates) {
  taskTemplatesCache = templates;
  const target = document.getElementById("taskType");
  if (!target) return;
  target.innerHTML = templates
    .map(t => `<option value="${escapeHtml(t.task_type)}">${escapeHtml(t.task_type)}</option>`)
    .join("");
}

function renderRunners(runners) {
  runnersCache = runners;
  const runnerSelect = document.getElementById("runner");
  if (runnerSelect) {
    runnerSelect.innerHTML =
      `<option value="">自动 / 项目默认</option>` +
      runners.map(r => `<option value="${escapeHtml(r.runner_id)}">${escapeHtml(r.runner_id)} (${escapeHtml(r.status)})</option>`).join("");
  }
  document.getElementById("runners").innerHTML = runners.length ? runners.map(r => `
    <div class="item">
      <strong>${escapeHtml(r.runner_id)}</strong> ${statusBadge(r.status)}<br>
      <span class="muted">${escapeHtml(r.hostname)} pid=${escapeHtml(r.pid)} models=${escapeHtml(r.supported_models || "")}</span>
    </div>`).join("") : `
    <div class="empty-state">
      <strong>没有在线 Runner</strong>
      <span>请先启动 runner/runner.py 或 scripts/start.bat runner，再刷新 Runner 状态。</span>
      <button class="secondary" onclick="withButtonLoading(this, '处理中...', async () => { const runners = await api('/runners', {headers: headers()}); renderRunners(runners); showToast('Runner 已刷新', 'success'); })">刷新 Runner</button>
    </div>`;
}

function loadFormOptions() {
  renderProjects(projectsCache);
  renderRunners(runnersCache);
  renderTaskTypes(taskTemplatesCache);
}

function renderHome({healthResult, runners, tasks, bridgeResult, appThreadsResult}) {
  const onlineRunners = runners.filter(r => String(r.status || "").toUpperCase() === "ONLINE").length;
  const offlineRunners = Math.max(runners.length - onlineRunners, 0);
  const runningTasks = tasks.filter(t => ["PENDING", "RUNNING"].includes(normalizedStatus(t.status))).length;
  const bridgeState = bridgeResult || {ok: false, pending: true};
  const appThreadsState = appThreadsResult || {ok: true, data: []};
  const appThreads = appThreadsState.ok && Array.isArray(appThreadsState.data) ? appThreadsState.data : [];
  const activeThreads = appThreads.filter(t => ["ACTIVE", "RUNNING"].includes(normalizedStatus(t.status))).length;
  const bridgeOk = bridgeState.ok && normalizedStatus(bridgeState.data.status || "ok") !== "ERROR";
  document.getElementById("homeStatus").innerHTML = `
    <div class="status-card ${healthResult.ok ? "" : "error"}">
      <span class="meta-label">Backend</span>
      <span class="status-value">${healthResult.ok ? "正常" : "异常"}</span>
    </div>
    <div class="status-card ${onlineRunners ? "" : "warning"}">
      <span class="meta-label">Runner</span>
      <span class="status-value">在线 ${escapeHtml(onlineRunners)} / 离线 ${escapeHtml(offlineRunners)}</span>
    </div>
    <div class="status-card ${bridgeState.pending ? "" : bridgeOk ? "" : "error"}">
      <span class="meta-label">Bridge</span>
      <span class="status-value">${bridgeState.pending ? "检查中" : bridgeOk ? "正常" : "异常"}</span>
    </div>
    <div class="status-card">
      <span class="meta-label">运行中</span>
      <span class="status-value">任务 ${escapeHtml(runningTasks)} / 会话 ${escapeHtml(activeThreads)}</span>
    </div>`;
  renderHomeAlerts({healthResult, bridgeResult: bridgeState, onlineRunners});
  renderHomeTasks(tasks.slice(0, 3));
  renderHomeThreads(appThreads.slice(0, 3), appThreadsState);
}

async function loadHomeAppServerStatus(baseState) {
  const [bridgeResult, appThreadsResult] = await Promise.all([
    safeApi("/app-server-bridge/health", {headers: headers()}),
    safeApi("/app-threads?limit=3", {headers: headers()}),
  ]);
  homeStateCache = {...baseState, bridgeResult, appThreadsResult};
  renderHome(homeStateCache);
}

function renderHomeAlerts({healthResult, bridgeResult, onlineRunners}) {
  const alerts = [];
  if (!healthResult.ok) alerts.push(`Backend 异常：${healthResult.error}`);
  if (!onlineRunners) alerts.push("没有在线 Runner，请先启动 runner/runner.py 或 scripts/start.bat runner。");
  if (bridgeResult && !bridgeResult.pending && !bridgeResult.ok) alerts.push(`Bridge 异常：${bridgeResult.error}`);
  document.getElementById("homeAlerts").innerHTML = alerts
    .map(message => `<div class="status-card error">${escapeHtml(message)}</div>`)
    .join("");
}

function renderHomeTasks(tasks) {
  document.getElementById("homeTasks").innerHTML = tasks.length
    ? tasks.map(t => `
      <div class="activity-card">
        <strong>#${escapeHtml(t.id)} ${escapeHtml(t.task_type)}</strong> ${statusBadge(t.status)}<br>
        <span class="muted">updated=${escapeHtml(t.updated_at || "")} runner=${escapeHtml(t.assigned_runner_id || t.runner_id || "")}</span>
        <div class="links">
          <a href="#" onclick="switchTab('tasks'); showTask(${escapeHtml(t.id)}); return false;">打开详情</a>
        </div>
      </div>`).join("")
    : `<div class="empty-state">
        <strong>还没有任务</strong>
        <span>点击下方按钮开始第一次 Codex 执行。</span>
        <button class="secondary" onclick="switchTab('tasks'); renderCreateTaskSheet();">新建任务</button>
      </div>`;
}

function renderHomeThreads(appThreads, appThreadsResult) {
  homeAppThreadsCache = appThreads;
  if (!appThreadsResult.ok) {
    document.getElementById("homeThreads").innerHTML = `<div class="empty-state">最近会话暂不可用：${escapeHtml(appThreadsResult.error)}</div>`;
    return;
  }
  document.getElementById("homeThreads").innerHTML = appThreads.length
    ? appThreads.map(t => `
      <div class="activity-card">
        <strong>#${escapeHtml(t.id)} ${escapeHtml(t.title)}</strong> ${statusBadge(t.status)}<br>
        <span class="muted">turns=${escapeHtml(t.turn_count)} updated=${escapeHtml(t.updated_at || "")}</span>
        <div class="links">
          <a href="#" onclick="switchTab('app'); selectAppThread(${escapeHtml(t.id)}); return false;">打开会话</a>
        </div>
      </div>`).join("")
    : `<div class="empty-state">
        <strong>还没有 App 会话</strong>
        <span>进入「会话」后新建一次 App Server 对话。</span>
        <button class="secondary" onclick="switchTab('app'); showAppThreadSwitcher();">新建会话</button>
      </div>`;
}

function selectedTaskStatusFilter() {
  const target = document.getElementById("taskStatusFilter");
  return target ? normalizedStatus(target.value) : "";
}

function filterTasksByStatus(tasks) {
  const statusFilter = selectedTaskStatusFilter();
  if (!statusFilter) return tasks;
  return tasks.filter(t => normalizedStatus(t.status) === statusFilter);
}

function renderFilteredTasks() {
  const filteredTasks = filterTasksByStatus(tasksCache);
  renderTasks(filteredTasks);
  const statusFilter = selectedTaskStatusFilter();
  document.getElementById("taskFilterSummary").textContent = statusFilter
    ? `当前筛选：${statusFilter}，显示 ${filteredTasks.length} / ${tasksCache.length} 个任务`
    : `当前筛选：全部，显示 ${tasksCache.length} 个任务`;
  updateTaskAutoRefresh();
}

function renderTasks(tasks) {
  const statusFilter = selectedTaskStatusFilter();
  const emptyMessage = statusFilter
    ? `当前筛选 ${statusFilter} 下没有任务。可以切换为「全部」或新建任务。`
    : "还没有任务。点击下方按钮开始第一次 Codex 执行。";
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
          <a href="${escapeHtml(t.result_url)}" target="_blank">result</a>
          <a href="#" onclick="showTaskMore(${escapeHtml(t.id)});return false;">更多</a>
        </div>
      </div>`).join("")
    : `<div class="empty-state">
        <strong>没有匹配任务</strong>
        <span>${escapeHtml(emptyMessage)}</span>
        <button class="secondary" onclick="renderCreateTaskSheet()">新建任务</button>
      </div>`;
}

function hasActiveTasks() {
  return tasksCache.some(t => TASK_ACTIVE_STATUSES.includes(normalizedStatus(t.status)));
}

function shouldAutoRefreshTasks() {
  return document.visibilityState === "visible" && ["home", "tasks"].includes(activeTabName) && hasActiveTasks();
}

function startTaskAutoRefresh() {
  if (taskAutoRefreshTimer) return;
  taskAutoRefreshTimer = setInterval(() => {
    refreshTasksForAutoRefresh().catch(err => {
      if (!taskAutoRefreshWarningShown) {
        taskAutoRefreshWarningShown = true;
        showToast(`任务自动刷新失败：${String(err)}`, "warning");
      }
      appLog(String(err));
    });
  }, TASK_AUTO_REFRESH_MS);
}

function stopTaskAutoRefresh() {
  if (!taskAutoRefreshTimer) return;
  clearInterval(taskAutoRefreshTimer);
  taskAutoRefreshTimer = null;
}

function updateTaskAutoRefresh() {
  if (shouldAutoRefreshTasks()) {
    startTaskAutoRefresh();
  } else {
    stopTaskAutoRefresh();
  }
}

async function refreshTasksForAutoRefresh() {
  if (!shouldAutoRefreshTasks()) {
    updateTaskAutoRefresh();
    return;
  }
  const tasks = await api("/tasks?limit=20", {headers: headers()});
  tasksCache = tasks;
  renderFilteredTasks();
  if (homeStateCache) {
    homeStateCache = {...homeStateCache, tasks};
    renderHome(homeStateCache);
  }
  taskAutoRefreshWarningShown = false;
  updateTaskAutoRefresh();
}

function handleVisibilityChange() {
  if (document.visibilityState === "hidden") {
    stopTaskAutoRefresh();
    return;
  }
  loadAll().catch(err => {
    showToast(String(err), "warning");
    appLog(String(err));
  });
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
  closeSheet();
  await showTask(task.id);
  showToast(`已创建任务 #${task.id}`, "success");
}

async function showTask(id) {
  const task = await api(`/tasks/${id}`, {headers: headers()});
  openSheet(`任务 #${task.id}`, `
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
          <button class="secondary" onclick="rerunTask(${escapeHtml(task.id)}, this)">重跑</button>
          <button class="danger" onclick="cancelTask(${escapeHtml(task.id)}, this)">取消</button>
        </div>
      </div>
      <div class="detail-section">
        <h3>log/result 预览</h3>
        <p class="muted">优先展示 log 预览；result 和 diff 保持链接打开，本版本不做 diff UI。</p>
        <pre id="taskPreview" class="preview-block"></pre>
      </div>
      <details>
        <summary>调试输出</summary>
        <pre id="output"></pre>
      </details>
    </div>`);
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

async function showTaskMore(id) {
  const task = await api(`/tasks/${id}`, {headers: headers()});
  openSheet(`任务 #${task.id} 更多`, `
    <div class="task-detail-sheet">
      <div class="detail-section">
        <h3>更多操作</h3>
        <div class="task-actions">
          <a href="#" onclick="showTask(${escapeHtml(task.id)});return false;">详情</a>
          <a href="${escapeHtml(task.log_url)}" target="_blank">log</a>
          <a href="${escapeHtml(task.result_url)}" target="_blank">result</a>
          <a href="${escapeHtml(task.diff_url)}" target="_blank">diff</a>
          <button class="secondary" onclick="rerunTask(${escapeHtml(task.id)}, this)">重跑</button>
          <button class="danger" onclick="cancelTask(${escapeHtml(task.id)}, this)">取消</button>
        </div>
      </div>
      <p class="muted">更多操作复用现有任务 API；本轮不新增后端 API 或 diff UI。</p>
    </div>`);
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

async function rerunTask(id, button = null) {
  return withButtonLoading(button, "处理中...", async () => {
    const task = await api(`/tasks/${id}/rerun`, {method: "POST", headers: headers()});
    await loadAll();
    await showTask(task.id);
    showToast(`已重跑任务 #${task.id}`, "success");
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

function persistAppThreadFilters() {
  writeUiState(UI_STATE_KEYS.appThreadStatusFilter, document.getElementById("appThreadStatusFilter").value);
  writeUiState(UI_STATE_KEYS.appIncludeArchived, document.getElementById("appIncludeArchived").checked ? "true" : "false");
}

function updateSelectedAppThreadDisplay() {
  const target = document.getElementById("appThreadCurrent");
  if (!selectedAppThreadId) {
    target.innerHTML = `
      <div class="app-session-header">
        <div class="app-session-title-row">
          <div>
            <div class="app-current-title">App Server 会话</div>
            <span class="muted">未选择当前会话</span>
          </div>
          ${statusBadge("WARNING")}
        </div>
        <div class="app-session-actions">
          <button class="secondary" onclick="showAppThreadSwitcher()">切换会话</button>
          <button class="secondary" onclick="showAppThreadSwitcher()">新建会话</button>
          <button class="ghost" onclick="showAppSessionMore()" disabled>更多</button>
        </div>
      </div>`;
    updateAppActionState();
    return;
  }
  const title = selectedAppThread ? selectedAppThread.title : "";
  const status = selectedAppThread ? selectedAppThread.status : "";
  const missingHint = selectedAppThreadMissingFromList
    ? `<span class="muted">当前会话不在当前筛选结果中</span>`
    : `<span class="muted">当前会话</span>`;
  target.innerHTML = `
    <div class="app-session-header">
      <div class="app-session-title-row">
        <div>
          <div class="app-current-title">${escapeHtml(title || "App Thread")}</div>
          ${missingHint}
        </div>
        ${statusBadge(status)}
      </div>
      <div class="app-session-actions">
        <button class="secondary" onclick="showAppThreadSwitcher()">切换会话</button>
        <button class="ghost" onclick="showAppSessionMore()">更多</button>
      </div>
    </div>`;
  updateAppActionState();
}

function projectOptionsHtml() {
  return projectsCache
    .filter(p => p.enabled)
    .map(p => `<option value="${escapeHtml(p.id)}">${escapeHtml(p.name)}</option>`)
    .join("");
}

function renderAppThreadSwitcherSheet() {
  openSheet("切换会话", `
    <div class="task-detail-sheet">
      <div class="detail-section">
        <h3>新建会话</h3>
        <label>项目 <select id="appThreadProject">${projectOptionsHtml()}</select></label>
        <label>App Thread 标题 <input id="appThreadTitleInput" placeholder="App Thread 标题"></label>
        <button id="appCreateThreadFromSheet">新建会话</button>
      </div>
      <div class="detail-section">
        <h3>最近会话</h3>
        <div class="thread-list-tools">
          <div class="row">
            <label>Thread 状态筛选
              <select id="appThreadStatusFilterSheet">
                <option value="">全部</option>
                <option value="ACTIVE">ACTIVE</option>
                <option value="ERROR">ERROR</option>
                <option value="CLOSED">CLOSED</option>
              </select>
            </label>
            <label class="inline"><input id="appIncludeArchivedSheet" type="checkbox"> 显示 archived</label>
          </div>
          <button id="refreshAppThreadsFromSheet" class="secondary">刷新会话列表</button>
        </div>
        <div id="appThreadsSheet" class="stack"></div>
      </div>
    </div>`);
  const statusFilter = document.getElementById("appThreadStatusFilter");
  const archivedFilter = document.getElementById("appIncludeArchived");
  document.getElementById("appThreadStatusFilterSheet").value = statusFilter.value;
  document.getElementById("appIncludeArchivedSheet").checked = archivedFilter.checked;
  document.getElementById("appThreadStatusFilterSheet").onchange = () => {
    statusFilter.value = document.getElementById("appThreadStatusFilterSheet").value;
    persistAppThreadFilters();
    loadAppThreadList().catch(err => {
      showToast(String(err), "error");
      appLog(String(err));
    });
  };
  document.getElementById("appIncludeArchivedSheet").onchange = () => {
    archivedFilter.checked = document.getElementById("appIncludeArchivedSheet").checked;
    persistAppThreadFilters();
    loadAppThreadList().catch(err => {
      showToast(String(err), "error");
      appLog(String(err));
    });
  };
  document.getElementById("refreshAppThreadsFromSheet").onclick = () => withButtonLoading("refreshAppThreadsFromSheet", "处理中...", async () => {
    await loadAppThreadList();
    showToast("App Threads 已刷新", "success");
  });
  document.getElementById("appCreateThreadFromSheet").onclick = () => withButtonLoading("appCreateThreadFromSheet", "处理中...", createAppThread);
  renderAppThreads(appThreadsCache);
}

async function showAppThreadSwitcher() {
  renderAppThreadSwitcherSheet();
  await loadAppThreadList();
}

function showAppSessionMore() {
  const title = selectedAppThread ? selectedAppThread.title : "App Thread";
  openSheet("会话更多", `
    <div class="task-detail-sheet">
      <div class="detail-section">
        <h3>${escapeHtml(title || "App Thread")}</h3>
        <div id="appSessionMoreStatus">
          ${selectedAppThread ? statusBadge(selectedAppThread.status) : `<span class="muted">未选择会话</span>`}
        </div>
      </div>
      <div class="detail-section">
        <h3>常用操作</h3>
        <div class="task-actions">
          <button class="secondary" onclick="withButtonLoading(this, '处理中...', async () => { await loadAppTurns(); showToast('Turns 已刷新', 'success'); })">刷新会话</button>
          <button class="secondary" onclick="showAppFinalSheet(this)">查看 App Final</button>
          <button class="secondary" onclick="withButtonLoading(this, '处理中...', refreshCurrentAppTurn)">刷新当前 Turn</button>
          <button class="danger" onclick="withButtonLoading(this, '处理中...', cancelCurrentAppTurn)">取消当前 Turn</button>
        </div>
      </div>
      <div class="detail-section">
        <h3>会话管理</h3>
        <div class="task-actions">
          <button class="secondary" onclick="showAppThreadSwitcher()">切换会话</button>
          <button class="secondary" onclick="withButtonLoading(this, '处理中...', reopenAppThread)">重开</button>
          <button class="danger" onclick="withButtonLoading(this, '处理中...', closeAppThread)">关闭</button>
        </div>
      </div>
      <div class="detail-section">
        <h3>事件与调试</h3>
        <div class="task-actions">
          <button class="secondary" onclick="showAppEventsSheet(this)">查看事件摘要</button>
          <button class="secondary" onclick="showAppDebugSheet()">调试输出</button>
          <button class="secondary" onclick="withButtonLoading(this, '处理中...', recoverStaleAppTurns)">恢复卡住 turn</button>
        </div>
      </div>
      <div class="detail-section">
        <h3>Bridge 与清理</h3>
        <div class="task-actions">
          <button class="secondary" onclick="withButtonLoading(this, '处理中...', checkAppServerBridge)">检查 App Server Bridge</button>
          <button class="secondary" onclick="withButtonLoading(this, '处理中...', () => cleanupAppThreads('CLOSED'))">清理 CLOSED</button>
          <button class="secondary" onclick="withButtonLoading(this, '处理中...', () => cleanupAppThreads('ERROR'))">清理 ERROR</button>
        </div>
      </div>
    </div>`);
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
  updateAppComposerState();
}

function updateAppComposerState() {
  const input = document.getElementById("appMessage");
  const hint = document.getElementById("appMessageHint");
  const count = document.getElementById("appMessageCount");
  const unifiedSendButton = document.getElementById("sendAppMessage");
  const rawMessage = input ? input.value : "";
  const message = rawMessage.trim();
  const status = selectedAppThread ? selectedAppThread.status : "";
  const hasThread = Boolean(selectedAppThreadId);
  if (count) count.textContent = `${rawMessage.length} 字`;
  if (hint) {
    if (!hasThread) {
      hint.textContent = "请先选择或新建会话";
    } else if (status === "CLOSED") {
      hint.textContent = "当前会话已关闭，请先重开";
    } else if (!message) {
      hint.textContent = "输入消息后即可发送";
    } else {
      hint.textContent = selectedSendMode() === "async" ? "异步发送，不要刷新页面" : "同步发送，等待完成后返回";
    }
  }
  if (unifiedSendButton) unifiedSendButton.disabled = !hasThread || status === "CLOSED" || !message;
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
    selectedAppThreadMissingFromList = !listedThread;
    if (listedThread) selectedAppThread = listedThread;
  }
  updateSelectedAppThreadDisplay();
  const threadTargets = [
    document.getElementById("appThreads"),
    document.getElementById("appThreadsSheet"),
  ].filter(Boolean);
  if (!appThreads.length) {
    threadTargets.forEach(target => {
      target.innerHTML = `
        <div class="empty-state">
          <strong>暂无 AppThread</strong>
          <span>当前筛选下没有会话，可以调整筛选或新建会话。</span>
          <button class="secondary" onclick="showAppThreadSwitcher()">新建会话</button>
        </div>`;
    });
    return;
  }
  const html = appThreads.map(t => `
    <div class="${selectedAppThreadId === t.id ? "item selected" : "item"}">
      <strong>#${escapeHtml(t.id)}</strong> ${escapeHtml(t.title)}<br>
      ${String(t.title || "").startsWith("[archived]") ? `<span class="muted">archived</span><br>` : ""}
      ${statusBadge(t.status)}<br>
      <span class="muted">project=${escapeHtml(t.project_id)} status=${escapeHtml(t.status)} turns=${escapeHtml(t.turn_count)} updated=${escapeHtml(t.updated_at)}</span><br>
      <span>${escapeHtml(shortText(t.latest_assistant_final || "", 160))}</span>
      ${t.last_error ? `<br><span class="muted">last_error=${escapeHtml(t.last_error)}</span>` : ""}
      <div class="links">
        <a href="#" onclick="selectAppThread(${escapeHtml(t.id)}); closeSheet(); return false;">选择</a>
      </div>
    </div>`).join("");
  threadTargets.forEach(target => {
    target.innerHTML = html;
  });
}

async function restoreSelectedAppThreadAfterLoad() {
  if (!selectedAppThreadId) return;
  let listedThread = appThreadsCache.find(t => t.id === selectedAppThreadId);
  if (!listedThread) {
    try {
      listedThread = await api(`/app-threads/${selectedAppThreadId}`, {headers: headers()});
      selectedAppThreadMissingFromList = true;
    } catch (err) {
      selectedAppThreadId = null;
      selectedAppThread = null;
      selectedAppThreadMissingFromList = false;
      removeUiState(UI_STATE_KEYS.selectedAppThreadId);
      updateSelectedAppThreadDisplay();
      appLog(`恢复 AppThread 失败：${String(err)}`);
      return;
    }
  } else {
    selectedAppThreadMissingFromList = false;
  }
  selectedAppThread = listedThread;
  updateSelectedAppThreadDisplay();
  await loadAppTurns();
}

async function createAppThread() {
  const projectTarget = document.getElementById("appThreadProject") || document.getElementById("project");
  const titleTarget = document.getElementById("appThreadTitleInput") || document.getElementById("appThreadTitle");
  const fallbackProject = projectsCache.find(p => p.enabled) || projectsCache[0];
  const projectId = projectTarget ? Number(projectTarget.value) : Number(fallbackProject ? fallbackProject.id : 0);
  if (!projectId) throw new Error("请先配置可用项目");
  const payload = {
    project_id: projectId,
    title: titleTarget ? titleTarget.value || null : null,
  };
  const appThread = await api("/app-threads", {method: "POST", headers: headers(true), body: JSON.stringify(payload)});
  selectedAppThreadId = appThread.id;
  selectedAppThread = appThread;
  selectedAppThreadMissingFromList = false;
  writeUiState(UI_STATE_KEYS.selectedAppThreadId, appThread.id);
  await loadAll();
  closeSheet();
  showToast(`已创建 App Thread #${appThread.id}`, "success");
  appLog(`已创建 App Thread #${appThread.id}`);
}

function selectAppThread(id) {
  selectedAppThreadId = id;
  selectedAppThread =
    appThreadsCache.find(t => t.id === id) ||
    homeAppThreadsCache.find(t => t.id === id) ||
    selectedAppThread;
  selectedAppThreadMissingFromList = !appThreadsCache.some(t => t.id === id);
  writeUiState(UI_STATE_KEYS.selectedAppThreadId, id);
  updateSelectedAppThreadDisplay();
  renderAppThreads(appThreadsCache);
  loadAppTurns().catch(err => {
    showToast(String(err), "error");
    appLog(String(err));
  });
}

function selectedSendMode() {
  const asyncToggle = document.getElementById("appSendAsync");
  return asyncToggle && asyncToggle.checked ? "async" : "sync";
}

function persistSendMode() {
  writeUiState(UI_STATE_KEYS.appSendMode, selectedSendMode());
}

async function sendAppMessage() {
  const mode = selectedSendMode();
  if (mode === "async") {
    return sendAsyncAppTurn();
  }
  return sendAppTurn();
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
    updateAppComposerState();
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
    updateAppComposerState();
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
  if (appTurnPollTimer && appTurnPollTargetId === turnId) return;
  stopAppTurnPolling();
  selectedAppTurnId = turnId;
  appTurnPollTargetId = turnId;
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
  appTurnPollTargetId = null;
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
      const errorText = turn.error_message || "App Turn failed";
      showToast(errorText, turn.status === "CANCELLED" ? "warning" : "error");
      appLog(errorText);
      if (isStaleBridgeThreadError(errorText)) {
        showStaleBridgeThreadSheet(errorText);
      }
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
  selectedAppThreadMissingFromList = false;
  writeUiState(UI_STATE_KEYS.selectedAppThreadId, selectedAppThreadId);
  await loadAppThreadList();
  updateSelectedAppThreadDisplay();
  showToast("已重开 App Thread", "success");
  appLog(`已重开 App Thread，新 bridge_thread_id=${reopened.bridge_thread_id || ""}`);
}

async function loadAppTurns() {
  if (!selectedAppThreadId) throw new Error("请先选择 App Thread");
  const turns = await api(`/app-threads/${selectedAppThreadId}/turns?limit=100`, {headers: headers()});
  appTurnsCache = turns;
  resumeActiveAppTurnPolling();
  document.getElementById("appTurns").innerHTML = turns.length
    ? turns.map(renderAppTurnConversation).join("")
    : `<div class="empty-state">
        <strong>暂无 AppTurn</strong>
        <span>请在底部输入消息后发送，或通过「更多」查看 Bridge 状态。</span>
        <button class="secondary" onclick="document.getElementById('appMessage').focus()">输入消息</button>
      </div>`;
}

function resumeActiveAppTurnPolling() {
  const activeTurns = appTurnsCache.filter(turn => ["PENDING", "RUNNING"].includes(normalizedStatus(turn.status)));
  if (!activeTurns.length) {
    if (appTurnPollTimer && selectedAppTurnId && !appTurnsCache.some(turn => turn.id === selectedAppTurnId && ["PENDING", "RUNNING"].includes(normalizedStatus(turn.status)))) {
      stopAppTurnPolling();
    }
    return;
  }
  const selectedActiveTurn = activeTurns.find(turn => turn.id === selectedAppTurnId);
  const activeTurn = selectedActiveTurn || activeTurns[activeTurns.length - 1];
  selectedAppTurnId = activeTurn.id;
  startAppTurnPolling(selectedAppTurnId);
  renderAppTurnStatus(activeTurn);
}

function selectAppTurn(turnId) {
  const turn = appTurnsCache.find(item => item.id === turnId);
  if (!turn) return;
  renderAppTurnStatus(turn);
  showAppTurnDetailSheet(turn);
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
  return `
    <div class="chat-turn">
      <div class="bubble-row user">
        <div class="bubble user" onclick="selectAppTurn(${escapeHtml(turn.id)})">
          ${escapeHtml(turn.user_message || "")}
          <span class="bubble-detail-hint">点击查看详情</span>
        </div>
      </div>
      <div class="bubble-row assistant">
        <div class="bubble assistant ${escapeHtml(statusClass(turn.status))}" onclick="selectAppTurn(${escapeHtml(turn.id)})">
          <div class="turn-meta">
            ${statusBadge(turn.status)}
            <span class="muted">duration_seconds=${escapeHtml(turn.duration_seconds ?? "")}</span>
          </div>
          ${pending ? `<div class="loading-card">${escapeHtml(APP_WAITING_TEXT)}</div>` : ""}
          ${escapeHtml(assistantBody)}
          <span class="bubble-detail-hint">点击查看详情</span>
        </div>
      </div>
    </div>`;
}

function showAppTurnDetailSheet(turn) {
  selectedAppTurnId = turn.id;
  openSheet(`App Turn #${turn.id}`, `
    <div class="task-detail-sheet">
      <div class="detail-section">
        <h3>状态</h3>
        ${statusBadge(turn.status)}
        <div class="meta-grid">
          <div class="meta-cell"><span class="meta-label">created_at</span><span class="meta-value">${escapeHtml(turn.created_at || "")}</span></div>
          <div class="meta-cell"><span class="meta-label">updated_at</span><span class="meta-value">${escapeHtml(turn.updated_at || "")}</span></div>
          <div class="meta-cell"><span class="meta-label">duration_seconds</span><span class="meta-value">${escapeHtml(turn.duration_seconds ?? "")}</span></div>
          <div class="meta-cell"><span class="meta-label">bridge_turn_id</span><span class="meta-value">${escapeHtml(turn.bridge_turn_id || "")}</span></div>
        </div>
      </div>
      <div class="detail-section">
        <h3>消息</h3>
        <p><strong>User</strong></p>
        <p>${escapeHtml(turn.user_message || "")}</p>
        <p><strong>Assistant</strong></p>
        <p>${escapeHtml(turn.assistant_final || turn.error_message || "")}</p>
      </div>
      <div class="detail-section">
        <h3>事件摘要</h3>
        ${renderEventSummaryBlock(turn.event_summary)}
      </div>
      <details>
        <summary>raw summary</summary>
        <pre>${escapeHtml(JSON.stringify(turn.event_summary || {}, null, 2))}</pre>
      </details>
    </div>`);
}

async function loadAppFinal() {
  if (!selectedAppThreadId) throw new Error("请先选择 App Thread");
  const final = await api(`/app-threads/${selectedAppThreadId}/final`, {headers: headers()});
  document.getElementById("appThreadFinal").innerHTML =
    `<strong>assistant_final</strong><br>${final.assistant_final ? escapeHtml(final.assistant_final) : `<span class="muted">暂无 assistant_final</span>`}`;
  return final;
}

async function showAppFinalSheet(button = null) {
  return withButtonLoading(button, "处理中...", async () => {
    const final = await loadAppFinal();
    openSheet("App Final", `
      <div class="task-detail-sheet">
        <div class="detail-section">
          <h3>assistant_final</h3>
          <p>${final.assistant_final ? escapeHtml(final.assistant_final) : `<span class="muted">暂无 assistant_final</span>`}</p>
        </div>
      </div>`);
    showToast("Final 已刷新", "success");
  });
}

async function loadAppEvents() {
  if (!selectedAppThreadId) throw new Error("请先选择 App Thread");
  const events = await api(`/app-threads/${selectedAppThreadId}/events`, {headers: headers()});
  renderAppEventsSummary(events);
  appLog(JSON.stringify(events, null, 2));
  return events;
}

function renderEventSummaryBlock(summary) {
  if (!summary) return `<span class="muted">无事件摘要</span>`;
  const eventCounts = summary.event_type_counts || {};
  const errors = Array.isArray(summary.errors) ? summary.errors : [];
  return `
    <div class="summary-grid">
      <div><strong>total_events</strong><br>${escapeHtml(summary.total_events ?? 0)}</div>
      <div><strong>has_error</strong><br>${escapeHtml(summary.has_error ?? false)}</div>
      <div><strong>event_type_counts</strong><br>${escapeHtml(JSON.stringify(eventCounts))}</div>
      <div><strong>assistant_text_preview</strong><br>${escapeHtml(summary.assistant_text_preview || "")}</div>
      <div><strong>errors</strong><br>${escapeHtml(JSON.stringify(errors))}</div>
    </div>`;
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

async function showAppEventsSheet(button = null) {
  return withButtonLoading(button, "处理中...", async () => {
    const events = await loadAppEvents();
    openSheet("事件摘要", `
      <div class="task-detail-sheet">
        <div class="detail-section">
          <h3>App Events</h3>
          ${renderEventSummaryBlock(events ? events.event_summary : null)}
          <span class="muted">latest_turn_id=${escapeHtml(events ? events.latest_turn_id ?? "" : "")}</span>
        </div>
        <details>
          <summary>raw summary</summary>
          <pre>${escapeHtml(JSON.stringify(events || {}, null, 2))}</pre>
        </details>
      </div>`);
    showToast("Events 已刷新", "success");
  });
}

function showAppDebugSheet() {
  openSheet("调试输出", `
    <div class="task-detail-sheet">
      <div class="detail-section">
        <h3>Debug Output</h3>
        <pre>${escapeHtml(appOutput.textContent || "暂无调试输出")}</pre>
      </div>
    </div>`);
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
  selectedAppThreadMissingFromList = false;
  selectedAppTurnId = null;
  removeUiState(UI_STATE_KEYS.selectedAppThreadId);
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
document.getElementById("homeCreateTask").onclick = () => {
  switchTab("tasks");
  renderCreateTaskSheet();
};
document.getElementById("openCreateTaskSheet").onclick = renderCreateTaskSheet;
document.getElementById("closeSheet").onclick = closeSheet;
sheetBackdrop.onclick = event => {
  if (event.target === sheetBackdrop) closeSheet();
};
document.getElementById("saveToken").onclick = () => withButtonLoading("saveToken", "处理中...", async () => {
  const token = tokenInput.value.trim();
  tokenInput.value = token;
  localStorage.setItem("apiToken", token);
  await loadAll();
  log("");
  appLog("");
  showToast("Token 已保存", "success");
});
document.getElementById("refresh").onclick = () => withButtonLoading("refresh", "处理中...", async () => {
  await loadAll();
  showToast("已刷新", "success");
});
document.getElementById("taskStatusFilter").onchange = () => {
  writeUiState(UI_STATE_KEYS.taskStatusFilter, document.getElementById("taskStatusFilter").value);
  renderFilteredTasks();
};
document.getElementById("refreshRunners").onclick = () => withButtonLoading("refreshRunners", "处理中...", async () => {
  const runners = await api("/runners", {headers: headers()});
  renderRunners(runners);
  showToast("Runner 已刷新", "success");
});
document.getElementById("checkAppBridge").onclick = () => withButtonLoading("checkAppBridge", "处理中...", checkAppServerBridge);
document.getElementById("refreshAppThreads").onclick = () => withButtonLoading("refreshAppThreads", "处理中...", async () => {
  await loadAppThreadList();
  showToast("App Threads 已刷新", "success");
});
document.getElementById("appThreadStatusFilter").onchange = () => {
  persistAppThreadFilters();
  loadAppThreadList().catch(err => {
  showToast(String(err), "error");
  appLog(String(err));
  });
};
document.getElementById("appIncludeArchived").onchange = () => {
  persistAppThreadFilters();
  loadAppThreadList().catch(err => {
  showToast(String(err), "error");
  appLog(String(err));
  });
};
document.getElementById("cleanupClosedThreads").onclick = () => withButtonLoading("cleanupClosedThreads", "处理中...", () => cleanupAppThreads("CLOSED"));
document.getElementById("cleanupErrorThreads").onclick = () => withButtonLoading("cleanupErrorThreads", "处理中...", () => cleanupAppThreads("ERROR"));
document.getElementById("recoverStaleTurns").onclick = () => withButtonLoading("recoverStaleTurns", "处理中...", recoverStaleAppTurns);
document.getElementById("createAppThread").onclick = () => withButtonLoading("createAppThread", "处理中...", createAppThread);
document.getElementById("sendAppTurn").onclick = () => withButtonLoading("sendAppTurn", "处理中...", sendAppTurn);
document.getElementById("sendAsyncAppTurn").onclick = () => withButtonLoading("sendAsyncAppTurn", "处理中...", sendAsyncAppTurn);
document.getElementById("sendAppMessage").onclick = () => withButtonLoading("sendAppMessage", "处理中...", sendAppMessage);
document.getElementById("appMessage").oninput = updateAppComposerState;
document.getElementById("appSendAsync").onchange = () => {
  persistSendMode();
  updateAppComposerState();
};
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
document.addEventListener("visibilitychange", handleVisibilityChange);
restoreInitialUiState();
updateAppComposerState();
loadAll().catch(err => {
  showToast(String(err), "error");
  log(String(err));
});
</script>
</body>"""
