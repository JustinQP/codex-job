# Codex Remote Runner MVP Design

## 1. 目标

v0.1.2 目标是提供一个本机可运行的最小远程任务执行闭环：

1. 通过 HTTP API 配置允许执行的项目目录。
2. 通过 HTTP API 创建 Codex 任务。
3. 独立 Runner 进程轮询数据库中的待执行任务。
4. Runner 在项目目录内调用本机 Codex CLI。
5. 保存日志、最后结果、git 状态和 diff 产物，供 API 查询。

v0.1 不解决多用户、多租户、分布式调度、复杂权限、自动提交和自动发布。

## 2. 架构

```text
Client / curl / API docs
        |
        v
FastAPI backend
        |
        v
SQLite database
        ^
        |
Python Runner process
        |
        v
Codex CLI + local git repository
```

### 后端

- 提供项目和任务 API。
- 使用 SQLModel 操作 SQLite。
- 不执行 Codex，不提供 shell 执行接口。
- 只读取 `data/jobs/<task_id>/` 下的任务产物。
- 任务响应只暴露 `log_url`、`result_url`、`diff_url`，不暴露本机绝对路径。

### Runner

- 独立 Python 进程。
- 轮询 `PENDING` 任务。
- 将任务标记为 `RUNNING` 后执行。
- 校验项目存在、已启用、路径为目录。
- 执行前校验项目必须是 git 仓库。
- 默认要求 git 工作区干净。
- 调用 Codex CLI。
- 将 stdout/stderr 实时写入日志文件。
- 执行完成后写入退出码、结果文件路径和 git 产物路径。
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
created_at
updated_at
```

### Task

```text
id
project_id
prompt
status
timeout_seconds
exit_code
error_message
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

v0.1 的安全边界是单机可信环境下的最小约束：

- 后端不提供任意 shell 命令执行接口。
- 任务只能绑定到已配置项目。
- 项目创建时校验路径必须存在且为目录。
- Runner 执行前再次校验项目路径存在且项目已启用。
- Runner 执行前校验项目必须是 git 仓库。
- 默认拒绝在非干净工作区执行任务。
- Codex 使用 `workspace-write` 沙箱。
- 单任务有超时时间，默认 2 小时。
- 日志、结果和 diff 只保存到 `data/jobs/<task_id>/`。
- API 读取任务产物时校验文件路径必须位于 jobs 目录内。
- Windows 下 Codex 超时时会调用 `taskkill /PID <pid> /T /F` 尽量清理进程树。
- 同一个 data 目录下通过 lock 文件限制单 Runner。

当前未实现：

- 用户身份认证。
- 项目级权限隔离。
- Prompt 内容安全审核。
- 任务取消时对子进程的精细控制。
- 多 Runner 并发执行。

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
GET  /tasks/{task_id}/log
GET  /tasks/{task_id}/result
GET  /tasks/{task_id}/diff
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

1. 增加任务取消接口，并可靠终止正在运行的 Codex 子进程。
2. 增加任务分页、筛选和按项目查询。
3. 增加数据库原子认领和更完整的 Runner 崩溃恢复。
4. 增加 API Token 或本机访问限制。
5. 增加任务重试和失败原因分类。
6. 增加简单 HTML 管理页面。
7. 增加结构化测试覆盖项目创建、任务创建、Runner 失败路径和产物读取。
