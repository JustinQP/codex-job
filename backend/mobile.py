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
    .item { border-top: 1px solid #e5e7eb; padding: 9px 0; }
    .item:first-child { border-top: 0; }
    .links { display: flex; gap: 8px; flex-wrap: wrap; }
    .links a { color: #2563eb; text-decoration: none; font-size: 13px; }
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
</main>

<script>
const tokenInput = document.getElementById("token");
const output = document.getElementById("output");
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

document.getElementById("saveToken").onclick = () => {
  localStorage.setItem("apiToken", tokenInput.value);
  loadAll().catch(err => log(String(err)));
};
document.getElementById("createTask").onclick = () => createTask().catch(err => log(String(err)));
document.getElementById("refresh").onclick = () => loadAll().catch(err => log(String(err)));
document.getElementById("clearOutput").onclick = () => log("");
loadAll().catch(err => log(String(err)));
</script>
</body>
</html>"""
