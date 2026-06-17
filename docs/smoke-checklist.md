# Smoke Checklist

本文档用于 v1.0.0 本地验收。

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
