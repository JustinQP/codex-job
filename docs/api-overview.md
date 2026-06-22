# API Overview

本文档概览 v1.0.0 当前 API 分组。启用 `API_TOKEN` 后，除 `/health` 和静态页面入口外，业务 API 均需要：

```text
X-API-Token: <token>
```

## 1. Health

```text
GET /health
```

用途：检查主后端是否可访问。

## 2. Projects

```text
GET  /projects
POST /projects
```

用途：管理可执行任务的本机项目配置。

## 3. Tasks

```text
GET  /tasks
POST /tasks
GET  /tasks/{id}
POST /tasks/{id}/cancel
POST /tasks/{id}/rerun
GET  /tasks/{id}/artifacts
GET  /tasks/{id}/log
GET  /tasks/{id}/result
GET  /tasks/{id}/diff
```

用途：查看历史任务和创建 deprecated Runner/codex exec 回退任务。

说明：

- `AGENT_COMMAND_MODE=false` 时，`POST /tasks` 可继续进入旧 Runner 队列。
- `AGENT_COMMAND_MODE=true` 时，新的多设备执行应使用 `POST /runs`。

## 4. Runs

```text
POST /runs
```

用途：在指定 Workspace 上创建 Agent Run。Run 会绑定 Workspace 所属 Device 并生成 AgentCommand，不进入旧 Runner 认领队列。

## 5. Runners

```text
POST /runner/register
POST /runner/heartbeat
POST /runner/tasks/claim
POST /runner/tasks/{task_id}/log
POST /runner/tasks/{task_id}/artifacts
POST /runner/tasks/{task_id}/finish
GET  /runner/tasks/{task_id}/cancel-state
```

状态：deprecated。旧接口保留用于 `AGENT_COMMAND_MODE=false` 回退和历史任务兼容，不用于新的 Workspace Agent Run。

兼容入口：

```text
POST /runners/register
POST /runners/heartbeat
GET  /runners
```

用途：Runner 注册、心跳、认领旧任务和回传结果。

## 6. App Server Bridge

```text
GET /app-server-bridge/health
```

用途：检查 App Server Bridge sidecar 是否可用。该接口通过主后端访问 Bridge，不直接暴露 Bridge Token。

## 7. AppThreads

```text
GET    /app-threads
POST   /app-threads
GET    /app-threads/{id}
PATCH  /app-threads/{id}
DELETE /app-threads/{id}
POST   /app-threads/{id}/reopen
POST   /app-threads/cleanup
```

`GET /app-threads` 支持：

```text
project_id
status=CREATED|ACTIVE|ERROR|CLOSED
include_archived=true|false
limit=1..200
```

`POST /app-threads/cleanup` 只支持清理 `CLOSED` 或 `ERROR`，行为是给 title 增加 `[archived]` 前缀，不物理删除记录。

## 8. AppTurns

```text
POST /app-threads/{id}/turns
POST /app-threads/{id}/turns/async
GET  /app-threads/{id}/turns
GET  /app-threads/{id}/final
GET  /app-threads/{id}/events

GET  /app-turns/{id}
POST /app-turns/{id}/cancel
POST /app-turns/recover-stale
```

`GET /app-threads/{id}/turns` 支持：

```text
status=PENDING|RUNNING|SUCCESS|FAILED|CANCELLED
limit=1..500
```

说明：

- 同步 turn 会阻塞等待 Bridge 返回。
- 异步 turn 会立即返回 `PENDING`，由后端单进程线程池执行。
- `POST /app-turns/{id}/cancel` 是本地状态取消。
- `POST /app-turns/recover-stale` 会把后端重启后残留的 `PENDING` / `RUNNING` AppTurn 标记为 `FAILED`。
