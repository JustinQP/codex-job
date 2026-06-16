# Codex Remote Runner MVP Design

## 1. 目标

v0.5.0 目标是提供一个真正通过 HTTP 通信的最小远程 Runner 闭环：

1. 通过 HTTP API 配置允许执行的项目目录。
2. 通过 HTTP API 创建 Codex 任务。
3. 独立 Runner 进程通过 HTTP 认领待执行任务。
4. Runner 在项目目录内调用本机 Codex CLI。
5. 保存日志、最后结果、git 状态和 diff 产物，供 API 查询。

v0.5.0 不解决多用户、多租户、分布式调度、复杂权限、自动提交和自动发布。

v0.5.0 起，Runner 不再直接访问后端 SQLite，也不共享后端 `data/jobs` 目录。后端保存任务状态和上传后的产物，Runner 只通过 `/runner/...` HTTP API 注册、心跳、认领任务和回传结果。

## 2. 架构

```text
Client / curl / API docs
        |
        v
FastAPI backend
        |
        +--> SQLite database
        |
        +--> data/jobs/<task_id>/

Python Runner process
        |
        | HTTP /runner/...
        v
FastAPI backend
        |
        | claim / upload artifacts
        |
Python Runner process
        |
        v
Codex CLI + local git repository
```

### 后端

- 提供项目和任务 API。
- 提供一个简单 HTML 管理页面。
- 提供 Runner 专用 HTTP API。
- 使用 SQLModel 操作 SQLite。
- 不执行 Codex，不提供 shell 执行接口。
- 保存 Runner 上传到 `data/jobs/<task_id>/` 的任务产物。
- 任务响应只暴露 `log_url`、`result_url`、`diff_url`，不暴露本机绝对路径。

### HTML 管理页面

v0.2.0 增加服务端渲染的简单 HTML 页面，不引入 Vue 或前端构建工具。

页面范围：

- `/`：项目列表、创建任务、任务列表、任务筛选。
- `/ui/tasks/{task_id}`：任务详情、产物链接、重跑入口。
- `/ui/tasks`：表单创建任务。
- `/ui/tasks/{task_id}/rerun`：表单重跑任务。

页面仍复用现有 service，不引入新的任务执行路径。

### 任务取消与运行控制

v0.2.1 增加任务取消：

- `POST /tasks/{task_id}/cancel`
- `PENDING` 任务直接变为 `CANCELLED`。
- `RUNNING` 任务设置 `cancel_requested=true`。
- Runner 执行 Codex 时定期检查取消标记。
- Windows 下使用 `taskkill /PID <pid> /T /F` 尽量终止进程树。
- 非 Windows 使用 terminate/kill。

### 工程化工作流

v0.3.0 增加：

- 任务类型：`PLAN`、`IMPLEMENT`、`REVIEW`、`TEST_FIX`、`DOCS`、`COMMIT`。
- `GET /task-templates` 返回内置 prompt 模板。
- 项目配置字段：`test_command`、`smoke_check_command`、`default_branch`、`require_clean_worktree`。
- 执行产物增加 `test-output.txt` 和 `task-report.md`。

v0.3.0 不自动执行 `test_command` 和 `smoke_check_command`，只写入报告，避免把远程 API 变成任意 shell 执行入口。

### 远程 Runner 前置安全边界

v0.4.1 增加远程使用前置安全边界：

- 可选 `API_TOKEN`，启用后除 `/health` 外，所有 API 读写接口都需要 `X-API-Token`。
- HTML GET 页面和 UI 写接口同样校验 `API_TOKEN`，当前不提供登录或 token 输入框。
- 可选 `PROJECT_PATH_WHITELIST`，限制新增项目路径，并在 Runner 执行前再次复验。
- 项目 API 和 HTML 页面不返回本机绝对路径。
- Runner 注册和心跳：
  - `POST /runners/register`
  - `POST /runners/heartbeat`
  - `GET /runners`

这仍不是多 Runner 调度系统，也不建议直接暴露到公网。

### 真正远程 Runner

v0.5.0 将 Runner 改为 HTTP client：

- Runner 使用 `BACKEND_URL` 连接后端。
- Runner 使用 `RUNNER_ID` 标识自己。
- Runner 使用 `RUNNER_TOKEN` 或 `API_TOKEN` 作为 `X-API-Token`。
- Runner 通过 `POST /runner/tasks/claim` 原子认领任务，不再直接 select SQLite。
- Runner 在本地项目目录执行 Codex。
- Runner 本地产物默认写入 `data/runner-jobs/<runner_id>/<task_id>/`。
- Runner 执行中定期通过 HTTP 上传日志。
- Runner 执行完成后通过 HTTP 上传日志、结果和 git 产物。
- v0.5.2 起，Runner 对临时网络错误和 HTTP 5xx 做短重试；最终产物上传失败时，本地任务目录保留 `upload-pending.json`。

### Runner

- 独立 Python 进程。
- 通过 HTTP 轮询后端任务。
- 由后端原子认领 `PENDING` 任务并标记为 `RUNNING`。
- 校验项目路径存在、路径为目录。
- 执行前校验项目必须是 git 仓库。
- 默认要求 git 工作区干净。
- 调用 Codex CLI。
- 将 stdout/stderr 实时写入 Runner 本地日志文件。
- 执行中按固定间隔上传最新日志，便于后端页面查看运行进度。
- 执行完成后通过 HTTP 上传日志、结果、diff 和 git 产物。
- 同一个 data 目录下通过 `runner.lock` 限制只运行一个 Runner。
- Runner 启动时读取 lock 中的 pid，自动清理 stale lock，拒绝与存活 Runner 并行启动。

### 数据库

默认使用：

```text
data/app.db
```

主要表：

- `projects`：项目配置。
- `tasks`：任务状态和产物路径。

## 3. 数据模型

### Project

```text
id
name
path
enabled
test_command
smoke_check_command
default_branch
require_clean_worktree
created_at
updated_at
```

### Task

```text
id
project_id
prompt
task_type
status
timeout_seconds
exit_code
error_message
cancel_requested
runner_id
runner_pid
log_file
result_file
diff_file
created_at
updated_at
started_at
finished_at
```

API 响应中的 `TaskRead` 不直接返回 `log_file`、`result_file`、`diff_file`，改为返回：

```text
log_url
result_url
diff_url
```

## 4. 状态流转

```text
PENDING -> RUNNING -> SUCCESS
PENDING -> RUNNING -> FAILED
PENDING -> CANCELLED
```

v0.1 中：

- 创建任务后状态为 `PENDING`。
- Runner 认领任务后状态为 `RUNNING`。
- Codex 退出码为 0 且 git 产物保存成功，状态为 `SUCCESS`。
- Codex 启动失败、超时、退出码非 0、项目校验失败、git 仓库校验失败、工作区非干净或 git 产物保存失败，状态为 `FAILED`。
- `CANCELLED` 是保留状态，后续实现取消任务时使用。

## 5. Codex 调用

Runner 使用以下命令执行任务：

```bash
codex exec --cd <project_path> --sandbox workspace-write --output-last-message <result_file> <prompt>
```

Codex CLI 查找顺序：

1. 环境变量 `CODEX_BIN`
2. `codex.cmd`
3. `codex`
4. `codex.exe`

执行产物：

```text
data/jobs/<task_id>/run.log
data/jobs/<task_id>/result.md
data/jobs/<task_id>/diff.patch
data/jobs/<task_id>/git-status.txt
data/jobs/<task_id>/diff-unstaged.patch
data/jobs/<task_id>/diff-staged.patch
data/jobs/<task_id>/untracked-files.txt
data/jobs/<task_id>/test-output.txt
data/jobs/<task_id>/task-report.md
```

`diff.patch` 是为了兼容 `/tasks/{task_id}/diff` 的组合文本，包含 git 状态、未暂存 diff、已暂存 diff 和未跟踪文件列表。

## 6. Git 工作区策略

Runner 执行任务前会执行 git preflight：

1. 项目必须是 git 仓库。
2. 默认要求 `git status --porcelain` 为空。
3. 如不满足要求，任务直接 `FAILED`，不会启动 Codex。

环境变量：

```text
REQUIRE_CLEAN_WORKTREE=true
```

默认值为 `true`。设置为 `false` 时允许非干净工作区执行，但仍要求项目是 git 仓库。

## 7. 安全边界

v0.5.0 的安全边界是局域网/可信 Runner 环境下的最小约束：

- 后端不提供任意 shell 命令执行接口。
- 启用 `API_TOKEN` 后，除 `/health` 外所有 API 读写接口需要 token。
- 启用 `API_TOKEN` 后，HTML GET 页面和 UI 写接口也需要 token；当前 HTML 页面不提供登录或 token 输入框，建议使用 API 调用。
- 启用 `PROJECT_PATH_WHITELIST` 后，只允许配置白名单内项目路径。
- Runner 执行任务前再次复验 `PROJECT_PATH_WHITELIST`。
- API 和 HTML 页面不返回本机绝对路径。
- 任务只能绑定到已配置项目。
- 项目创建时校验路径必须存在且为目录。
- Runner 执行前再次校验项目路径存在且项目已启用。
- Runner 执行前校验项目必须是 git 仓库。
- 默认拒绝在非干净工作区执行任务。
- Codex 使用 `workspace-write` 沙箱。
- 单任务有超时时间，默认 2 小时。
- Runner 本地生成日志、结果和 diff，完成后通过 HTTP 上传。
- 后端保存上传后的日志、结果和 diff 到 `data/jobs/<task_id>/`。
- 任务详情页对 `PENDING` 和 `RUNNING` 任务自动刷新状态。
- API 读取任务产物时校验文件路径必须位于 jobs 目录内。
- Windows 下 Codex 超时时会调用 `taskkill /PID <pid> /T /F` 尽量清理进程树。
- 同一个 data 目录下通过 lock 文件限制单 Runner。

当前未实现：

- 多用户账号体系。
- 项目级细粒度权限隔离。
- Prompt 内容安全审核。
- 多 Runner 并发执行。
- Runner 端产物上传大小限制。
- `upload-pending.json` 自动补传队列。

## 8. API

最小 API：

```text
GET  /health
POST /projects
GET  /projects
POST /tasks
GET  /tasks
GET  /tasks/{task_id}
POST /tasks/{task_id}/rerun
POST /tasks/{task_id}/cancel
GET  /tasks/{task_id}/artifacts
GET  /tasks/{task_id}/log
GET  /tasks/{task_id}/result
GET  /tasks/{task_id}/diff
GET  /task-templates
POST /runners/register
POST /runners/heartbeat
GET  /runners
POST /runner/register
POST /runner/heartbeat
POST /runner/tasks/claim
POST /runner/tasks/{task_id}/log
POST /runner/tasks/{task_id}/artifacts
POST /runner/tasks/{task_id}/finish
GET  /runner/tasks/{task_id}/cancel-state
```

API 详细字段以 FastAPI `/docs` 为准。

`GET /tasks` 支持查询参数：

```text
project_id
status
limit
```

`limit` 默认 50，最大 200。

任务创建和重跑的 `timeout_seconds` 限制：

```text
default = 7200
min = 30
max = 21600
```

`POST /tasks/{task_id}/rerun` 会复制原任务的 `project_id`、`prompt`、`timeout_seconds`，创建新的 `PENDING` 任务，不复用旧任务产物路径。

## 9. 验收方式

基础自动检查：

```bash
python -m compileall backend runner scripts
pytest -q
python -c "from backend.db import init_db; init_db(); print('db ok')"
```

手工闭环：

1. 启动后端。
2. 创建项目。
3. 创建任务。
4. 启动 Runner。
5. 查看任务状态从 `PENDING` 到 `RUNNING` 再到终态。
6. 查看日志、结果、diff 和 git 产物。

## 10. 后续迭代计划

优先级建议：

1. 增加更完整的 Runner 崩溃恢复和 RUNNING 超时回收。
2. 增加任务自动重试和失败原因分类。
3. 增加 UI token 输入或本地 session。
4. 增加 Runner 上传大小限制和更细的 artifact 校验。
5. 增加结构化测试覆盖更多 Runner 失败路径和产物读取边界。
