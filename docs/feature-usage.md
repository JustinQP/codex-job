# 功能与用法说明

## 定位

Codex Job v2.0 是本地/可信局域网内使用的单用户控制台。主线由 Control Plane、Device Agent、AgentCommand、Run 和连续 Session 组成。

## 移动端

入口：

```text
http://127.0.0.1:8000/mobile
```

底部导航：

- 会话：创建和继续连续 Codex Session。
- 项目：选择设备、Workspace 和项目。
- 运行：查看 Run，取消运行，重跑历史运行。
- 我的：保存 API Token，查看主线运行诊断，执行维护操作。

## 启动

Control Plane：

```powershell
$env:API_TOKEN="dev-token"
$env:AGENT_TOKEN="agent-dev-token"
$env:PROJECT_PATH_WHITELIST="F:\JustinKing"
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Device Agent：

```powershell
$env:BACKEND_URL="http://127.0.0.1:8000"
$env:AGENT_TOKEN="agent-dev-token"
$env:CODEX_AGENT_DATA_DIR="data\agent"
$env:CODEX_AGENT_WORKSPACES_FILE="data\agent\workspaces.json"
python -m agent.main --register
python -m agent.main --sync-workspaces
python -m agent.main --run-loop
```

## Run

Run 是一次性执行记录。创建 Run 时必须指定 `workspace_id`，控制端会：

1. 找到 Workspace 所属 Device。
2. 获取 Workspace execution lock。
3. 创建 `RUN_EXECUTE` AgentCommand。
4. 由 Device Agent 执行并上传日志/产物。
5. AgentCommand 完成后回写 Run 状态并释放锁。

产物入口统一为：

```text
/runs/{run_id}/log
/runs/{run_id}/result
/runs/{run_id}/diff
/runs/{run_id}/artifacts/git-status
/runs/{run_id}/artifacts/report
```

## Session

AppThread 创建时生成 `SESSION_OPEN` AgentCommand。Agent 在目标 Workspace 上打开 app-server session，成功后回写：

- `agent_session_id`
- `codex_thread_id`

AppTurn 创建时生成 `TURN_START` AgentCommand。Agent 在同一 session 中继续发送消息，成功后回写：

- `assistant_final`
- `codex_turn_id`
- `event_summary`

## 数据策略

v2.0 开发期不迁移旧历史数据。需要从零开始时清理 `data` 后重启后端即可。

```powershell
python scripts\verify_data_migration.py
```

该脚本只检查当前数据库是否符合 v2.0 reset 策略，不做旧数据迁移。
