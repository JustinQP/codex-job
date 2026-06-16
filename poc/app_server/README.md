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
