# App Server POC

本目录是独立 POC，用于验证 Python/HTTP Bridge 是否可以通过 stdio JSONL 与 `codex app-server` 通信，并提供最小手机控制页。

v0.8.0 起，主后端可以通过 HTTP 调用本目录的 Bridge sidecar 创建 App Thread 和发送 App Turn。Bridge 仍独立运行，不合并进 `backend/main.py`，不替换主线 `codex exec` Runner。

## 当前推荐运行方式

在项目根目录启动 Bridge：

```powershell
$env:APP_SERVER_BRIDGE_TOKEN="dev-token"
python .\poc\app_server\app_server_bridge.py --host 127.0.0.1 --port 8766
```

本机访问：

```text
http://127.0.0.1:8766/mobile
```

手机局域网访问：

```powershell
$env:APP_SERVER_BRIDGE_TOKEN="dev-token"
python .\poc\app_server\app_server_bridge.py --host 0.0.0.0 --port 8766
```

```text
http://<电脑局域网IP>:8766/mobile
```

局域网访问仅限可信网络，必须设置 `APP_SERVER_BRIDGE_TOKEN`。页面本身不鉴权，但页面调用 Bridge API 时会带 `X-Bridge-Token`。不要公网暴露该 POC 服务。

作为 v0.8.0 主后端 sidecar 使用时，主后端需要配置：

```powershell
$env:APP_SERVER_BRIDGE_URL="http://127.0.0.1:8766"
$env:APP_SERVER_BRIDGE_TOKEN="dev-token"
```

主线手机控制台入口仍是：

```text
http://127.0.0.1:8000/mobile
```

可选配置：

- `--codex-command <path>`：指定 Codex 命令，默认 `codex.cmd`
- `CODEX_COMMAND`：指定 Codex 命令
- `APP_SERVER_BRIDGE_TOKEN`：启用后，除 `/health` 外所有 API 必须传 `X-Bridge-Token`
- `APP_SERVER_BRIDGE_IDLE_TIMEOUT_SECONDS`：thread 空闲超时，默认 `1800`

## Bridge API

Bridge 启动后不会自动创建 app-server 子进程。只有调用 `POST /threads` 时，才会启动一个长期运行的 `codex.cmd app-server --listen stdio://` 子进程并创建 app thread。

接口：

- `GET /health`
- `GET /threads`
- `POST /threads`
- `PATCH /threads/{bridge_thread_id}`
- `POST /threads/{bridge_thread_id}/turns`
- `GET /threads/{bridge_thread_id}`
- `GET /threads/{bridge_thread_id}/events`
- `GET /threads/{bridge_thread_id}/final`
- `DELETE /threads/{bridge_thread_id}`

创建 thread：

```powershell
$headers = @{ "X-Bridge-Token" = "dev-token" }
$body = @{ title = "测试 Thread" } | ConvertTo-Json -Compress
$thread = Invoke-RestMethod `
  -Method Post `
  http://127.0.0.1:8766/threads `
  -Headers $headers `
  -ContentType "application/json; charset=utf-8" `
  -Body $body
```

发送 turn：

```powershell
$body = @{ message = "请只回复 bridge-ok，不要修改文件。" } | ConvertTo-Json -Compress

Invoke-RestMethod `
  -Method Post `
  "http://127.0.0.1:8766/threads/$($thread.bridge_thread_id)/turns" `
  -Headers $headers `
  -ContentType "application/json; charset=utf-8" `
  -Body $body
```

查看最近一轮最终回复：

```powershell
Invoke-RestMethod `
  -Method Get `
  "http://127.0.0.1:8766/threads/$($thread.bridge_thread_id)/final" `
  -Headers $headers
```

重命名 thread：

```powershell
$body = @{ title = "新的标题" } | ConvertTo-Json -Compress
Invoke-RestMethod `
  -Method Patch `
  "http://127.0.0.1:8766/threads/$($thread.bridge_thread_id)" `
  -Headers $headers `
  -ContentType "application/json; charset=utf-8" `
  -Body $body
```

关闭并清理 thread：

```powershell
Invoke-RestMethod `
  -Method Delete `
  "http://127.0.0.1:8766/threads/$($thread.bridge_thread_id)" `
  -Headers $headers
```

## Mobile 页面

入口：

```text
http://127.0.0.1:8766/mobile
```

功能：

- 配置 Bridge Base URL 和 Bridge Token，保存到 `localStorage`
- 查看 health、mode、sandbox、idle timeout
- 创建、选择、重命名、删除 thread
- 发送 message，查看 final 和 events summary
- 使用 prompt 模板
- 复制 final 和 events summary
- 运行连续会话测试

连续会话验收：

1. 创建 thread
2. 发送 `请记住这个词：mobile-session-test。只回复“已记住”。`
3. 发送 `刚才让你记住的词是什么？只回复这个词。`
4. final 包含 `mobile-session-test` 即通过

## POC 历史

- POC-1：`app_server_stdio_client.py` 验证 Python stdio JSONL 基础通信
- POC-2：`app_server_event_parser.py` 与 `app_server_conversation_poc.py` 验证事件解析和最终回复提取
- POC-3：`app_server_thread_reuse_poc.py` 验证同一 thread 连续 turn 上下文复用
- POC-4：`app_server_bridge.py` 提供最小 HTTP Bridge
- POC-4.1/4.2：Bridge 小加固，包含列表、删除、并发保护、空闲超时和更稳的 turn events 截取
- POC-5：`mobile.html` 提供最小手机控制页
- POC-6：手机端可用性增强与会话管理

生成 schema：

```powershell
.\poc\app_server\generate_schema.ps1
```

脚本会创建 `poc/app_server/schema`，并执行：

```powershell
codex.cmd app-server generate-json-schema --out .\poc\app_server\schema
```

## 产物目录

以下目录和文件由 POC 运行生成，并由 `.gitignore` 忽略：

- `poc/app_server/schema/*`
- `poc/app_server/events-*.jsonl`
- `poc/app_server/app-server-stderr-*.log`
- `poc/app_server/runs/`
- `poc/app_server/bridge-runs/`

Bridge 每轮 turn 会保存：

- `turn-<n>/events.jsonl`
- `turn-<n>/run-summary.json`
- `turn-<n>/assistant-final.md`

## 当前限制

- 单进程内存态
- 服务重启后 thread 丢失
- 作为 sidecar 被主后端 HTTP 调用，不合并进 backend
- 不替换 backend/runner/codex exec 主链路
- 主线第一版同步阻塞等待 turn 完成
- 主系统只保存 latest summary/final，不持久化完整事件流
- 不支持 SSE
- 不支持审批 UI
- 不支持 diff UI
- 不做持久化和恢复
- 不要公网暴露

## 风险

- App Server 仍属 experimental POC，协议字段和 method 名称可能变动。
- 当前 POC 只验证 app-server 会话能力，不承担主线任务调度、持久化、权限治理或生产链路职责。
- 当前使用 Python 标准库和原生 HTML/CSS/JS 实现，不引入前端工程化。
