# Codex Job

当前版本：v2.0.0

定位：单用户 Codex Control Plane + Device Agent 本地控制台。

## 1. 项目定位

v2.0 主线只保留一条执行路径：

```text
mobile / API
  -> backend/main.py
  -> AgentCommand 持久化命令队列
  -> agent/main.py on selected device
  -> workspace registry
  -> codex exec / agent-managed codex app-server
```

不再保留 Runner fallback、Task API、App Server Bridge sidecar 和 `AGENT_COMMAND_MODE` 开关。开发期旧数据可丢弃，建议从空 `data/app.db` 启动。

## 2. 核心能力

- Device：Agent 注册、心跳、在线状态和命令轮询。
- Workspace：每台设备只暴露本机显式注册的工作目录。
- Project：绑定移动端选择的业务项目上下文。
- Run：通过 `/runs` 创建一次性 AgentCommand 执行。
- Session：AppThread/AppTurn 通过 Agent-managed app-server 保持连续会话。
- Mobile：底部导航为“会话 / 项目 / 运行 / 我的”。

## 3. 快速开始

### 3.1 安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
cd frontend
npm.cmd install
npm.cmd run build
cd ..
```

### 3.2 启动 Control Plane

```powershell
$env:API_TOKEN="dev-token"
$env:AGENT_TOKEN="agent-dev-token"
$env:PROJECT_PATH_WHITELIST="F:\JustinKing"
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

也可以使用脚本启动后端窗口：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_app_server_stack.ps1 -ApiToken dev-token -AgentToken agent-dev-token -ProjectPathWhitelist F:\JustinKing
```

访问：

```text
http://127.0.0.1:8000/mobile
```

局域网手机访问时，把 `127.0.0.1` 换成后端机器的局域网 IP。

### 3.3 配置 Device Agent

创建 `data\agent\workspaces.json`：

```json
{
  "allowed_roots": ["F:/JustinKing"],
  "workspaces": [
    {
      "key": "codex-job",
      "name": "Codex Job",
      "path": "F:/JustinKing/codex-job",
      "enabled": true
    }
  ]
}
```

启动 Agent：

```powershell
$env:BACKEND_URL="http://127.0.0.1:8000"
$env:AGENT_TOKEN="agent-dev-token"
$env:CODEX_AGENT_DATA_DIR="data\agent"
$env:CODEX_AGENT_WORKSPACES_FILE="data\agent\workspaces.json"
$env:CODEX_AGENT_DISPLAY_NAME="Desk A"
python -m agent.main --register
python -m agent.main --sync-workspaces
python -m agent.main --run-loop
```

`CODEX_AGENT_DATA_DIR` 是 Agent 本地状态根目录：`identity.json`、`state.json`、默认 `workspaces.json`、app-server 会话数据和 Run 本地产物都在此目录下管理。其中一次性 Run 的日志和产物会写入 `CODEX_AGENT_DATA_DIR\runs\{run_id}`，避免从不同 cwd 启动 Agent 时落到相对 `data\agent-runs`。

开发期双 fake Agent 可用：

```powershell
$env:AGENT_TOKEN="agent-dev-token"
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_dual_fake_agents.ps1 -Action Start -Register -SyncWorkspaces
```

## 4. 主要 API

除 `/health`、`/mobile` 和静态资源外，移动端业务 API 需要：

```text
X-API-Token: dev-token
```

Agent API 需要：

```text
X-Agent-Token: agent-dev-token
```

主要分组：

- Health：`GET /health`
- Devices：`GET /devices`、`GET /devices/{id}`
- Workspaces：`GET /workspaces`、`GET /workspaces/{id}`
- Projects：`GET /projects`、`POST /projects`
- Runs：`GET /runs`、`POST /runs`、`GET /runs/{id}`、`POST /runs/{id}/cancel`、`POST /runs/{id}/rerun`
- Agent：`POST /agent/register`、`POST /agent/heartbeat`、`POST /agent/workspaces/sync`、`POST /agent/commands/claim`
- AppThreads：`GET /app-threads`、`POST /app-threads`、`PATCH /app-threads/{id}`、`DELETE /app-threads/{id}`、`POST /app-threads/{id}/reopen`
- AppTurns：`POST /app-threads/{id}/turns/async`、`GET /app-turns/{id}`、`GET /app-turns/{id}/stream`、`POST /app-turns/{id}/cancel`

完整说明见 `docs/api-overview.md`。

## 5. 数据策略

v2.0 不迁移旧 Task/Runner/Bridge 历史数据。

从零开发环境：

```powershell
Remove-Item -Recurse -Force data\*
```

保留 `.gitkeep` 时请手动跳过。启动后端会自动创建新的 `data/app.db`。

检查当前数据状态：

```powershell
python scripts\verify_data_migration.py
```

## 6. 验收命令

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

## 7. 部署安全边界

- 只在本机或可信局域网运行，不按公网服务部署。
- API_TOKEN 和 AGENT_TOKEN 必须配置且不能相同。
- 创建未绑定 Workspace 的本地 Project 时必须配置 PROJECT_PATH_WHITELIST。
- 后端绑定 `0.0.0.0` 时，必须确认网络边界可信，并避免把端口暴露到公网。
- Token 只提供单用户工具级保护，不等同于多用户权限系统或审计系统。

## 8. 当前限制

- 面向本地或可信局域网，不建议公网部署。
- API Token 不是完整多用户权限系统。
- Agent Token 和 API Token 分离，但没有 Token 管理 UI。
- Workspace 必须由设备本地 registry 显式配置。
- 不支持审批 UI。
- 不支持 diff UI。
- F05 真实双设备 smoke 已按用户指令越过，未记录为通过。
