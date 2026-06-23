# Agent-Managed App Server Session

v2.0 连续会话只通过 Device Agent 管理 app-server session。

## 创建会话

`POST /app-threads`：

1. 校验 Project、Workspace、Device。
2. 获取 Workspace lock。
3. 创建 AppThread，状态为 `OPENING`。
4. 创建 `SESSION_OPEN` AgentCommand。
5. Agent 完成后写入 `agent_session_id`、`codex_thread_id`，状态变为 `ACTIVE`。

## 创建 Turn

`POST /app-threads/{id}/turns/async`：

1. 校验 AppThread 为 `ACTIVE`。
2. 创建 AppTurn，状态为 `PENDING`。
3. 创建 `TURN_START` AgentCommand。
4. Agent ack 后 AppTurn 进入 `RUNNING`。
5. Agent complete 后 AppTurn 进入终态，并写入 `codex_turn_id`、`assistant_final`、`event_summary`。

## 恢复

- 后端重启后，`recover-stale` 会把残留的 `PENDING` / `RUNNING` AppTurn 标记为 `FAILED`。
- AppThread 出现不可恢复错误后，使用 `reopen` 重新生成 `SESSION_OPEN` 命令。
