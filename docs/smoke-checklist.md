# Smoke Checklist

本文档用于 v2.0.0 本地验收。

## 自动化验证

```powershell
python -m compileall backend agent scripts
pytest -q tests --basetemp .pytest-tmp-v2-mainline
python scripts\smoke_local_e2e.py
cd frontend
npm.cmd run typecheck
npm.cmd run build
cd ..
git diff --check
```

`python scripts\smoke_local_e2e.py` 使用内存数据库、TestClient、fake Device Agent 和 fake app-server 执行本机端到端验收，覆盖 Control Plane、Device Agent、Workspace/Project 创建、read-only Run、Session Turn、取消和关闭流程。它不替代真实设备 smoke，但可以作为每次回归的低成本主线检查。

真实双设备验收使用 [Real Dual Device Smoke](real-dual-device-smoke.md) 记录。该检查需要 two real devices，不属于本机自动化 smoke，未拿到真实设备证据时不能记录为通过。

## 空数据启动

1. 清理 `data`。
2. 启动 Control Plane。
3. 启动 Device Agent 或 dual fake agents。
4. 打开 `/mobile`。
5. 在项目页确认 Device、Workspace、Project 可见。

## Run Smoke

预期：

- `POST /runs` 创建 Run。
- Run 绑定 Workspace 所属 Device。
- 创建 `RUN_EXECUTE` AgentCommand。
- Agent 完成后 Run 状态变为 `SUCCESS` 或 `FAILED`。
- `/runs/{id}/cancel` 可取消未完成 Run 并释放 Workspace lock。
- `/runs/{id}/rerun` 创建新的 Run 和 AgentCommand。

## Session Smoke

预期：

- `POST /app-threads` 创建 `SESSION_OPEN` AgentCommand。
- Agent 完成后 AppThread 进入 `ACTIVE`。
- 返回 `agent_session_id` 和 `codex_thread_id`。
- `POST /app-threads/{id}/turns/async` 创建 `TURN_START` AgentCommand。
- 连续 Turn 复用同一个 Agent app-server session。
- Turn 完成后返回 `codex_turn_id` 和 `assistant_final`。

## Removed Route Check

OpenAPI 中不应出现：

- `/tasks`
- `/runner/*`
- `/runners`
- `/app-server-bridge/health`

## 未验证项

- F05 真实双设备 smoke 需要 two real devices，当前本机自动化未覆盖；按 `real-dual-device-smoke.md` 补充证据前，不记录为通过。
