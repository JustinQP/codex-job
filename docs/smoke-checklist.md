# Smoke Checklist

本文档用于 v1.0.0 本地验收。

## 0. 重构前自动化回归基线

A01 冻结以下单机控制台核心行为，后续多设备重构不得破坏：

- Project 创建和列表：`tests/test_tasks_api.py` 覆盖 `/projects` 创建、列表、`path_label` 和项目执行默认配置。
- Task 创建、认领、完成、取消和重跑：`tests/test_tasks_api.py`、`tests/test_runner_service.py` 覆盖创建配置继承、Runner 认领、日志/产物上传、完成、pending/running 取消和 rerun。
- Runner 注册、心跳和 lease：`tests/test_runner_service.py` 覆盖注册 lease、过期 Runner 下线、运行中 Task lease 恢复。
- AppThread cwd 和 reopen：`tests/test_app_thread_service.py`、`tests/test_app_threads_api.py` 覆盖创建和 reopen 时都把 Project 路径传给 Bridge cwd。
- AppTurn 同步、异步、冲突、失败和取消：`tests/test_app_thread_service.py`、`tests/test_app_threads_api.py`、`tests/test_app_turn_executor.py` 覆盖同步发送、异步 pending、并发冲突、Bridge 失败、stale 恢复和取消。
- `/app-turns/{id}/stream`：`tests/test_app_threads_api.py` 覆盖 terminal `status`、`final` 和 `error`；`tests/test_app_thread_service.py` 覆盖 active Bridge turn 的 `assistant_delta` 过滤。

基线验证命令：

```powershell
python -m compileall backend runner scripts poc/app_server
pytest -q
cd frontend
npm run typecheck
npm run build
```

## 1. compileall

```powershell
python -m compileall backend runner scripts poc/app_server
```

预期：无语法错误。

## 2. pytest

```powershell
pytest -q
```

预期：全部测试通过。

## 3. backend health

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

预期：返回 `status=ok`。

## 4. bridge health

```powershell
$headers = @{ "X-API-Token" = "dev-token" }
Invoke-RestMethod http://127.0.0.1:8000/app-server-bridge/health -Headers $headers
```

预期：主后端能通过 HTTP 调用 Bridge sidecar。

## 5. App Server 同步 smoke

```powershell
$env:API_TOKEN="dev-token"
python .\scripts\smoke_app_server_flow.py --base-url http://127.0.0.1:8000 --project-path F:\JustinKing\codex-job
```

预期：`pass=true`，并尽量自动关闭创建的 AppThread。

## 6. App Server 异步 smoke

```powershell
$env:API_TOKEN="dev-token"
python .\scripts\smoke_app_server_flow.py --base-url http://127.0.0.1:8000 --project-path F:\JustinKing\codex-job --async-turn
```

预期：异步 AppTurn 轮询到 `SUCCESS`。

## 7. 并发保护 smoke

```powershell
$env:API_TOKEN="dev-token"
python .\scripts\smoke_app_server_flow.py --base-url http://127.0.0.1:8000 --project-path F:\JustinKing\codex-job --async-turn --check-async-conflict
```

预期：第二个并发异步 turn 返回 409，`async_conflict_passed=true`。

## 8. recover-stale smoke

```powershell
$env:API_TOKEN="dev-token"
python .\scripts\smoke_app_server_flow.py --base-url http://127.0.0.1:8000 --recover-stale
```

预期：返回 `recover_stale_called=true`，即使没有 stale turn 也应通过。

## 9. mobile 手工验收

打开：

```text
http://127.0.0.1:8000/mobile
```

检查：

- 保存 API Token。
- 检查 Bridge。
- 创建 AppThread。
- 同步发送 AppTurn。
- 异步发送 AppTurn。
- 刷新当前 Turn。
- 取消当前 Turn。
- 查看 final。
- 查看 events。
- reopen AppThread。
- recover stale AppTurn。
- 状态筛选。
- 清理 CLOSED/ERROR。
