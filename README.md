# Codex Job

当前版本：v2.0.0

Mobile Frontend current iteration: v2.0.0 multi-device control plane. The mobile console lives in `frontend/` with Vite + React + TypeScript; `/mobile` serves `frontend/dist/index.html` first.
Mobile 前端现在是会话优先结构：会话 / 项目 / 运行 / 我的。运行是底层 Task / Runner 执行记录，不再作为主交互入口。
定位：单用户 Codex Control Plane + Device Agent 本地控制台

## 1. 项目定位

本项目是一个面向本地/可信局域网使用的个人 Codex 控制台。

v2.0 主线能力是 Control Plane + Device Agent：

```text
mobile / API (control plane)
  ↓
backend/main.py
  ↓
AgentCommand 持久化命令队列
  ↓
agent/main.py on selected device
  ↓
workspace registry
  ↓
codex exec / codex app-server
```

旧 Runner/codex exec 链路保留为 deprecated fallback，用于 `AGENT_COMMAND_MODE=false` 回退。旧 App Server Bridge POC 仍保留给本机 sidecar smoke 和兼容路径；多设备目标应优先通过 Device Agent 执行。

Device Agent 会在每台电脑本地保存稳定设备身份、读取本机 Workspace Registry、向控制端同步可用工作目录，并轮询属于该设备的命令。

App Server sidecar 兼容路径：

```text
mobile / API
  ↓
backend/main.py
  ↓
App Thread / App Turn API
  ↓
backend/services/app_thread_service.py
  ↓
backend/services/app_turn_executor.py
  ↓
backend/services/app_server_bridge_client.py
  ↓ HTTP
poc/app_server/app_server_bridge.py
  ↓ stdio
codex app-server
```

App Server Bridge 仍作为 sidecar 独立运行。当前不建议公网暴露。

## 2. 核心能力

- 设备管理：Agent 注册、心跳、在线/离线状态和设备级命令轮询。
- Workspace Registry：每台设备只暴露本机显式注册的工作目录。
- Agent Run 主线：通过 Workspace 创建 Run，由对应设备 Agent 执行并上传日志和产物。
- 连续 Session：通过 Workspace 创建 AppThread/AppTurn，Agent 侧复用同一 Codex App Server 会话。
- 手机控制台：在手机浏览器中选择设备、Workspace、项目、会话和运行记录。
- 旧 Runner fallback：deprecated，支持旧 `/tasks` + `/runner/*` 链路回退。
- Smoke 验收：提供 App Server 会话 smoke、迁移验证、fake Agent 和安装脚本验收入口。

项目文档、当前路线图和历史归档入口见 `docs/README.md`。

## 3. 快速开始

### 环境准备

建议使用虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

确认每台执行设备可以运行 Python 和 Codex CLI。旧 Runner 会优先读取 `CODEX_BIN`，未配置时依次查找 `codex.cmd`、`codex`、`codex.exe`；Device Agent 通过本机命令执行器调用 Codex。

### 启动 Control Plane

本机开发可继续使用一键启动脚本：

```powershell
.\scripts\start_app_server_stack.ps1 -ApiToken dev-token -BridgeToken dev-token
```

带 smoke：

```powershell
.\scripts\start_app_server_stack.ps1 -ApiToken dev-token -BridgeToken dev-token -RunSmoke
```

多设备 Agent 主线建议显式启动后端：

```powershell
$env:API_TOKEN="dev-token"
$env:AGENT_TOKEN="agent-dev-token"
$env:AGENT_COMMAND_MODE="true"
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

手机访问：

```text
http://<control-plane-lan-ip>:8000/mobile
```

### 配置第二台电脑的 Device Agent

1. 在第二台电脑克隆或同步本仓库，并安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

2. 创建 Agent Workspace 配置，例如 `data\agent\workspaces.json`：

```json
{
  "allowed_roots": [
    "F:/JustinKing"
  ],
  "workspaces": [
    {
      "key": "codex-job",
      "name": "Codex Job",
      "path": "F:/JustinKing/codex-job",
      "enabled": true
    }
  ]
}
```

3. 设置环境变量并注册、同步 Workspace：

```powershell
$env:BACKEND_URL="http://<control-plane-lan-ip>:8000"
$env:AGENT_TOKEN="agent-dev-token"
$env:CODEX_AGENT_DATA_DIR="data\agent"
$env:CODEX_AGENT_WORKSPACES_FILE="data\agent\workspaces.json"
$env:CODEX_AGENT_DISPLAY_NAME="Desk B"
python -m agent.main --register
python -m agent.main --sync-workspaces
python -m agent.main --run-loop
```

4. 需要 Windows 自启动时，先检查环境，再安装计划任务：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install_windows_agent.ps1 -Action Check -BackendUrl http://<control-plane-lan-ip>:8000 -AgentToken agent-dev-token
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install_windows_agent.ps1 -Action Install -BackendUrl http://<control-plane-lan-ip>:8000 -AgentToken agent-dev-token -Force
```

卸载只删除 Windows Task Scheduler 启动项，不删除 Workspace、项目文件或 `data\agent`。

### 手动启动

窗口 1：启动 App Server Bridge sidecar。

```powershell
$env:APP_SERVER_BRIDGE_TOKEN="dev-token"
python .\poc\app_server\app_server_bridge.py --host 127.0.0.1 --port 8766
```

窗口 2：启动主后端。

```powershell
$env:API_TOKEN="dev-token"
$env:APP_SERVER_BRIDGE_URL="http://127.0.0.1:8766"
$env:APP_SERVER_BRIDGE_TOKEN="dev-token"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

访问：

```text
http://127.0.0.1:8000/mobile
```

If `/mobile` is opened before the frontend is built, the backend returns a clear build-missing page. Build with:
```powershell
cd frontend
npm install
npm run build
```

For frontend development, run the Vite dev server separately:
```powershell
cd frontend
npm install
npm run dev
```

Frontend structure:
```text
frontend/src/api        API client and endpoint modules
frontend/src/components React pages and shared UI components
frontend/src/hooks      polling, toast, and localStorage hooks
frontend/src/styles     tokens, base, component, task, session, and app styles
frontend/src/utils      date, error, and text helpers
```

FastAPI hosts the production build:
- `/mobile` returns `frontend/dist/index.html` when present.
- `/assets/*` serves `frontend/dist/assets/*`.
- If the build is missing, `/mobile` returns a clear build instruction page.

v2.0 keeps the primary mobile navigation as 会话 / 项目 / 运行 / 我的. 项目页用于选择设备、Workspace 和当前项目；会话页用于连续 Session；运行页用于查看 Run/Task 记录。

## 4. Deprecated Runner/codex exec 回退链路

旧 Runner 任务链路用于执行一次性 `codex exec` 任务，当前仅作为回退链路保留。

边界：

- `AGENT_COMMAND_MODE=false` 时仍可使用旧 `/tasks` + `/runner/*` 链路。
- `AGENT_COMMAND_MODE=true` 时，通过 `/runs` 创建的新 Agent Run 绑定 Device/Workspace/AgentCommand，不进入旧 Runner 认领队列。
- 不删除旧表、历史记录或 `runner/` 代码；旧接口在 OpenAPI 中标记为 deprecated。

常用启动方式：

```powershell
# 启动后端
scripts\start.bat api

# 启动持续 Runner
scripts\start.bat runner

# Runner 只处理一次任务
scripts\start.bat runner-once
```

常用环境变量：

```powershell
$env:API_TOKEN="dev-token"
$env:BACKEND_URL="http://127.0.0.1:8000"
$env:RUNNER_ID="desktop-001"
$env:RUNNER_TOKEN="dev-token"
$env:CODEX_BIN="C:\path\to\codex.cmd"
```

Task 创建时可指定：

- `project_id`
- `prompt`
- `timeout_seconds`
- `task_type`
- `assigned_runner_id`
- `model`
- `reasoning_effort`
- `sandbox`

Runner 会上传日志和产物到后端 `data/jobs/<task_id>/`。后端 API 不直接暴露本机绝对路径，只返回 `log_url`、`result_url`、`diff_url` 等访问入口。

## 5. App Server sidecar 会话链路

App Server sidecar 会话链路用于验证 `codex app-server` 的会话能力。

关键边界：

- Bridge sidecar 独立运行。
- 主后端只通过 HTTP 调用 Bridge。
- 不在 `backend/main.py` 中直接启动 `codex app-server`。
- 不替代 Runner/codex exec 主链路。
- Bridge 重启后旧 `bridge_thread_id` 可能失效，可以使用 AppThread `reopen`。
- 后端重启后 `PENDING` / `RUNNING` AppTurn 会被 `recover-stale` 标记为 `FAILED`。

App Server 会话能力包括：

- 创建、查看、重命名、关闭、重开 AppThread。
- 同步发送 AppTurn。
- 异步发送 AppTurn并通过 SSE 或轮询查看状态。
- 同一 AppThread 的异步 turn 并发保护。
- 本地取消 AppTurn。
- 查看 final 和 event summary。
- AppThread/AppTurn 状态筛选。
- 将 `CLOSED` / `ERROR` AppThread 标记为 `[archived]`。

## 6. 手机控制台

入口：

```text
http://127.0.0.1:8000/mobile
```

局域网手机访问时，将 `127.0.0.1` 换成后端机器的局域网 IP。

手机控制台支持：

- 保存 API Token 到 localStorage。
- 查看设备、Workspace、Runner fallback 和 Bridge 诊断。
- 选择当前设备、Workspace 和项目。
- 在当前 Workspace 创建或继续会话。
- 查看运行记录、log/result/diff，必要时重跑或取消运行。
- 检查 App Server Bridge。
- 创建、选择、关闭、重开 AppThread。
- 同步/异步发送 AppTurn。
- 增量查看当前 turn 输出，必要时回退轮询。
- 刷新当前 turn、取消当前 turn。
- 查看 final 和 event summary。
- recover stale AppTurn。
- AppThread 状态筛选和 archived 清理。

页面是本地个人控制台，不做完整登录系统。启用 `API_TOKEN` 后，页面会把 Token 作为 `X-API-Token` 请求头发送。

## 7. Smoke 验收矩阵

### 后端基础自检

```powershell
python -m compileall backend runner scripts poc/app_server
pytest -q
```

### App Server 同步 smoke

```powershell
$env:API_TOKEN="dev-token"
python .\scripts\smoke_app_server_flow.py --base-url http://127.0.0.1:8000 --project-path F:\JustinKing\codex-job
```

### App Server 异步 smoke

```powershell
$env:API_TOKEN="dev-token"
python .\scripts\smoke_app_server_flow.py --base-url http://127.0.0.1:8000 --project-path F:\JustinKing\codex-job --async-turn
```

### App Server 并发保护 smoke

```powershell
$env:API_TOKEN="dev-token"
python .\scripts\smoke_app_server_flow.py --base-url http://127.0.0.1:8000 --project-path F:\JustinKing\codex-job --async-turn --check-async-conflict
```

### stale turn 恢复 smoke

```powershell
$env:API_TOKEN="dev-token"
python .\scripts\smoke_app_server_flow.py --base-url http://127.0.0.1:8000 --recover-stale
```

更多验收步骤见 `docs/smoke-checklist.md`。

## 8. API 概览

除 `/health` 和 `/mobile` 页面本身外，启用 `API_TOKEN` 后，主要 API 都需要请求头：

```text
X-API-Token: dev-token
```

主要 API 分组：

- Health：`GET /health`
- Devices：`GET /devices`、`GET /devices/{id}`
- Workspaces：`GET /workspaces`、`GET /workspaces/{id}`
- Projects：`GET /projects`、`POST /projects`
- Runs：`POST /runs`
- Tasks：`GET /tasks`、`POST /tasks`、`GET /tasks/{id}`、`POST /tasks/{id}/cancel`、`POST /tasks/{id}/rerun`
- Agent：`POST /agent/register`、`POST /agent/heartbeat`、`POST /agent/workspaces/sync`、`POST /agent/commands/claim`
- Runners：deprecated，`POST /runner/register`、`POST /runner/heartbeat`、`POST /runner/tasks/claim`
- App Server Bridge：`GET /app-server-bridge/health`
- AppThreads：`GET /app-threads`、`POST /app-threads`、`PATCH /app-threads/{id}`、`DELETE /app-threads/{id}`、`POST /app-threads/{id}/reopen`、`POST /app-threads/cleanup`
- AppTurns：`POST /app-threads/{id}/turns`、`POST /app-threads/{id}/turns/async`、`GET /app-turns/{id}`、`GET /app-turns/{id}/stream`、`POST /app-turns/{id}/cancel`、`POST /app-turns/recover-stale`

完整说明见 `docs/api-overview.md`。

## 9. 状态机

### AppThread

```text
CREATED
ACTIVE
ERROR
CLOSED
```

典型流转：

```text
CREATED -> ACTIVE
ACTIVE -> ERROR
ACTIVE -> CLOSED
ERROR -> ACTIVE by reopen
CLOSED -> ACTIVE by reopen
```

### AppTurn

```text
PENDING
RUNNING
SUCCESS
FAILED
CANCELLED
```

典型流转：

```text
PENDING -> RUNNING -> SUCCESS
PENDING -> RUNNING -> FAILED
PENDING -> CANCELLED
RUNNING -> CANCELLED
PENDING/RUNNING -> FAILED by recover-stale
```

更多状态说明见 `docs/state-machines.md`。

## 10. 常见问题

Q1: `/app-server-bridge/health` 返回 `503`  
A: Bridge sidecar 没启动，或 `APP_SERVER_BRIDGE_URL` 配错。

Q2: AppThread 发送失败，提示 `thread_not_found` / bridge thread missing  
A: Bridge 重启后内存态 thread 丢失，点击“重开 App Thread”。

Q3: smoke 失败后残留 AppThread  
A: smoke 脚本会尽量调用 `DELETE /app-threads/{id}` 清理残留；如仍残留，可在 mobile 中关闭或清理 archived。

Q4: 手机打不开 `127.0.0.1:8000/mobile`  
A: 手机访问时要使用电脑局域网 IP，不是 `127.0.0.1`。

Q5: 可以公网暴露吗？  
A: 不建议。当前主要面向本地/可信局域网使用，API Token 不是完整多用户权限系统。

## 11. 当前限制

- 当前主要面向本地/可信局域网使用。
- API Token 不是完整多用户权限系统。
- Agent Token 和 API Token 分离，但没有 Token 管理 UI。
- Workspace 必须在设备本地 registry 中显式配置，控制端不接受任意 cwd。
- App Server Bridge POC 仍保留为 deprecated sidecar fallback；正式多设备路径优先使用 Agent 模块。
- F05 真实双设备 smoke 已按用户指令越过，当前 release checklist 将其列为未验证项。
- 不支持审批 UI。
- 不支持 diff UI。
- 旧 Runner/codex exec 链路仅作为 deprecated fallback 保留。
- 不做公网部署。

## 12. 版本摘要

- v0.5：Runner 不再直接访问后端 SQLite，改为 HTTP 轮询和上传产物。
- v0.6：多 Runner 基础调度、Runner lease、离线检测、运行中任务恢复策略。
- v0.7：移动端控制台和 Codex 参数配置。
- v0.8：App Server Bridge sidecar 主线集成、主线 smoke、一键启动、AppThread reopen。
- v0.9：异步 AppTurn、轮询、本地取消、并发保护、stale recovery、event summary、筛选和 archived 清理。
- v1.0：稳定版收口，README/docs 重构，验收矩阵固化。
- v1.1-v1.7：Mobile UI、会话体验和前端工程化迭代，历史计划见 `docs/90-archive/README.md`。
- v1.8：Mobile 切换为“会话 / 项目 / 运行 / 我的”的 conversation-first 产品结构，并增加 AppTurn 增量 SSE 展示。
- v2.0：引入 Control Plane + Device Agent、多设备 Workspace、AgentCommand 命令通道、Agent Run、连续 Session、事件持久化和旧 Runner deprecated fallback。
