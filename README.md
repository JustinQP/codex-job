# Codex Remote Runner

当前版本：v1.0.0

Mobile UI 当前迭代：v1.2


Mobile Frontend current iteration: v1.7.0. Added `frontend/` Vite + React + TypeScript skeleton; `/mobile` serves `frontend/dist/index.html` first.
定位：Codex Remote Runner + App Server Sidecar 本地控制台

## 1. 项目定位

本项目是一个面向本地/可信局域网使用的 Codex Remote Runner 控制台。

主线能力是通过独立 Runner 执行 `codex exec` 任务：

```text
mobile / API
  ↓
backend/main.py
  ↓
Task API
  ↓
runner
  ↓
codex exec
```

App Server 能力是 experimental sidecar POC，用于探索 `codex app-server` 会话模式：

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

App Server Bridge 仍作为 sidecar 独立运行，不替代 Runner/codex exec 主链路。当前不建议公网暴露。

## 2. 核心能力

- 项目配置：管理本机项目路径、默认 Runner、模型、推理难度和 sandbox。
- Task 主线：通过 HTTP API 创建任务，由独立 Runner 轮询、执行、上传日志和产物。
- Runner 调度：支持 Runner 注册、心跳、任务认领、取消状态查询。
- 手机控制台：在手机浏览器中提交任务、查看任务、控制 App Server 会话。
- App Server sidecar：支持 AppThread、同步/异步 AppTurn、轮询、本地取消、reopen、recover-stale、event summary、筛选和 archived 清理。
- Smoke 验收：提供主线 App Server 会话 smoke 脚本和文档化验收矩阵。

## 3. 快速开始

### 环境准备

建议使用虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

确认本机可以执行 Codex CLI。Runner 会优先读取 `CODEX_BIN`，未配置时依次查找 `codex.cmd`、`codex`、`codex.exe`。

### 一键启动 App Server 栈

```powershell
.\scripts\start_app_server_stack.ps1 -ApiToken dev-token -BridgeToken dev-token
```

带 smoke：

```powershell
.\scripts\start_app_server_stack.ps1 -ApiToken dev-token -BridgeToken dev-token -RunSmoke
```

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

v1.7.0 only wires the frontend build and FastAPI hosting path. Full task and App Server session pages will be migrated in later v1.7.x steps.

## 4. 主线 Runner/codex exec 任务链路

主线任务链路用于执行一次性 `codex exec` 任务。

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
- 异步发送 AppTurn 并轮询状态。
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
- 查看 Runner 列表和状态。
- 选择项目、Runner、任务类型、模型、推理难度、sandbox。
- 提交任务、查看最近任务、查看 log/result/diff、取消任务。
- 检查 App Server Bridge。
- 创建、选择、关闭、重开 AppThread。
- 同步/异步发送 AppTurn。
- 刷新当前 turn、取消当前 turn。
- 查看 final 和 event summary。
- recover stale AppTurn。
- AppThread 状态筛选和 archived 清理。

页面是本地 POC 控制台，不做完整登录系统。启用 `API_TOKEN` 后，页面会把 Token 作为 `X-API-Token` 请求头发送。

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
- Projects：`GET /projects`、`POST /projects`
- Tasks：`GET /tasks`、`POST /tasks`、`GET /tasks/{id}`、`POST /tasks/{id}/cancel`、`POST /tasks/{id}/rerun`
- Runners：`POST /runner/register`、`POST /runner/heartbeat`、`POST /runner/tasks/claim`
- App Server Bridge：`GET /app-server-bridge/health`
- AppThreads：`GET /app-threads`、`POST /app-threads`、`PATCH /app-threads/{id}`、`DELETE /app-threads/{id}`、`POST /app-threads/{id}/reopen`、`POST /app-threads/cleanup`
- AppTurns：`POST /app-threads/{id}/turns`、`POST /app-threads/{id}/turns/async`、`GET /app-turns/{id}`、`POST /app-turns/{id}/cancel`、`POST /app-turns/recover-stale`

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
- App Server 仍是 experimental sidecar POC。
- App Server 异步执行是单进程线程池。
- 服务重启后不会继续执行 `RUNNING` / `PENDING` AppTurn，会将其恢复为 `FAILED`。
- 取消是本地状态取消，不保证中断正在执行的 Codex App Server turn。
- `APP_TURN_EXECUTION_TIMEOUT_SECONDS` 是 Bridge HTTP 调用超时，不是强杀 Codex 子进程。
- 不支持 SSE。
- 不支持审批 UI。
- 不支持 diff UI。
- 不替换 Runner/codex exec 主链路。
- 不做公网部署。

## 12. 版本摘要

- v0.5：Runner 不再直接访问后端 SQLite，改为 HTTP 轮询和上传产物。
- v0.6：多 Runner 基础调度、Runner lease、离线检测、运行中任务恢复策略。
- v0.7：移动端控制台和 Codex 参数配置。
- v0.8：App Server Bridge sidecar 主线集成、主线 smoke、一键启动、AppThread reopen。
- v0.9：异步 AppTurn、轮询、本地取消、并发保护、stale recovery、event summary、筛选和 archived 清理。
- v1.0：稳定版收口，README/docs 重构，验收矩阵固化。
- v1.1：Mobile 控制台 UI/UX 重构；v1.1.2 已优化任务创建、最近任务卡片和任务详情卡，计划见 `docs/mobile-ui-ux-v1.1-plan.md`。
