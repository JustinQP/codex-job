# Codex App Server stdio POC

本目录是独立 POC，只验证 Python 是否可以通过 stdio JSONL 与 `codex app-server` 通信。

当前不接入 `backend/main.py`、`runner/runner.py`、数据库模型或现有任务系统。

## 生成 schema

在项目根目录执行：

```powershell
.\poc\app_server\generate_schema.ps1
```

脚本会创建 `poc/app_server/schema`，并执行：

```powershell
codex.cmd app-server generate-json-schema --out .\poc\app_server\schema
```

`schema` 目录下生成内容会被 `.gitignore` 忽略，仅保留 `schema/.gitkeep`。

## POC-1：stdio JSONL 基础通信

在项目根目录执行：

```powershell
python .\poc\app_server\app_server_stdio_client.py
```

如 `codex.cmd` 不在当前 PATH，可显式指定：

```powershell
python .\poc\app_server\app_server_stdio_client.py --codex-command C:\path\to\codex.cmd
```

产物：

- `poc/app_server/events-<timestamp>.jsonl`
- `poc/app_server/app-server-stderr-<timestamp>.log`

## POC-2：事件解析与最终回复提取

在项目根目录执行：

```powershell
python .\poc\app_server\app_server_conversation_poc.py --message "请只回复 app-server-parser-ok，不要修改文件。"
```

每次运行会创建：

```text
poc/app_server/runs/<timestamp>/
```

并保存：

- `events.jsonl`：app-server stdout 中收到的 JSON 行
- `stderr.log`：app-server stderr
- `run-summary.json`：事件数量、类型统计、ID、错误和未知事件摘要
- `assistant-final.md`：解析出的最终助手回复

`runs` 目录会被 `.gitignore` 忽略。

## POC-3：连续会话 thread 复用验证

在项目根目录执行：

```powershell
python .\poc\app_server\app_server_thread_reuse_poc.py
```

该脚本会在同一个 `codex.cmd app-server --listen stdio://` 进程里只创建一个 thread，然后连续发送两轮 turn：

1. `请记住这个词：justin-plus-session-test。只回复“已记住”。`
2. `刚才让你记住的词是什么？只回复这个词。`

产物目录：

```text
poc/app_server/runs/thread-reuse-<timestamp>/
```

产物：

- `thread-state.json`：thread、turn、初始化和启动信息
- `stderr.log`：本次 app-server 进程的共用 stderr
- `turn-1/events.jsonl`
- `turn-1/run-summary.json`
- `turn-1/assistant-final.md`
- `turn-2/events.jsonl`
- `turn-2/run-summary.json`
- `turn-2/assistant-final.md`
- `result.json`：包含 `thread_id`、两轮最终回复、`context_retained`、期望 token 和错误列表

## POC-4：最小 HTTP Bridge

在项目根目录启动：

```powershell
python .\poc\app_server\app_server_bridge.py --host 127.0.0.1 --port 8766
```

默认不会在服务启动时创建 app-server 子进程。只有调用 `POST /threads` 时，才会启动一个 `codex.cmd app-server --listen stdio://` 子进程并创建一个 app thread。

可选配置：

- `--codex-command <path>`：指定 Codex 命令，默认 `codex.cmd`
- 环境变量 `CODEX_COMMAND`：指定 Codex 命令
- 环境变量 `APP_SERVER_BRIDGE_TOKEN`：启用后，除 `/health` 外所有接口必须传 `X-Bridge-Token`
- 环境变量 `APP_SERVER_BRIDGE_IDLE_TIMEOUT_SECONDS`：thread 空闲超时，默认 `1800`

接口：

- `GET /health`
- `GET /threads`
- `POST /threads`
- `POST /threads/{bridge_thread_id}/turns`
- `GET /threads/{bridge_thread_id}`
- `GET /threads/{bridge_thread_id}/events`
- `GET /threads/{bridge_thread_id}/final`
- `DELETE /threads/{bridge_thread_id}`

创建 thread：

```powershell
$thread = Invoke-RestMethod -Method Post http://127.0.0.1:8766/threads
$thread
```

列出当前内存中的 thread：

```powershell
Invoke-RestMethod -Method Get http://127.0.0.1:8766/threads
```

发送 turn：

```powershell
$body = @{ message = "请只回复 bridge-ok，不要修改文件。" } | ConvertTo-Json -Compress

Invoke-RestMethod `
  -Method Post `
  "http://127.0.0.1:8766/threads/$($thread.bridge_thread_id)/turns" `
  -ContentType "application/json; charset=utf-8" `
  -Body $body
```

查看最近一轮最终回复：

```powershell
Invoke-RestMethod -Method Get "http://127.0.0.1:8766/threads/$($thread.bridge_thread_id)/final"
```

关闭并清理 thread：

```powershell
Invoke-RestMethod -Method Delete "http://127.0.0.1:8766/threads/$($thread.bridge_thread_id)"
```

Token 验证：

```powershell
$env:APP_SERVER_BRIDGE_TOKEN = "dev-token"
python .\poc\app_server\app_server_bridge.py --host 127.0.0.1 --port 8766

$headers = @{ "X-Bridge-Token" = "dev-token" }
$thread = Invoke-RestMethod -Method Post http://127.0.0.1:8766/threads -Headers $headers
Invoke-RestMethod -Method Get "http://127.0.0.1:8766/threads/$($thread.bridge_thread_id)" -Headers $headers
```

连续会话验证示例：

```powershell
$thread = Invoke-RestMethod -Method Post http://127.0.0.1:8766/threads

$body1 = @{ message = "请记住这个词：bridge-session-test。只回复“已记住”。" } | ConvertTo-Json -Compress
Invoke-RestMethod `
  -Method Post `
  "http://127.0.0.1:8766/threads/$($thread.bridge_thread_id)/turns" `
  -ContentType "application/json; charset=utf-8" `
  -Body $body1

$body2 = @{ message = "刚才让你记住的词是什么？只回复这个词。" } | ConvertTo-Json -Compress
Invoke-RestMethod `
  -Method Post `
  "http://127.0.0.1:8766/threads/$($thread.bridge_thread_id)/turns" `
  -ContentType "application/json; charset=utf-8" `
  -Body $body2

Invoke-RestMethod -Method Get "http://127.0.0.1:8766/threads/$($thread.bridge_thread_id)/final"
```

验收标准：第二轮 final 包含 `bridge-session-test`。

产物目录：

```text
poc/app_server/bridge-runs/<bridge_thread_id>/
```

每轮 turn 会保存：

- `turn-<n>/events.jsonl`
- `turn-<n>/run-summary.json`
- `turn-<n>/assistant-final.md`

当前限制：

- 只做 POC，不接入主系统
- 单进程内存态，服务重启后 thread 丢失
- 不支持 SSE
- 不支持审批 UI
- 不支持 diff UI
- 不做持久化和恢复

## POC-5：最小手机控制页

启动 Bridge：

```powershell
$env:APP_SERVER_BRIDGE_TOKEN = "dev-token"
python .\poc\app_server\app_server_bridge.py --host 127.0.0.1 --port 8766
```

本机访问：

```text
http://127.0.0.1:8766/mobile
```

页面功能：

- 配置 Bridge Base URL，默认当前 origin
- 配置 Bridge Token，并保存到 `localStorage`
- 检查健康状态
- 创建 Thread
- 刷新 Thread 列表
- 删除当前 Thread
- 发送 message
- 获取当前 Thread final
- 获取当前 Thread events summary
- 运行连续会话测试

手机局域网访问：

如需手机访问，可将启动 host 改为 `0.0.0.0`，并使用电脑局域网 IP 访问：

```powershell
$env:APP_SERVER_BRIDGE_TOKEN = "dev-token"
python .\poc\app_server\app_server_bridge.py --host 0.0.0.0 --port 8766
```

```text
http://<电脑局域网IP>:8766/mobile
```

该方式仅限可信局域网，并必须设置 `APP_SERVER_BRIDGE_TOKEN`。页面本身不鉴权，但页面调用除 `/health` 外的 Bridge API 时会带上配置的 `X-Bridge-Token`。

验收步骤：

1. 打开 `/mobile`
2. 填入 Bridge Token 并保存配置
3. 点击检查健康状态
4. 点击创建 Thread
5. 输入 `请只回复 mobile-ok` 并发送
6. 点击获取当前 Thread final
7. 点击运行连续会话测试，结果应显示 `PASS`
8. 点击删除当前 Thread

当前限制：

- POC 页面不接主系统
- 不做持久化
- 服务重启后 thread 丢失
- 不支持 SSE
- 不支持审批 UI
- 不支持 diff UI

## POC-6：手机端可用性增强与会话管理

启动 Bridge：

```powershell
$env:APP_SERVER_BRIDGE_TOKEN = "dev-token"
python .\poc\app_server\app_server_bridge.py --host 127.0.0.1 --port 8766
```

本机访问：

```text
http://127.0.0.1:8766/mobile
```

手机局域网访问：

```powershell
$env:APP_SERVER_BRIDGE_TOKEN = "dev-token"
python .\poc\app_server\app_server_bridge.py --host 0.0.0.0 --port 8766
```

```text
http://<电脑局域网IP>:8766/mobile
```

局域网访问提醒：

- 仅限可信局域网。
- 必须设置 `APP_SERVER_BRIDGE_TOKEN`。
- 页面本身不鉴权，但页面调用 Bridge API 时会带 `X-Bridge-Token`。
- 不要公网暴露该 POC 服务。

POC-6 增强点：

- `GET /health` 返回 `mode`、`sandbox`、`idle_timeout_seconds`、`codex_command`、`repo_root` 等状态字段。
- `POST /threads` 支持传入 `title`，`GET /threads` 和 `GET /threads/{id}` 返回标题。
- `PATCH /threads/{id}` 支持重命名当前内存态 thread。
- 手机页顶部展示 health、token 状态、当前 thread 标题和短 ID。
- 手机页支持 thread 标题输入、创建后自动选中、列表高亮、重命名、删除确认。
- 手机页支持 prompt 模板、final/events 复制、错误清空、长任务提示、消息字数统计。

POC-6 验收步骤：

1. 打开 `http://127.0.0.1:8766/mobile`
2. 保存 token：`dev-token`
3. 点击检查 health
4. 输入标题并创建 Thread
5. 发送 `请只回复 mobile-ok`
6. 获取 final
7. 复制 final
8. 使用模板填充 prompt
9. 重命名 Thread
10. 运行连续会话测试，结果应显示 `PASS`
11. 删除 Thread

当前限制：

- 单进程内存态。
- 服务重启后 thread 丢失。
- 不接 backend/runner 主系统。
- 不支持 SSE。
- 不支持审批 UI。
- 不支持 diff UI。
- 仍然是 App Server experimental POC。

## 协议推断

当前根据 schema 推断的最小流程是：

1. `initialize`
2. `thread/start`
3. `turn/start`

`turn/start` 会发送最小文本输入：

```text
请只回复 app-server-python-ok，不要修改任何文件。
```

## POC-1 预期输出

脚本会在 `poc/app_server` 下生成：

- `events-<timestamp>.jsonl`：app-server stdout 中收到的 JSON 行
- `app-server-stderr-<timestamp>.log`：app-server stderr

如果协议或运行环境导致失败，脚本会输出：

- 卡住的协议步骤
- 已收到的 JSON 行数量
- 最近收到的 method 或 response id
- 下一步应检查的 schema 文件

## 风险

- App Server 仍属 experimental 能力，协议字段和 method 名称可能变动。
- 当前 POC 只验证 stdio JSONL 通信，不承担任务调度、持久化、权限治理或生产链路职责。
- 当前使用 Python 标准库实现，不引入额外依赖。
