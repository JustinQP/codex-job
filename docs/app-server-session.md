# App Server Session Sidecar

App Server 会话能力是 v1.0.0 中保留的 experimental sidecar POC，用于探索 `codex app-server` 会话模式。

## 架构

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

1. Bridge sidecar 独立运行。
2. 主后端只通过 HTTP 调用 Bridge。
3. 不直接在 `backend/main.py` 中启动 `codex app-server`。
4. 不替代 Runner/codex exec 主链路。
5. Bridge 重启后旧 `bridge_thread_id` 可能失效，可以使用 `POST /app-threads/{id}/reopen`。
6. 后端重启后 `PENDING` / `RUNNING` turn 会被 `recover-stale` 标记为 `FAILED`。

## 启动

窗口 1：启动 Bridge sidecar。

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

- Bridge 是 sidecar 内存态服务，重启后 thread 会丢失。
- 异步 AppTurn 是主后端单进程线程池，不做跨进程恢复。
- 本地取消不保证中断正在执行的 Codex App Server turn。
- 不支持 SSE、审批 UI、diff UI。
