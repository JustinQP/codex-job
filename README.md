# Codex Remote Runner MVP

这是一个最小可用的 Codex Remote Runner。它提供 FastAPI 接口用于配置项目和提交任务，由本机独立 Runner 进程轮询 SQLite 中的任务，并调用 Codex CLI 在已配置项目目录中执行。

v0.1 只覆盖单机 MVP：

- Python + FastAPI 后端
- SQLite + SQLModel 持久化
- 独立 Python Runner 轮询任务
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

## 重跑任务

```bash
curl -X POST http://127.0.0.1:8000/tasks/1/rerun
```

重跑会复制原任务的 `project_id`、`prompt`、`timeout_seconds`，创建一个新的 `PENDING` 任务，并生成新的任务产物路径。

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

启用后，创建项目、创建任务、重跑、取消、Runner 注册和心跳等写接口需要请求头：

```text
X-API-Token: your-token
```

可选限制项目路径白名单：

```bat
set PROJECT_PATH_WHITELIST=E:\JustinQP
```

多个路径在 Windows 下使用分号分隔。项目 API 和页面不会返回本机绝对路径。

Runner 注册和心跳接口：

```text
POST /runners/register
POST /runners/heartbeat
GET  /runners
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

- 暂不支持用户登录、权限、审计。
- 暂不支持取消正在运行的 Codex 子进程，`CANCELLED` 状态为后续能力预留。
- 暂不支持任务重试、并发锁增强、分页和搜索。
- Runner 适合单机单进程使用，本版本只用 lock 文件限制同一 data 目录下的单 Runner。
