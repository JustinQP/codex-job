# Codex Remote Runner MVP

这是一个最小可用的 Codex Remote Runner。它提供 FastAPI 接口用于配置项目和提交任务，由本机独立 Runner 进程轮询 SQLite 中的任务，并调用 Codex CLI 在已配置项目目录中执行。

v0.1 只覆盖单机 MVP：

- Python + FastAPI 后端
- SQLite + SQLModel 持久化
- 独立 Python Runner 轮询任务
- 调用本机 Codex CLI
- 保存任务日志、最后结果和 `git diff`
- 不自动 `git commit`
- 不自动 `git push`
- 不提供任意 shell 命令执行接口

## 目录结构

```text
backend/
  main.py
  db.py
  models.py
  schemas.py
  services/
runner/
  runner.py
  codex_executor.py
  config.py
scripts/
  demo_create_task.py
data/
docs/
  01-mvp-design.md
requirements.txt
```

## 环境准备

建议使用虚拟环境：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

确认本机可以执行 Codex CLI。Runner 会优先读取 `CODEX_BIN`，未配置时依次查找 `codex.cmd`、`codex`、`codex.exe`。

可选环境变量：

```bash
set CODEX_BIN=C:\path\to\codex.cmd
set CODEX_RUNNER_DATA_DIR=E:\JustinQP\codex-job\data
set CODEX_RUNNER_DB_PATH=E:\JustinQP\codex-job\data\app.db
set RUNNER_POLL_INTERVAL_SECONDS=5
set TASK_TIMEOUT_SECONDS=7200
```

PowerShell 示例：

```powershell
$env:CODEX_BIN="C:\path\to\codex.cmd"
```

## 启动后端

```bash
uvicorn backend.main:app --reload
```

默认地址：

- API 文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/health

## 启动 Runner

持续轮询：

```bash
python runner/runner.py
```

只处理一次任务，适合调试：

```bash
python runner/runner.py --once
```

## 创建项目

```bash
curl -X POST http://127.0.0.1:8000/projects ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"demo\",\"path\":\"E:\\JustinQP\\codex-job\",\"enabled\":true}"
```

PowerShell：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/projects `
  -ContentType "application/json" `
  -Body '{"name":"demo","path":"E:\JustinQP\codex-job","enabled":true}'
```

## 创建任务

```bash
curl -X POST http://127.0.0.1:8000/tasks ^
  -H "Content-Type: application/json" ^
  -d "{\"project_id\":1,\"prompt\":\"请查看 README.md 并总结项目用途。\",\"timeout_seconds\":7200}"
```

PowerShell：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/tasks `
  -ContentType "application/json" `
  -Body '{"project_id":1,"prompt":"请查看 README.md 并总结项目用途。","timeout_seconds":7200}'
```

## Demo 脚本

在后端启动后运行：

```bash
python scripts/demo_create_task.py --project-path E:\JustinQP\codex-job
```

如果已经有项目 ID：

```bash
python scripts/demo_create_task.py --project-id 1 --prompt "请检查 README.md 是否清晰。"
```

## 查看任务

```bash
curl http://127.0.0.1:8000/tasks
curl http://127.0.0.1:8000/tasks/1
curl http://127.0.0.1:8000/tasks/1/log
curl http://127.0.0.1:8000/tasks/1/result
curl http://127.0.0.1:8000/tasks/1/diff
```

任务产物默认保存到：

```text
data/jobs/<task_id>/
  run.log
  result.md
  diff.patch
```

## 基础自检

```bash
python -m compileall backend runner scripts
python -c "from backend.db import init_db; init_db(); print('db ok')"
```

## 当前限制

- 暂不支持用户登录、权限、审计。
- 暂不支持取消正在运行的 Codex 子进程，`CANCELLED` 状态为后续能力预留。
- 暂不支持任务重试、并发锁增强、分页和搜索。
- Runner 适合单机单进程使用，多 Runner 并发认领任务需要后续加强数据库锁。
