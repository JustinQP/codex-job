# API Overview

本文档概览 v2.0.0 主线 API。除 `/health` 和静态页面入口外，移动端业务 API 需要：

```text
X-API-Token: <token>
```

Agent API 使用：

```text
X-Agent-Token: <agent-token>
```

## Health

```text
GET /health
```

返回 Control Plane 状态，固定主线执行模式：

```json
{
  "status": "ok",
  "execution_mode": "agent_command",
  "session_mode": "agent_managed_app_server"
}
```

## Projects

```text
GET  /projects
POST /projects
```

用途：管理移动端项目上下文。项目可绑定 Workspace；执行目录最终由设备本地 Workspace Registry 决定。

## Devices

```text
GET /devices
GET /devices/{device_id}
```

用途：查看 Device Agent 注册和在线状态。

## Workspaces

```text
GET /workspaces
GET /workspaces/{workspace_id}
```

用途：查看 Agent 从本机 Workspace Registry 同步上来的可执行目录。控制端只展示 `path_label`。

## Runs

```text
GET  /runs
POST /runs
GET  /runs/{run_id}
POST /runs/{run_id}/cancel
POST /runs/{run_id}/rerun
GET  /runs/{run_id}/artifacts
GET  /runs/{run_id}/log
GET  /runs/{run_id}/result
GET  /runs/{run_id}/diff
GET  /runs/{run_id}/artifacts/git-status
GET  /runs/{run_id}/artifacts/report
GET  /run-templates
```

用途：在指定 Workspace 上创建和查看 Agent Run。`POST /runs` 会创建 `RUN_EXECUTE` AgentCommand，绑定 Workspace 所属 Device。

## Agent

```text
POST /agent/register
POST /agent/heartbeat
POST /agent/workspaces/sync
POST /agent/commands/claim
POST /agent/commands/{command_id}/ack
POST /agent/commands/{command_id}/renew
POST /agent/commands/{command_id}/complete
POST /agent/commands/{command_id}/events
POST /agent/reconcile
POST /agent/runs/{run_id}/log-chunks
POST /agent/runs/{run_id}/artifacts
```

用途：Device Agent 注册、心跳、同步 Workspace、认领命令、续租、完成命令、上传事件、日志和产物。

## AppThreads

```text
GET    /app-threads
POST   /app-threads
GET    /app-threads/{id}
PATCH  /app-threads/{id}
DELETE /app-threads/{id}
POST   /app-threads/{id}/reopen
POST   /app-threads/cleanup
```

`POST /app-threads` 创建 `SESSION_OPEN` AgentCommand。完成后返回 `agent_session_id` 和 `codex_thread_id`。

## AppTurns

```text
POST /app-threads/{id}/turns
POST /app-threads/{id}/turns/async
GET  /app-threads/{id}/turns
GET  /app-threads/{id}/final
GET  /app-threads/{id}/events
GET  /app-turns/{id}
GET  /app-turns/{id}/events
GET  /app-turns/{id}/stream
POST /app-turns/{id}/cancel
POST /app-turns/recover-stale
```

Turn 创建统一生成 `TURN_START` AgentCommand。完成后返回 `codex_turn_id`、`assistant_final` 和事件摘要。

## Removed

以下旧路径已删除，不再出现在 OpenAPI：

- `/tasks*`
- `/runner/*`
- `/runners*`
- `/app-server-bridge/health`
