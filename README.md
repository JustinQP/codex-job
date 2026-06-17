# Codex Remote Runner MVP

这是一个最小可用的 Codex Remote Runner。它提供 FastAPI 接口用于配置项目和提交任务，由本机独立 Runner 进程通过 HTTP 轮询任务，并调用 Codex CLI 在已配置项目目录中执行。

v0.5.0 起，Runner 不再直接访问后端 SQLite，也不再共享后端 `data/jobs` 目录。后端保存任务状态和上传后的产物，Runner 只通过 `/runner/...` HTTP API 注册、心跳、认领任务和回传结果。

v0.6.0 起，后端支持多 Runner 基础调度：原子 claim、Runner lease、离线检测、RUNNING 任务超时回收、任务指定 `assigned_runner_id`，以及项目默认 `default_runner_id`。

RUNNING 任务 lease 过期时默认标记为 `FAILED`，避免 Codex 进程仍在运行时被重复派发。如需自动回收到 `PENDING`，可设置：

```bat
set RECOVER_EXPIRED_TASKS_MODE=requeue
```

v0.7.0 增加移动端控制台和 Codex 参数配置：

- 手机访问 `http://<backend-host>:8000/mobile`。
- API Token 保存在手机浏览器 localStorage。
- 可选择项目、Runner、任务类型、模型、推理难度和 sandbox。
- 当前目标模式只支持一次性 GOAL/受控目标任务，不支持无限自主迭代。

v0.8.0 增加 App Server 会话模式主线集成：

- App Server Bridge 仍作为 sidecar 独立运行。
- 主后端通过 `APP_SERVER_BRIDGE_URL` 调用 Bridge。
- 主线手机控制台可以创建 App Thread、发送 App Turn、查看 final。
- 不替换 Runner/codex exec 主链路。

v0.1 只覆盖单机 MVP：

- Python + FastAPI 后端
- SQLite + SQLModel 持久化
- 独立 Python Runner 通过 HTTP 轮询任务
- 调用本机 Codex CLI
- 保存任务日志、最后结果和 `git diff`
- 不自动 `git commit`
- 不自动 `git push`
- 不提供任意 shell 命令执行接口

## 目录结构

```text
backend/
  main.py
  db.py
  models.py
  schemas.py
  services/
runner/
  runner.py
  codex_executor.py
  config.py
scripts/
  demo_create_task.py
  start.bat
data/
docs/
  01-mvp-design.md
requirements.txt
```

## 环境准备

建议使用虚拟环境：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

确认本机可以执行 Codex CLI。Runner 会优先读取 `CODEX_BIN`，未配置时依次查找 `codex.cmd`、`codex`、`codex.exe`。

可选环境变量：

```bat
set CODEX_BIN=C:\path\to\codex.cmd
set CODEX_RUNNER_DATA_DIR=E:\JustinQP\codex-job\data
set CODEX_RUNNER_DB_PATH=E:\JustinQP\codex-job\data\app.db
set RUNNER_POLL_INTERVAL_SECONDS=5
set TASK_TIMEOUT_SECONDS=7200
set REQUIRE_CLEAN_WORKTREE=true
```

任务超时时间限制：

- 默认：7200 秒
- 最小：30 秒
- 最大：21600 秒

PowerShell 示例：

```powershell
$env:CODEX_BIN="C:\path\to\codex.cmd"
```

## 一键启动

同时启动后端和 Runner：

```bat
scripts\start.bat
```

只启动后端：

```bat
scripts\start.bat api
```

只启动 Runner：

```bat
scripts\start.bat runner
```

Runner 只处理一次任务，适合 smoke test：

```bat
scripts\start.bat runner-once
```

Runner HTTP 配置：

```bat
set BACKEND_URL=http://127.0.0.1:8000
set RUNNER_ID=desktop-001
set RUNNER_TOKEN=your-token
```

`RUNNER_TOKEN` 会作为 `X-API-Token` 请求头发送；如果未设置，会回退读取 `API_TOKEN`。Runner 本地产物默认写入 `data/runner-jobs/<runner_id>/<task_id>/`，执行中会定期上传日志，执行完成后上传到后端 `data/jobs/<task_id>/`。

v0.5.2 起，Runner 对临时网络错误和 HTTP 5xx 做短重试。最终产物上传失败时，会在本地任务目录保留 `upload-pending.json`，便于恢复网络后定位待补传任务。

Runner 可声明支持的模型：

```bat
set RUNNER_SUPPORTED_MODELS=gpt-5,gpt-5-codex
```

默认地址：

- 管理页面：http://127.0.0.1:8000/
- API 文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/health

## HTML 管理页面

v0.2.0 提供一个简单 HTML 管理页面，不引入 Vue 或前端构建工具。

页面入口：

```text
http://127.0.0.1:8000/
```

支持：

- 查看项目列表
- 创建任务
- 选择任务类型：`PLAN`、`IMPLEMENT`、`REVIEW`、`TEST_FIX`、`DOCS`、`COMMIT`
- 查看任务列表
- 按项目、状态、数量筛选任务
- 查看任务详情
- 打开 log/result/diff
- 基于旧任务 prompt 重跑
- 取消 `PENDING` 或 `RUNNING` 任务

## 手动启动

启动后端：

```bash
uvicorn backend.main:app --reload
```

持续启动 Runner：

```bash
python runner/runner.py
```

Runner 只处理一次任务：

```bash
python runner/runner.py --once
```

## 创建项目

```bat
curl -X POST http://127.0.0.1:8000/projects ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"demo\",\"path\":\"E:\\JustinQP\\codex-job\",\"enabled\":true}"
```

PowerShell：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/projects `
  -ContentType "application/json" `
  -Body '{"name":"demo","path":"E:\JustinQP\codex-job","enabled":true}'
```

## 创建任务

```bat
curl -X POST http://127.0.0.1:8000/tasks ^
  -H "Content-Type: application/json" ^
  -d "{\"project_id\":1,\"prompt\":\"请查看 README.md 并总结项目用途。\",\"timeout_seconds\":7200}"
```

PowerShell：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/tasks `
  -ContentType "application/json" `
  -Body '{"project_id":1,"prompt":"请查看 README.md 并总结项目用途。","timeout_seconds":7200}'
```

指定 Runner 执行任务：

```json
{
  "project_id": 1,
  "prompt": "请检查 README.md",
  "assigned_runner_id": "desktop-001"
}
```

项目也可以配置默认 Runner：

```json
{
  "name": "demo",
  "path": "E:\\JustinQP\\codex-job",
  "default_runner_id": "desktop-001"
}
```

`assigned_runner_id` 和 `default_runner_id` 必须指向已注册过的 Runner，否则 API 会返回 400。

Codex 参数可在项目默认配置或任务创建时设置：

```json
{
  "model": "gpt-5",
  "reasoning_effort": "high",
  "sandbox": "workspace-write"
}
```

任务创建时参数优先级：

```text
Task payload > Project default > system default
```

`sandbox` 默认是 `workspace-write`。`model=default` 或 `reasoning_effort=default` 不会额外传给 Codex CLI。

## 手机控制台

主线手机控制台入口：

```text
http://127.0.0.1:8000/mobile
```

局域网手机访问时，将 `127.0.0.1` 换成后端机器的局域网 IP。页面支持：

- 保存 API Token 到 localStorage。
- 查看 Runner 列表和状态。
- 选择项目、Runner、任务类型、模型、推理难度、sandbox。
- 提交任务、查看最近任务、查看 log/result/diff、取消任务。
- v0.8.0 起，可在主线手机控制台中检查 App Server Bridge、创建 App Thread、发送 App Turn、查看 turns/final、关闭 App Thread。
- v0.8.2 起，App Server 会话区会显示当前选中 thread、最近 final、turn 数量，并提供独立状态输出区和 final/events 查看按钮。

当前目标模式只提交一次受控目标任务，不做无限自主迭代。

## App Server POC

App Server POC 是独立 sidecar 链路，只在 `poc/app_server` 下运行。v0.8.0 起，主后端可以通过 HTTP 调用该 sidecar 创建 App Thread 和发送 App Turn，但它仍不替换当前 `codex exec` Runner 主链路。

入口区分：

```text
主线手机控制台：
http://127.0.0.1:8000/mobile

App Server POC 手机控制台：
http://127.0.0.1:8766/mobile
```

启动 App Server POC Bridge：

```powershell
$env:APP_SERVER_BRIDGE_TOKEN="dev-token"
python .\poc\app_server\app_server_bridge.py --host 127.0.0.1 --port 8766
```

POC 当前限制见 `poc/app_server/README.md`。不要将该 POC 公网暴露；如需手机局域网访问，必须设置 `APP_SERVER_BRIDGE_TOKEN`。

v0.8.0 启动顺序：

```powershell
# 1. 启动 App Server Bridge sidecar
$env:APP_SERVER_BRIDGE_TOKEN="dev-token"
python .\poc\app_server\app_server_bridge.py --host 127.0.0.1 --port 8766

# 2. 启动主后端
$env:API_TOKEN="dev-token"
$env:APP_SERVER_BRIDGE_URL="http://127.0.0.1:8766"
$env:APP_SERVER_BRIDGE_TOKEN="dev-token"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# 3. 打开主线手机控制台
http://127.0.0.1:8000/mobile
```

v0.8.2 主线 App Server 会话 smoke：

```powershell
# 1. 启动 App Server Bridge sidecar
$env:APP_SERVER_BRIDGE_TOKEN="dev-token"
python .\poc\app_server\app_server_bridge.py --host 127.0.0.1 --port 8766

# 2. 启动主后端
$env:API_TOKEN="dev-token"
$env:APP_SERVER_BRIDGE_URL="http://127.0.0.1:8766"
$env:APP_SERVER_BRIDGE_TOKEN="dev-token"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# 3. 运行主线 App Server 会话 smoke
$env:API_TOKEN="dev-token"
python .\scripts\smoke_app_server_flow.py --base-url http://127.0.0.1:8000 --project-path F:\JustinKing\codex-job
```

`smoke_app_server_flow.py` 只访问主后端 `8000`，不直接访问 Bridge `8766`。如果 `assistant_final` 包含 `app-thread-smoke-ok`，则 smoke 判定通过。

App Server 会话模式第一版是同步阻塞调用。Bridge sidecar 不可用时，App Thread API 返回 `502`、`503` 或 `504`。当前不持久化完整事件流，只保存最近 summary/final，不支持 SSE、审批 UI 或 diff UI。

## v0.8.3 App Server 日常使用流程

### 1. 一键启动

在项目根目录运行：

```powershell
.\scripts\start_app_server_stack.ps1 -ApiToken dev-token -BridgeToken dev-token
```

带 smoke：

```powershell
.\scripts\start_app_server_stack.ps1 -ApiToken dev-token -BridgeToken dev-token -RunSmoke
```

脚本会分别启动 App Server Bridge sidecar 和主后端，并输出主线 mobile、Bridge POC mobile 与 smoke 命令。

### 2. 手动启动

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

### 3. Smoke

```powershell
$env:API_TOKEN="dev-token"
python .\scripts\smoke_app_server_flow.py --base-url http://127.0.0.1:8000 --project-path F:\JustinKing\codex-job
```

smoke 脚本只访问主后端 `8000`。如果创建 AppThread 后后续步骤失败，脚本会尽量调用 `DELETE /app-threads/{id}` 清理残留。

### 4. 常见问题

Q1: `/app-server-bridge/health` 返回 `503`  
A: Bridge sidecar 没启动，或 `APP_SERVER_BRIDGE_URL` 配错。

Q2: AppThread 发送失败，提示 `thread_not_found` / bridge thread missing  
A: Bridge 重启后内存态 thread 丢失，点击“重开 App Thread”。

Q3: smoke 失败后残留 AppThread  
A: v0.8.3 smoke 会尽量自动 `DELETE`；如仍残留，可在 mobile 中关闭。

Q4: 手机打不开 `127.0.0.1:8000/mobile`  
A: 手机访问时要使用电脑局域网 IP，不是 `127.0.0.1`。

Q5: 不要公网暴露  
A: 当前仍是本地可信局域网工具，API Token 保存在 localStorage。

## v0.9.0 App Turn 异步执行

v0.9.0 新增异步 App Turn 链路，保留原有同步接口不变。

### 1. 异步 API

```text
POST /app-threads/{id}/turns/async
GET  /app-turns/{turn_id}
```

`POST /app-threads/{id}/turns/async` 会立即创建 `PENDING` AppTurn 并提交到单进程后台线程池。手机端可以通过 `GET /app-turns/{turn_id}` 轮询 `PENDING` / `RUNNING` / `SUCCESS` / `FAILED` 状态。

### 2. 异步 smoke

```powershell
$env:API_TOKEN="dev-token"
python .\scripts\smoke_app_server_flow.py --base-url http://127.0.0.1:8000 --project-path F:\JustinKing\codex-job --async-turn
```

### 3. 当前限制

- 当前异步执行是单进程线程池。
- 服务重启后 `RUNNING` / `PENDING` AppTurn 不会自动恢复。
- 不支持取消。
- 不支持 SSE。
- 不支持审批 UI。
- 不支持 diff UI。
- 不替换 Runner/codex exec 主链路。

## Demo 脚本

在后端启动后运行：

```bash
python scripts/demo_create_task.py --project-path E:\JustinQP\codex-job
```

如果已经有项目 ID：

```bash
python scripts/demo_create_task.py --project-id 1 --prompt "请检查 README.md 是否清晰。"
```

## 查看任务

```bash
curl http://127.0.0.1:8000/tasks
curl "http://127.0.0.1:8000/tasks?project_id=1&status=PENDING&limit=50"
curl http://127.0.0.1:8000/tasks/1
curl http://127.0.0.1:8000/tasks/1/log
curl http://127.0.0.1:8000/tasks/1/result
curl http://127.0.0.1:8000/tasks/1/diff
```

`GET /tasks` 支持：

- `project_id`：按项目过滤
- `status`：按状态过滤，取值为 `PENDING`、`RUNNING`、`SUCCESS`、`FAILED`、`CANCELLED`
- `limit`：默认 50，最大 200

任务响应不会暴露本机绝对路径，只返回：

```text
log_url
result_url
diff_url
```

## v0.5.0 本机 HTTP smoke test

以下步骤验证 Runner 通过 HTTP 注册、认领任务、上传日志和产物，不直接访问后端 SQLite：

1. 启动后端：

```bat
set API_TOKEN=dev-token
scripts\start.bat api
```

2. 新开终端，创建项目和任务：

```powershell
$headers = @{ "X-API-Token" = "dev-token" }
$project = Invoke-RestMethod -Method Post http://127.0.0.1:8000/projects `
  -Headers $headers `
  -ContentType "application/json" `
  -Body '{"name":"codex-job","path":"E:\JustinQP\codex-job","enabled":true}'

$task = Invoke-RestMethod -Method Post http://127.0.0.1:8000/tasks `
  -Headers $headers `
  -ContentType "application/json" `
  -Body (@{project_id=$project.id; prompt="请查看 README.md 并总结项目用途。"; timeout_seconds=7200} | ConvertTo-Json)
```

3. 新开终端，启动一次性 Runner：

```bat
set BACKEND_URL=http://127.0.0.1:8000
set RUNNER_ID=desktop-001
set RUNNER_TOKEN=dev-token
scripts\start.bat runner-once
```

4. 查看结果：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/tasks/$($task.id) -Headers $headers
Invoke-RestMethod http://127.0.0.1:8000/tasks/$($task.id)/log -Headers $headers
Invoke-RestMethod http://127.0.0.1:8000/tasks/$($task.id)/result -Headers $headers
Invoke-RestMethod http://127.0.0.1:8000/tasks/$($task.id)/diff -Headers $headers
```

预期结果：

- Runner 窗口显示正在连接 `BACKEND_URL` 并处理任务。
- 任务状态从 `PENDING` 变为 `RUNNING`，最终变为 `SUCCESS`、`FAILED` 或 `CANCELLED`。
- 后端 `data/jobs/<task_id>/` 能看到 Runner 通过 HTTP 上传的 `run.log`、`result.md`、`diff.patch` 等产物。

## 重跑任务

```bash
curl -X POST http://127.0.0.1:8000/tasks/1/rerun
```

重跑会复制原任务的 `project_id`、`prompt`、`timeout_seconds`、`task_type`、`assigned_runner_id`、`model`、`reasoning_effort` 和 `sandbox`，创建一个新的 `PENDING` 任务，并生成新的任务产物路径。

## 取消任务

```bash
curl -X POST http://127.0.0.1:8000/tasks/1/cancel
```

- `PENDING` 任务会直接变为 `CANCELLED`。
- `RUNNING` 任务会标记 `cancel_requested=true`，Runner 轮询到取消请求后会终止 Codex 进程树，并将任务状态更新为 `CANCELLED`。

## 工程化工作流

任务支持 `task_type`：

```text
PLAN
IMPLEMENT
REVIEW
TEST_FIX
DOCS
COMMIT
```

内置模板接口：

```bash
curl http://127.0.0.1:8000/task-templates
```

项目配置支持以下工作流字段：

```text
test_command
smoke_check_command
default_branch
require_clean_worktree
```

Runner 会生成：

```text
data/jobs/<task_id>/test-output.txt
data/jobs/<task_id>/task-report.md
```

v0.3.0 中 `test_command` 和 `smoke_check_command` 只记录到报告，不自动执行，避免引入远程任意 shell 执行风险。

## 远程安全边界

可选启用 API Token：

```bat
set API_TOKEN=your-token
```

启用后，除 `/health` 外，所有 API 读写接口都需要请求头：

```text
X-API-Token: your-token
```

HTML GET 页面和 UI 表单写接口也会执行同样的 token 校验。当前 HTML 页面不提供登录或 token 输入框，因此启用 `API_TOKEN` 后建议使用 API 调用查看、创建、重跑和取消任务。

可选限制项目路径白名单：

```bat
set PROJECT_PATH_WHITELIST=E:\JustinQP
```

多个路径在 Windows 下使用分号分隔。项目 API 和页面不会返回本机绝对路径。

白名单会在创建项目时校验，也会在 Runner 执行任务前再次校验。即使数据库中已有项目路径，只要当前不在 `PROJECT_PATH_WHITELIST` 下，Runner 也会拒绝执行。

兼容的 Runner 查询接口：

```text
POST /runners/register
POST /runners/heartbeat
GET  /runners
```

v0.5.0 Runner 专用 HTTP API：

```text
POST /runner/register
POST /runner/heartbeat
POST /runner/tasks/claim
POST /runner/tasks/{task_id}/log
POST /runner/tasks/{task_id}/artifacts
POST /runner/tasks/{task_id}/finish
GET  /runner/tasks/{task_id}/cancel-state
```

任务产物默认保存到：

```text
data/jobs/<task_id>/
  run.log
  result.md
  diff.patch
  git-status.txt
  diff-unstaged.patch
  diff-staged.patch
  untracked-files.txt
  test-output.txt
  task-report.md
```

说明：

- `/tasks/{task_id}/diff` 仍然保留，返回组合后的 `diff.patch`。
- `diff-unstaged.patch` 保存未暂存改动。
- `diff-staged.patch` 保存已暂存改动。
- `untracked-files.txt` 保存未跟踪文件列表，不保存未跟踪文件内容。

## Git 工作区检查

Runner 执行任务前会检查项目是否为 git 仓库。

默认要求工作区干净：

```bat
set REQUIRE_CLEAN_WORKTREE=true
```

如果 `git status --porcelain` 非空，任务会直接进入 `FAILED`，错误原因会写入 `run.log` 和 `error_message`。

如需允许在非干净工作区执行：

```bat
set REQUIRE_CLEAN_WORKTREE=false
```

即使关闭干净工作区要求，项目仍必须是 git 仓库。

## Runner 锁

同一个 `data` 目录下只允许一个 Runner 运行。Runner 会创建：

```text
data/runner.lock
```

Runner 正常退出或收到中断时会尽量清理该锁文件。如果异常退出后锁文件残留，并确认没有 Runner 进程运行，可以手动删除。

v0.1.2 起，Runner 会读取 lock 文件中的 `pid`。如果进程不存在，会自动清理 stale lock；如果进程仍存在，会拒绝启动。

## 基础自检

```bash
python -m compileall backend runner scripts
pytest -q
python -c "from backend.db import init_db; init_db(); print('db ok')"
```

## 当前限制

- 暂不支持用户登录、细粒度权限、审计。
- `API_TOKEN` 只是共享密钥保护，不是完整账号体系。
- Runner 不再直接访问 SQLite 或后端 `data/jobs`，但仍不是多租户调度系统。
- `upload-pending.json` 只记录待补传状态，暂未提供自动补传队列。
- 暂不支持任务自动重试和全文搜索。
- 单个 Runner 本地仍使用 lock 文件限制同一 data 目录下的重复启动；多个 Runner 需要使用不同 `RUNNER_ID` 和独立本地 data 目录。
