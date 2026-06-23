# 功能与用法说明

本文档按当前已经实现的 v2.0.0 功能整理使用入口、核心能力和常见操作。架构边界、接口细节和验收命令分别见 `README.md`、`docs/api-overview.md`、`docs/app-server-session.md` 和 `docs/smoke-checklist.md`。

## 1. 产品定位

Codex Job 是一个面向本地或可信局域网的个人 Codex 控制台。当前主线是：

- Control Plane：运行在后端机器上，提供 API、移动端页面、命令队列和任务记录。
- Device Agent：运行在每台执行设备上，注册设备、同步 Workspace、认领命令并调用本机 Codex。
- Mobile Console：通过手机浏览器访问 `/mobile`，选择设备、Workspace、项目、会话和运行记录。
- Deprecated fallback：保留旧 Runner/codex exec 链路和 App Server Bridge sidecar，用于兼容、回退和本机 smoke。

当前不定位为公网多用户系统，不提供完整登录、RBAC、审批 UI 或 diff UI。

## 2. 访问入口

### 2.1 移动端控制台

```text
http://127.0.0.1:8000/mobile
```

手机在局域网访问时，将 `127.0.0.1` 替换为后端机器的局域网 IP：

```text
http://<control-plane-lan-ip>:8000/mobile
```

移动端当前底部导航为：

- 会话：连续 Codex Session 的主入口。
- 项目：选择当前设备、Workspace 和项目，查看当前工作空间状态。
- 运行：查看 Run/Task 执行记录，支持筛选、取消和重跑。
- 我的：保存 API Token，查看诊断状态，执行维护操作。

### 2.2 后端基础入口

```text
GET /
GET /health
```

`/` 是旧 HTML 任务面板，主要用于旧 Runner fallback 的任务查看、创建、取消和重跑。当前主交互建议使用 `/mobile`。

`/health` 返回后端状态和当前执行模式：

- `execution_mode=agent_command`：启用 Device Agent 主线。
- `execution_mode=legacy_runner`：使用旧 Runner fallback。

### 2.3 前端构建

生产模式下，FastAPI 会优先返回 `frontend/dist/index.html`。如果还没有构建，`/mobile` 会返回明确的构建提示。

```powershell
cd frontend
npm install
npm run build
```

前端开发模式可单独启动 Vite：

```powershell
cd frontend
npm install
npm run dev
```

## 3. 认证与运行模式

### 3.1 手机端 API Token

启用 `API_TOKEN` 后，除 `/health` 和静态入口外，移动端业务 API 需要请求头：

```text
X-API-Token: <token>
```

在 `/mobile` 的“我的”页面保存 Token 后，前端会把它存入浏览器 `localStorage`，后续请求自动携带该请求头。

### 3.2 Device Agent Token

Device Agent 使用独立认证头，不使用手机端 Token：

```text
X-Agent-Token: <agent-token>
```

后端通过 `AGENT_TOKEN` 配置 Agent 认证，Agent 侧通过同名环境变量访问控制端。

### 3.3 执行模式

```powershell
$env:AGENT_COMMAND_MODE="true"
```

启用后，新 Run 和主线 Session 通过 AgentCommand 投递到目标设备。关闭或未启用时，旧 `/tasks` + `/runner/*` 链路仍可作为 fallback 使用。

## 4. 启动与部署用法

### 4.1 本机一键启动

本机开发和 App Server Bridge smoke 可以使用：

```powershell
.\scripts\start_app_server_stack.ps1 -ApiToken dev-token -BridgeToken dev-token
```

带 smoke：

```powershell
.\scripts\start_app_server_stack.ps1 -ApiToken dev-token -BridgeToken dev-token -RunSmoke
```

### 4.2 多设备 Control Plane

后端机器启动 Control Plane：

```powershell
$env:API_TOKEN="dev-token"
$env:AGENT_TOKEN="agent-dev-token"
$env:AGENT_COMMAND_MODE="true"
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

启动后，在手机浏览器访问：

```text
http://<control-plane-lan-ip>:8000/mobile
```

### 4.3 Device Agent

在每台执行设备上准备 Python 依赖和本仓库，然后创建 Workspace Registry，例如 `data\agent\workspaces.json`：

```json
{
  "allowed_roots": [
    "F:/JustinKing"
  ],
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

注册、同步 Workspace 并进入轮询：

```powershell
$env:BACKEND_URL="http://<control-plane-lan-ip>:8000"
$env:AGENT_TOKEN="agent-dev-token"
$env:CODEX_AGENT_DATA_DIR="data\agent"
$env:CODEX_AGENT_WORKSPACES_FILE="data\agent\workspaces.json"
$env:CODEX_AGENT_DISPLAY_NAME="Desk B"
python -m agent.main --register
python -m agent.main --sync-workspaces
python -m agent.main --run-loop
```

Agent 会保存稳定设备身份，后续重启继续复用同一个 `device_id`。

### 4.4 Windows Agent 自启动

先检查，再安装计划任务：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install_windows_agent.ps1 -Action Check -BackendUrl http://<control-plane-lan-ip>:8000 -AgentToken agent-dev-token
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install_windows_agent.ps1 -Action Install -BackendUrl http://<control-plane-lan-ip>:8000 -AgentToken agent-dev-token -Force
```

卸载只删除 Windows Task Scheduler 启动项，不删除 Workspace、项目文件或 `data\agent`。

## 5. 移动端功能说明

### 5.1 项目页

项目页用于确定后续会话和运行的工作上下文。

已实现功能：

- 查看已注册设备及其在线状态。
- 按当前设备查看同步上来的 Workspace。
- 选择当前设备、Workspace 和项目。
- 查看当前项目路径标签、默认 Runner、模型、sandbox、更新时间等信息。
- 查看当前工作空间的活跃会话数、运行中数量和失败运行数。
- 查看当前项目最近会话，点击后进入会话页。
- 查看当前项目最近运行记录。

使用建议：

1. 先进入“项目”页。
2. 选择在线设备。
3. 选择该设备上的 Workspace。
4. 选择项目。
5. 再进入“会话”或“运行”页操作。

注意：控制端只展示 `path_label`，不会把 Agent 本机真实路径作为任意 cwd 下发。真正执行路径由设备本地 Workspace Registry 解析。

### 5.2 会话页

会话页是连续 Codex App Server Session 的主入口。

已实现功能：

- 创建 AppThread，并绑定当前项目和 Workspace。
- 从会话列表切换 AppThread。
- 按状态筛选会话。
- 选择是否显示 archived 会话。
- 发送同步或异步 AppTurn。
- 异步 Turn 支持 SSE 增量输出；连接异常时会有限重试，并可回退轮询。
- 查看历史 Turn、展开内容、用历史用户消息重试。
- 取消当前运行中的 Turn。
- 查看当前会话 final。
- 查看当前会话 event summary。
- 关闭 AppThread。
- 重开 AppThread。
- recover stale AppTurn。
- 将 `CLOSED` 或 `ERROR` 会话标记为 archived。

典型用法：

1. 在“项目”页选好设备、Workspace 和项目。
2. 进入“会话”页。
3. 点击切换会话入口，新建或选择会话。
4. 在输入框中输入消息。
5. 使用默认异步模式发送，页面会增量显示输出。
6. 输出异常、Bridge 重启或 Session 需要恢复时，使用“重开”继续。
7. 后端重启后如有卡住的 `PENDING` / `RUNNING` Turn，使用 `recover stale AppTurn`。

发送限制：

- 未选择会话时不能发送。
- 目标设备离线或不可用时不能发送。
- 会话关闭后需要重开才能继续发送。
- 同一会话已有运行中 Turn 时，不能再发送新的 Turn。

### 5.3 运行页

运行页用于查看 Agent Run 和旧 Task 记录。

已实现功能：

- 按当前项目和 Workspace 查看运行记录。
- 切换“当前 Workspace”与“全部设备历史”范围。
- 按状态筛选：`PENDING`、`RUNNING`、`SUCCESS`、`FAILED`、`CANCELLED`。
- 查看运行详情。
- 查看 log、result、diff 访问入口。
- 对运行中记录请求取消。
- 对历史运行发起重跑。
- 有运行中任务时自动轮询刷新。

使用建议：

- 日常检查当前目录执行结果时，使用“当前 Workspace”。
- 排查跨设备历史时，切换为“全部设备历史”。
- 目标设备离线时，重跑按钮会给出不可执行原因。

### 5.4 我的页

“我的”页用于连接配置、诊断和维护。

已实现功能：

- 保存或清空 API Token。
- 查看后端 control mode。
- 查看 `agent_command_mode` 是否启用。
- 查看 App Server Bridge 状态。
- 查看 Bridge mode、sandbox、runner 数量。
- 查看 Runner fallback 诊断信息。
- 刷新诊断。
- recover stale AppTurn。
- 清理 `CLOSED` AppThread。
- 清理 `ERROR` AppThread。
- 查看常用 smoke 启动命令。

使用建议：

- 首次打开 `/mobile` 后，先在“我的”页保存 `API_TOKEN`。
- 会话失败时先刷新诊断，确认后端和 Bridge 状态。
- 后端异常重启后，优先执行 `recover stale AppTurn`。

## 6. 后端 API 功能

完整接口见 `docs/api-overview.md`。当前主要分组如下：

- Health：检查后端状态和执行模式。
- Devices：查看 Device Agent 注册和在线状态。
- Workspaces：查看 Agent 同步的可执行 Workspace。
- Projects：创建和查看项目配置。
- Runs：在指定 Workspace 上创建 Agent Run。
- Tasks：查看历史任务，兼容旧 Runner/codex exec fallback。
- Agent：Agent 注册、心跳、Workspace 同步、命令认领、续租、完成、事件和产物上传。
- Runners：deprecated，旧 Runner 注册、心跳、认领和上传结果。
- App Server Bridge：检查 sidecar 是否可用。
- AppThreads：创建、查看、重命名、关闭、重开、筛选和 archived 清理会话。
- AppTurns：同步/异步发送、查看状态、SSE stream、事件列表、取消和 stale 恢复。

常用 API 示例：

```powershell
$headers = @{ "X-API-Token" = "dev-token" }
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/devices -Headers $headers
Invoke-RestMethod http://127.0.0.1:8000/workspaces -Headers $headers
Invoke-RestMethod http://127.0.0.1:8000/app-server-bridge/health -Headers $headers
```

## 7. Deprecated fallback 功能

### 7.1 旧 Runner/codex exec

旧 Runner 链路用于一次性 `codex exec` 任务，当前仅作为 fallback 保留。

可用能力：

- 创建 Task。
- Runner 注册和心跳。
- Runner 认领任务。
- 上传 log、result、diff、git status 和 report。
- 请求取消 Task。
- 重跑 Task。
- 在旧 HTML 面板查看任务。

启动方式：

```powershell
scripts\start.bat api
scripts\start.bat runner
scripts\start.bat runner-once
```

适用场景：

- `AGENT_COMMAND_MODE=false` 的旧模式。
- 多设备 Agent 主线不可用时的本机回退。
- 查看和兼容历史 Task 记录。

### 7.2 App Server Bridge sidecar

App Server Bridge sidecar 用于本机 `codex app-server` smoke 和兼容验证。

窗口 1：

```powershell
$env:APP_SERVER_BRIDGE_TOKEN="dev-token"
python .\poc\app_server\app_server_bridge.py --host 127.0.0.1 --port 8766
```

窗口 2：

```powershell
$env:API_TOKEN="dev-token"
$env:APP_SERVER_BRIDGE_URL="http://127.0.0.1:8766"
$env:APP_SERVER_BRIDGE_TOKEN="dev-token"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

注意：

- Bridge 是独立 sidecar，不由 `backend/main.py` 内部启动。
- Bridge 重启后旧内存态 thread 可能失效，需要 reopen AppThread。
- 当前不建议公网暴露。

## 8. 数据、产物与安全边界

当前实现遵循以下边界：

- 控制端不接受任意 cwd；执行目录来自设备本地 Workspace Registry。
- 后端 API 不直接暴露本机绝对路径，只返回 `path_label` 或 artifact 访问入口。
- Run/Task 产物存放在后端 `data/jobs/<task_id>/` 下。
- Artifact 读取会校验路径仍在 jobs 目录内。
- Run artifact 上传有单文件和总量限制，可通过 `RUN_ARTIFACT_MAX_FILE_BYTES`、`RUN_ARTIFACT_MAX_TOTAL_BYTES` 配置。
- 手机端 `API_TOKEN` 与 Agent 侧 `AGENT_TOKEN` 分离。
- 当前 API Token 不是完整多用户权限系统，不建议公网部署。

## 9. 常见操作流程

### 9.1 在手机上创建连续会话

1. 启动 Control Plane，确认手机能打开 `/mobile`。
2. 在“我的”页保存 API Token。
3. 启动目标设备 Device Agent，完成 register、sync-workspaces 和 run-loop。
4. 在“项目”页选择设备、Workspace 和项目。
5. 进入“会话”页，新建 AppThread。
6. 发送消息并观察增量输出。
7. 需要恢复时使用 reopen 或 recover stale。

### 9.2 查看一次运行结果

1. 进入“运行”页。
2. 选择“当前 Workspace”或“全部设备历史”。
3. 使用状态筛选定位记录。
4. 打开运行详情。
5. 查看 log、result 或 diff 入口。
6. 如仍在运行，可请求取消；如已结束，可发起重跑。

### 9.3 处理 Bridge 或会话异常

1. 在“我的”页刷新诊断。
2. 如果 Bridge 不可用，检查 sidecar 是否启动、`APP_SERVER_BRIDGE_URL` 和 `APP_SERVER_BRIDGE_TOKEN` 是否正确。
3. 如果会话提示 thread missing 或 recover required，回到会话页执行 reopen。
4. 如果后端重启后存在卡住 Turn，执行 recover stale。

### 9.4 验收当前功能

基础检查：

```powershell
python -m compileall backend runner scripts poc/app_server
pytest -q
```

前端检查：

```powershell
cd frontend
npm run typecheck
npm run build
```

App Server smoke 见 `docs/smoke-checklist.md`。

## 10. 当前限制

- 当前主要面向本地或可信局域网。
- 不建议公网部署。
- 不支持完整用户登录、组织、RBAC 或 Token 管理 UI。
- 不支持审批 UI。
- 不支持 diff UI。
- 真实双设备 smoke 当前记录为未执行，后续补验时应按 `docs/smoke-checklist.md` 执行。
- 旧 Runner/codex exec 与 App Server Bridge sidecar 都是兼容和 fallback 能力，新使用场景优先走 Device Agent 主线。
