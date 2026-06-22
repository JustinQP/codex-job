# App Server Session Sidecar

App Server 会话能力在 v2.0.0 中有两条路径：

1. 正式多设备路径：Control Plane 通过 AgentCommand 把 Session/Turn 命令投递到 Workspace 所属 Device Agent，Agent 侧复用本机 Codex App Server 会话。
2. deprecated sidecar fallback：控制端通过 `poc/app_server/app_server_bridge.py` 调用本机 `codex app-server`，用于本机 smoke 和兼容验证。

## 正式 Agent 架构

```text
mobile / API
  ↓
backend/main.py
  ↓
AppThread / AppTurn service
  ↓
AgentCommand queue in SQLite
  ↓
agent/main.py on selected device
  ↓
agent/app_server/session_manager.py
  ↓
workspace registry cwd
  ↓
codex app-server
```

## Sidecar fallback 架构

```text
mobile / API
  ↓
backend/main.py
  ↓
App Thread / App Turn API
  ↓
app_thread_service.py
  ↓
app_turn_executor.py
  ↓
app_server_bridge_client.py
  ↓ HTTP
poc/app_server/app_server_bridge.py
  ↓ stdio
codex app-server
```

## 边界

1. Device Agent 只解析本机 Workspace Registry 中启用的 workspace key。
2. Control Plane 不通过请求 payload 下发任意 cwd。
3. Agent 模式下同一 AppThread 复用同一 Agent session 和 Codex thread。
4. Bridge sidecar fallback 独立运行，仍不在 `backend/main.py` 中直接启动 `codex app-server`。
5. Bridge 重启后旧 `bridge_thread_id` 可能失效，可以使用 `POST /app-threads/{id}/reopen`。
6. 后端重启后 `PENDING` / `RUNNING` turn 会被 `recover-stale` 标记为 `FAILED`。

## Agent 启动

第二台电脑配置并启动 Agent：

```powershell
$env:BACKEND_URL="http://<control-plane-lan-ip>:8000"
$env:AGENT_TOKEN="agent-dev-token"
$env:CODEX_AGENT_DATA_DIR="data\agent"
$env:CODEX_AGENT_WORKSPACES_FILE="data\agent\workspaces.json"
python -m agent.main --register
python -m agent.main --sync-workspaces
python -m agent.main --run-loop
```

## Sidecar fallback 启动

窗口 1：

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

## 使用

主线入口：

```text
http://127.0.0.1:8000/mobile
```

常见流程：

1. 检查 Bridge health。
2. 创建 AppThread。
3. 同步或异步发送 AppTurn。
4. 轮询异步 AppTurn。
5. 查看 final 和 event summary。
6. Bridge 重启后使用 reopen。
7. 后端重启后使用 recover-stale 清理卡住的 turn。

## 限制

- Agent 模式仍依赖设备在线和本机 Codex 可用。
- Bridge fallback 是 sidecar 内存态服务，重启后 thread 会丢失。
- 本地取消不保证所有 Codex App Server turn 都能协议级中断；必要时 Agent 侧回收进程并要求 reopen。
- 不支持审批 UI、diff UI。
