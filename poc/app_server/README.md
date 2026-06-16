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

## 运行 Python POC

在项目根目录执行：

```powershell
python .\poc\app_server\app_server_stdio_client.py
```

如 `codex.cmd` 不在当前 PATH，可显式指定：

```powershell
python .\poc\app_server\app_server_stdio_client.py --codex-command C:\path\to\codex.cmd
```

## 协议推断

当前根据 schema 推断的最小流程是：

1. `initialize`
2. `thread/start`
3. `turn/start`

`turn/start` 会发送最小文本输入：

```text
请只回复 app-server-python-ok，不要修改任何文件。
```

## 预期输出

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
