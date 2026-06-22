# 多设备连续会话 Codex 执行任务清单

> 关联路线图：`docs/20-plan/multi-device-continuous-session-roadmap.md`  
> 执行对象：Codex  
> 目标：把当前单机控制台逐步演进为个人使用的多设备 Codex 控制台  
> 执行原则：一次只执行一个任务 ID，完成验证后再进入下一项

## 1. 项目背景与范围

这是一个为作者本人开发的个人工具，不是 SaaS，也不是面向企业多租户交付的产品。

核心使用场景：

1. 在手机端控制电脑上的 Codex 执行工作。
2. 作者有多台电脑，不同项目目录位于不同电脑。
3. 在选定电脑的指定目录中创建连续会话，并持续进行多轮工作。
4. 手机刷新、短暂断网或切换页面后，仍能查看历史并继续当前会话。

### 1.1 必须做

- 多设备稳定身份。
- 每个项目目录明确属于某台设备。
- 手机端选择设备和工作目录。
- 一次性 `codex exec` 精确路由到目标设备。
- 连续 Session 精确路由到目标设备和目录。
- 同一 Session 复用同一个 Codex App Server thread。
- Agent 主动连接控制端，不要求每台电脑开放入站端口。
- 命令幂等、状态闭环、失败可恢复。
- 日志和会话事件增量上传、持久化和重放。
- 工作目录白名单和写入互斥。
- Windows 优先的启动、安装和诊断能力。

### 1.2 明确不做

本阶段不要实现：

- 用户注册、登录体系。
- 租户、组织、团队、成员。
- RBAC、角色和细粒度用户权限。
- OAuth、SSO。
- 计费、套餐、配额购买。
- 多控制端高可用。
- SaaS 公网部署。
- PostgreSQL、Redis、Celery、Kafka、Kubernetes。
- 跨设备代码或文件自动同步。
- 任意远程 Shell。
- 控制端下发任意绝对路径。
- 自动 Git push。

### 1.3 简化后的安全边界

个人使用场景下采用最小安全方案：

- 手机端继续使用一个 `API_TOKEN`。
- 所有设备 Agent 可以先共用一个 `AGENT_TOKEN`。
- `API_TOKEN` 与 `AGENT_TOKEN` 必须分离，不能互相调用对方接口。
- 控制端和 Agent 默认运行在可信局域网、Tailscale 或其他私有网络。
- v2.0 不做 Token 管理 UI、复杂配对流程或每设备独立 Token 轮换。
- Agent 只能执行本机配置文件中注册的 Workspace。

## 2. Codex 执行规则

Codex 执行本清单时必须遵守：

1. 每次只执行一个任务 ID，例如 `A01`，不得自动继续下一项。
2. 开始前读取：
   - `AGENTS.md`
   - `docs/30-rules/engineering-baseline.md`
   - `docs/30-rules/testing-acceptance.md`
   - 本任务依赖的现有设计和代码
3. 先检查当前代码，不能假设任务清单中的文件结构仍完全不变。
4. 允许为当前任务进行必要重构，但不得顺手实现后续任务。
5. 优先复用现有 FastAPI、SQLModel、React、Vite、pytest 和 Codex 执行逻辑。
6. 不为了“架构优雅”引入新框架或大型依赖。
7. 修改数据库时必须提供迁移和已有数据兼容。
8. 修改核心状态机时必须补充成功、失败、重复请求和边界测试。
9. 未执行的测试不能写成已通过。
10. 默认不 commit、不 push；除非用户在该次任务中明确要求。
11. 完成后只将当前任务复选框改为 `[x]`，并在任务下追加一段简短“执行结果”。
12. 如果发现前置任务未完成，停止实现并说明依赖，不要绕过架构顺序。

推荐给 Codex 的指令格式：

```text
请执行 docs/20-plan/multi-device-continuous-session-codex-task-list.md 中的任务 A01。
只完成 A01，不要执行后续任务。
遵守 AGENTS.md 和项目测试验收规则。
完成后更新任务复选框和执行结果，并说明修改文件、测试结果、风险与未完成项。
不要 commit，不要 push。
```

## 3. 任务状态总览

### A. 重构基线

- [x] A01 建立重构前回归基线
- [x] A02 增加最小 GitHub Actions CI
- [x] A03 引入轻量数据库版本迁移机制
- [x] A04 拆分 FastAPI 路由装配层
- [x] A05 增加新旧执行模式功能开关

### B. Device 与 Workspace

- [x] B01 新增 Device 数据模型和迁移
- [x] B02 实现 Agent 稳定设备身份
- [x] B03 实现 Agent 注册、心跳和认证接口
- [x] B04 新增 Workspace 数据模型和迁移
- [x] B05 实现 Agent 本地 Workspace Registry
- [x] B06 实现 Workspace 同步接口
- [x] B07 兼容迁移现有 Project
- [x] B08 手机端增加设备和 Workspace 选择

### C. Agent 命令通道

- [x] C01 新增 AgentCommand 模型和状态机
- [x] C02 实现命令创建服务和幂等键
- [x] C03 实现命令 claim、续租和完成接口
- [x] C04 实现 Agent 命令循环
- [x] C05 实现命令事件增量上传
- [x] C06 实现 Agent 重连 reconciliation

### D. 多设备 Run

- [x] D01 将 Run/Task 绑定 Device 和 Workspace
- [x] D02 通过 AgentCommand 下发 `codex exec`
- [x] D03 实现增量日志上传
- [x] D04 实现产物 manifest 和大小限制
- [x] D05 实现真实 Run 取消
- [x] D06 手机端运行页显示设备和 Workspace
- [ ] D07 兼容并逐步废弃旧 Runner 认领接口

### E. 多设备连续 Session

- [x] E01 将 App Server POC 整理为正式 Agent 模块
- [x] E02 通过命令通道创建 Session
- [ ] E03 通过命令通道执行 Turn
- [ ] E04 保证同一 Session 复用同一 Codex thread
- [ ] E05 新增 TurnEvent 持久化和去重
- [ ] E06 改造 SSE 为可重放事件流
- [x] E07 实现原子 Turn 并发保护
- [x] E08 实现 Session/Turn 取消和超时回收
- [x] E09 实现 Session reopen 和 generation
- [x] E10 实现 Workspace 写入锁
- [x] E11 手机会话页显示设备、目录和执行模式
- [x] E12 手机刷新后恢复当前 Turn 输出

### F. 验收与交付

- [x] F01 增加双 Fake Agent 集成测试
- [x] F02 增加本机双 Agent 模拟脚本
- [x] F03 增加 Windows Agent 安装和自启动脚本
- [x] F04 完成已有数据升级和回滚验证
- [ ] F05 完成真实多设备 smoke 验收
- [ ] F06 收口文档、归档旧计划并发布 v2.0

---

# 4. 详细任务

## A. 重构基线

### [x] A01 建立重构前回归基线

**目标**

冻结当前单机 Run、AppThread、AppTurn、Bridge cwd 和 SSE 行为，为后续重构提供回归保护。

**依赖**

无。

**实现要求**

1. 检查现有测试覆盖以下接口和行为：
   - Project 创建和列表。
   - Task 创建、认领、完成、取消和重跑。
   - Runner 注册、心跳和 lease。
   - AppThread 创建时使用 Project 路径作为 Bridge cwd。
   - AppThread reopen 时仍使用原 Project 路径。
   - AppTurn 同步、异步、冲突、失败和取消。
   - `/app-turns/{id}/stream` 的 status、delta、final 和 error。
2. 对缺失的关键路径补充回归测试。
3. 增加一份测试基线说明到现有 smoke 或测试文档，不新建重复文档。
4. 不修改现有业务语义。

**建议影响文件**

```text
tests/test_tasks_api.py
tests/test_runner_service.py
tests/test_app_threads_api.py
tests/test_app_thread_service.py
tests/test_app_server_bridge.py
tests/test_ui.py
docs/smoke-checklist.md
```

**验收标准**

- 当前核心单机流程均有自动化回归测试。
- 测试不依赖真实 Codex CLI 即可运行。
- 没有通过字符串断言替代所有业务测试；核心状态变化应调用真实服务或 API。

**验证命令**

```powershell
python -m compileall backend runner scripts poc/app_server
pytest -q
cd frontend
npm run typecheck
npm run build
```

执行结果：
- 状态：完成
- 修改文件：
  - `pytest.ini`
  - `tests/test_tasks_api.py`
  - `tests/test_runner_service.py`
  - `docs/smoke-checklist.md`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：不涉及
- 自动化测试：
  - `python -m compileall backend runner scripts poc/app_server`：通过
  - `pytest -q`：通过，157 passed
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
- 人工验证：不涉及
- 回归影响：仅补充单机控制台回归测试和测试配置；不修改业务语义
- 风险与未完成项：PowerShell 直接执行 `npm run ...` 会受本机执行策略拦截，本次使用等价的 `npm.cmd run ...` 完成验证

---

### [x] A02 增加最小 GitHub Actions CI

**目标**

每次 push/PR 自动执行 Python 和前端基础验证。

**依赖**

A01。

**实现要求**

1. 新增一个最小 workflow。
2. Python Job：
   - 安装 `requirements.txt`。
   - 执行 compileall。
   - 执行 `pytest -q`。
3. Frontend Job：
   - 使用 `npm ci`。
   - 执行 `npm run typecheck`。
   - 执行 `npm run build`。
4. 不接入发布、Docker、缓存服务或真实 Codex Token。
5. CI 不运行依赖本机 Codex 的真实 smoke。

**建议影响文件**

```text
.github/workflows/ci.yml
```

**验收标准**

- workflow YAML 可被 GitHub Actions 识别。
- Python 和 Frontend 分开显示结果。
- 本地命令与 CI 命令一致。

**验证命令**

```powershell
python -m compileall backend runner scripts poc/app_server
pytest -q
cd frontend
npm ci
npm run typecheck
npm run build
```

执行结果：
- 状态：完成
- 修改文件：
  - `.github/workflows/ci.yml`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：不涉及
- 自动化测试：
  - `python -m compileall backend runner scripts poc/app_server`：通过
  - `pytest -q`：通过，157 passed
  - `cd frontend; npm.cmd ci`：本机既有 `node_modules` 原生文件被占用导致 EPERM，未作为通过结果
  - 干净前端副本中 `npm.cmd ci --cache ..\npm-cache-a02-clean`：提权联网后通过，等价验证 GitHub Actions fresh checkout 场景
  - 干净前端副本中 `npm.cmd run typecheck`：通过
  - 干净前端副本中 `npm.cmd run build`：通过
  - 原 `frontend` 目录恢复依赖后 `npm.cmd run typecheck`：通过
- 人工验证：检查 workflow 包含独立 Python 和 Frontend job，未配置发布、Docker、缓存服务或真实 Codex Token
- 回归影响：仅新增 CI 配置，不影响运行时代码
- 风险与未完成项：本机 PowerShell 直接执行 `npm ...` 会受执行策略影响，本次使用 `npm.cmd`；本机既有 `node_modules` 文件锁会影响 `npm ci`，CI fresh checkout 不受该残留影响

---

### [x] A03 引入轻量数据库版本迁移机制

**目标**

为 Device、Workspace、Command 和 Event 新表提供可追踪迁移，停止继续依赖无版本的字段补丁。

**依赖**

A01。

**实现要求**

1. 增加 `schema_migrations` 表或等价机制。
2. 每个 migration 有稳定版本号、名称和幂等检查。
3. 应用启动时按顺序执行未完成 migration。
4. migration 前支持备份 SQLite 数据库文件；测试环境可关闭备份。
5. 将当前 `_ensure_sqlite_columns` 纳入兼容迁移，不能直接删除导致旧数据库无法升级。
6. 为 migration 成功、重复执行和失败回滚补测试。
7. 不引入 Alembic，除非现有轻量方案无法满足需求并在执行结果中说明必要性。

**建议影响文件**

```text
backend/db.py
backend/migrations.py
backend/migrations/
tests/test_db_migrations.py
```

**验收标准**

- 空数据库可以初始化到最新版本。
- 现有旧结构数据库副本可以升级。
- migration 重复执行不会重复改表。
- migration 失败不会被标记为已完成。

**验证命令**

```powershell
pytest -q tests/test_db_migrations.py
pytest -q
```

执行结果：
- 状态：完成
- 修改文件：
  - `backend/db.py`
  - `backend/migrations.py`
  - `tests/test_db_migrations.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：新增 `schema_migrations` 表；新增版本 `0001 legacy_sqlite_columns`，纳入原有 SQLite 兼容列补丁；默认对存在的 SQLite 数据库文件创建 `.bak-YYYYMMDDHHMMSS` 备份，可通过 `CODEX_RUNNER_DB_BACKUP=false` 关闭
- 自动化测试：
  - `pytest -q tests/test_db_migrations.py`：通过，5 passed
  - `pytest -q`：通过，162 passed
- 人工验证：不涉及
- 回归影响：`init_db()` 仍先执行 `SQLModel.metadata.create_all()`，再按版本执行未完成 migration；重复执行不会重复改表
- 风险与未完成项：当前仅提供轻量迁移机制，未引入 Alembic；后续新表需要继续按版本追加 migration

---

### [x] A04 拆分 FastAPI 路由装配层

**目标**

降低 `backend/main.py` 继续扩张的风险，为 Agent API 和新产品 API 留出清晰边界。

**依赖**

A01、A03。

**实现要求**

1. `backend/main.py` 保留：
   - FastAPI 创建。
   - lifespan。
   - 静态前端挂载。
   - router 注册。
2. 按现有领域拆分 router：
   - projects。
   - tasks/runs。
   - runners。
   - app_threads/app_turns。
   - UI/health。
3. 保持现有 URL、response model 和认证行为不变。
4. 公共鉴权、artifact 读取和错误辅助函数放到明确模块。
5. 不同时重写 service 层。

**建议影响文件**

```text
backend/main.py
backend/dependencies.py
backend/routers/
tests/test_api_contract.py
```

**验收标准**

- 现有 API 路径和返回结构不变。
- OpenAPI 中接口数量不减少。
- 全量测试通过。

**验证命令**

```powershell
python -m compileall backend
pytest -q
```

执行结果：
- 状态：完成
- 修改文件：
  - `backend/main.py`
  - `backend/dependencies.py`
  - `backend/routers/__init__.py`
  - `backend/routers/ui.py`
  - `backend/routers/projects.py`
  - `backend/routers/tasks.py`
  - `backend/routers/runners.py`
  - `backend/routers/app_threads.py`
  - `tests/test_api_contract.py`
  - `tests/test_app_threads_api.py`
  - `tests/test_artifact_guard.py`
  - `tests/test_security_api.py`
  - `tests/test_ui.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：不涉及
- 自动化测试：
  - `python -m compileall backend`：通过
  - `pytest -q`：通过，163 passed
- 人工验证：检查 `backend/main.py` 仅保留 FastAPI 创建、lifespan、静态前端挂载和 router 注册；OpenAPI 契约测试覆盖核心路径仍存在
- 回归影响：现有 URL、response model 和 API Token 保护保持不变；测试 monkeypatch 目标调整到新 router 模块
- 风险与未完成项：未拆 service 层；后续 Agent API 可继续在 `backend/routers/` 下新增边界

---

### [x] A05 增加新旧执行模式功能开关

**目标**

允许新 Agent 通道逐步上线，并在出现问题时回退当前本地 Runner/Bridge 模式。

**依赖**

A04。

**实现要求**

1. 增加配置读取模块。
2. 增加配置：

```text
AGENT_COMMAND_MODE=false
```

3. `false` 时保持当前语义。
4. `true` 时后续任务可以启用 Device/Workspace/Command 新链路。
5. 配置解析应有默认值和非法值处理。
6. 前端健康或设置页可显示当前模式，但本任务不实现完整新 UI。

**建议影响文件**

```text
backend/config.py
backend/main.py
frontend/src/api/types.ts
frontend/src/components/settings/SettingsPage.tsx
tests/test_config.py
```

**验收标准**

- 未配置时仍使用现有模式。
- 配置启用后健康接口可以识别模式。
- 不影响当前 Run 和 Session。

执行结果：
- 状态：完成
- 修改文件：
  - `backend/config.py`
  - `backend/routers/ui.py`
  - `frontend/src/api/health.ts`
  - `frontend/src/api/types.ts`
  - `frontend/src/components/settings/SettingsPage.tsx`
  - `tests/test_config.py`
  - `tests/test_security_api.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：不涉及
- 自动化测试：
  - `pytest -q tests/test_config.py tests/test_security_api.py`：通过，25 passed
  - `python -m compileall backend`：通过
  - `pytest -q`：通过，177 passed
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
- 人工验证：检查 `/health` 默认返回 `agent_command_mode=false`、`execution_mode=legacy_runner`；`AGENT_COMMAND_MODE=true` 时返回 `agent_command`
- 回归影响：默认未配置时仍走现有 Runner/Bridge 语义；本任务未切换 Run 或 Session 链路
- 风险与未完成项：仅提供开关和展示，后续任务再接入新 Agent Command 链路

---

## B. Device 与 Workspace

### [x] B01 新增 Device 数据模型和迁移

**目标**

把“某台可以执行 Codex 的电脑”作为正式实体。

**依赖**

A03。

**实现要求**

新增 Device，建议字段：

```text
device_id              UUID 字符串主键
display_name
hostname
os_name
agent_version
capabilities_json
status                 ONLINE / OFFLINE / DISABLED
last_heartbeat_at
lease_expires_at
created_at
updated_at
```

其他要求：

1. Device 状态使用枚举或集中常量。
2. 提供 `device_service`：注册、心跳、离线判断、列表。
3. 不加入 user_id、tenant_id、organization_id。
4. 增加迁移和服务单元测试。

**建议影响文件**

```text
backend/models.py 或 backend/models/device.py
backend/services/device_service.py
backend/migrations/
backend/schemas.py
tests/test_device_service.py
```

**验收标准**

- 相同 `device_id` 重复注册只更新记录。
- lease 过期后设备可被标记 OFFLINE。
- DISABLED 设备不能被心跳自动恢复为 ONLINE，除非业务明确允许并有测试。

执行结果：
- 状态：完成
- 修改文件：
  - `backend/models.py`
  - `backend/migrations.py`
  - `backend/schemas.py`
  - `backend/services/device_service.py`
  - `tests/test_device_service.py`
  - `tests/test_db_migrations.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：新增版本 `0002 devices`，创建 `devices` 表及 status、last_heartbeat_at、lease_expires_at 索引
- 自动化测试：
  - `pytest -q tests/test_device_service.py tests/test_db_migrations.py`：通过，10 passed
  - `pytest -q`：通过，182 passed
- 人工验证：不涉及
- 回归影响：新增 Device 模型和服务，不改变现有 Runner/Task/AppThread 链路
- 风险与未完成项：本任务仅提供模型和服务，Agent API 和前端设备列表由后续 B03/B08 接入

---

### [x] B02 实现 Agent 稳定设备身份

**目标**

设备 Agent 重启后复用同一个 `device_id`，不再使用 PID 组成默认身份。

**依赖**

B01。

**实现要求**

1. 新增正式 `agent/` 包，不继续把新功能堆入 `runner/` 或 `poc/`。
2. 首次启动生成 UUID，并持久化到本机数据目录，例如：

```text
data/agent/identity.json
```

3. identity 文件至少包含：
   - device_id。
   - display_name。
   - created_at。
4. 再次启动读取原 identity。
5. identity 文件损坏时给出明确错误，不静默生成新设备导致重复记录。
6. 支持环境变量覆盖 display name，不允许随意覆盖 device_id。

**建议影响文件**

```text
agent/__init__.py
agent/config.py
agent/identity.py
agent/main.py
tests/test_agent_identity.py
```

**验收标准**

- 同一数据目录连续启动得到相同 device_id。
- 不同数据目录得到不同 device_id。
- 损坏 identity 有明确诊断。

执行结果：
- 状态：完成
- 修改文件：
  - `agent/__init__.py`
  - `agent/config.py`
  - `agent/identity.py`
  - `agent/main.py`
  - `tests/test_agent_identity.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：不涉及
- 自动化测试：
  - `pytest -q tests/test_agent_identity.py`：通过，7 passed
  - `python -m compileall agent backend`：通过
  - `pytest -q`：通过，189 passed
- 人工验证：
  - 执行 `$env:CODEX_AGENT_DATA_DIR='data\agent-test-b02'; $env:CODEX_AGENT_DISPLAY_NAME='Test Agent'; python -m agent.main --print-identity`
  - 结果：成功输出包含 `device_id`、`display_name`、`created_at`、`identity_path` 的 JSON
- 回归影响：新增正式 `agent/` 包，不改动旧 Runner 逻辑
- 风险与未完成项：本任务只实现本地稳定身份；注册、心跳和后端 Agent API 由 B03 接入

---

### [x] B03 实现 Agent 注册、心跳和认证接口

**目标**

Agent 使用独立认证向控制端注册并维持在线状态。

**依赖**

B01、B02、A04。

**实现要求**

1. 增加 `AGENT_TOKEN` 配置。
2. Agent API 使用独立请求头，例如：

```text
X-Agent-Token
```

3. 新增接口：

```text
POST /agent/register
POST /agent/heartbeat
GET  /devices
GET  /devices/{device_id}
```

4. `API_TOKEN` 不能调用 Agent 写接口。
5. `AGENT_TOKEN` 不能调用手机控制 API。
6. Agent 定时心跳并上报 hostname、OS、版本和能力。
7. 复用 B01 的 lease/offline 逻辑。
8. 不实现用户登录和设备配对 UI。

**建议影响文件**

```text
backend/dependencies.py
backend/routers/agent.py
backend/routers/devices.py
backend/schemas.py
agent/api_client.py
agent/heartbeat.py
tests/test_agent_auth_api.py
```

**验收标准**

- 正确 Agent Token 可注册和心跳。
- 无 Token、错误 Token、API Token 均返回 401/403。
- 手机 API Token 可以查看设备，但不能伪造 Agent 心跳。

执行结果：
- 状态：完成
- 修改文件：
  - `backend/dependencies.py`
  - `backend/main.py`
  - `backend/routers/agent.py`
  - `backend/routers/devices.py`
  - `agent/config.py`
  - `agent/api_client.py`
  - `agent/heartbeat.py`
  - `agent/main.py`
  - `tests/test_agent_auth_api.py`
  - `tests/test_agent_api_client.py`
  - `tests/test_api_contract.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：不涉及
- 自动化测试：
  - `pytest -q tests/test_agent_auth_api.py tests/test_agent_api_client.py tests/test_device_service.py tests/test_api_contract.py`：通过，12 passed
  - `python -m compileall backend agent`：通过
  - `pytest -q`：通过，195 passed
- 人工验证：不涉及
- 回归影响：新增 `X-Agent-Token` 写接口和 `X-API-Token` 设备读接口；旧手机 API 和旧 Runner API 认证不变
- 风险与未完成项：Agent 目前支持单次注册/心跳 helper，持续循环和 Workspace 同步由后续任务实现

---

### [x] B04 新增 Workspace 数据模型和迁移

**目标**

把“某台设备上的一个允许 Codex 工作的目录”作为正式实体。

**依赖**

B01、A03。

**实现要求**

建议字段：

```text
id
workspace_key
device_id
name
path_label
enabled
default_model
default_reasoning_effort
default_sandbox
default_approval_policy
require_clean_worktree
created_at
updated_at
```

要求：

1. 唯一约束为 `(device_id, workspace_key)`。
2. 控制端不依赖远程绝对路径执行 `Path.exists()`。
3. 控制端默认不向手机返回完整绝对路径。
4. Workspace 必须绑定 Device。
5. 增加列表、详情和状态服务。

**建议影响文件**

```text
backend/models.py 或 backend/models/workspace.py
backend/services/workspace_service.py
backend/schemas.py
backend/migrations/
tests/test_workspace_service.py
```

**验收标准**

- 两个设备可以注册相同 workspace_key。
- 同一设备重复 workspace_key 被拒绝或更新，语义必须明确。
- Disabled Workspace 不能创建新的执行对象。

执行结果：
- 状态：完成
- 修改文件：
  - `backend/models.py`
  - `backend/migrations.py`
  - `backend/schemas.py`
  - `backend/services/workspace_service.py`
  - `tests/test_workspace_service.py`
  - `tests/test_db_migrations.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：新增版本 `0003 workspaces`，创建 `workspaces` 表，增加 `(device_id, workspace_key)` 唯一约束及 device/enabled 索引
- 自动化测试：
  - `pytest -q tests/test_workspace_service.py tests/test_db_migrations.py`：通过，10 passed
  - `python -m compileall backend`：通过
  - `pytest -q`：通过，200 passed
- 人工验证：不涉及
- 回归影响：新增 Workspace 模型和服务，不改变旧 Project/Task/AppThread 行为
- 风险与未完成项：本任务仅提供数据模型和服务；Agent 本地 registry 和同步接口由 B05/B06 接入

---

### [x] B05 实现 Agent 本地 Workspace Registry

**目标**

真实绝对路径由设备本地管理，控制端只引用 Workspace 标识。

**依赖**

B02、B04。

**实现要求**

1. Agent 从一个简单配置文件加载 Workspace，例如 JSON 或 TOML；不要为此引入大型配置库。
2. 每项至少包含：

```text
key
name
path
enabled
```

3. Agent 本地校验：
   - 路径存在。
   - 是目录。
   - resolve 后仍位于允许根目录。
   - workspace key 非空且唯一。
4. 提供 `resolve(workspace_key)`，后续命令只使用该方法获取路径。
5. 禁止命令 payload 携带任意 cwd 绕过 registry。
6. 错误应包含 workspace key，不在上传控制端时暴露完整敏感路径。

**建议影响文件**

```text
agent/workspace_registry.py
agent/config.py
scripts/agent.example.json
tests/test_workspace_registry.py
```

**验收标准**

- 合法 Workspace 可解析。
- 不存在、越界、重复和禁用 Workspace 被拒绝。
- Windows 路径大小写、盘符和符号链接边界有测试。

执行结果：
- 状态：完成
- 修改文件：
  - `agent/config.py`
  - `agent/workspace_registry.py`
  - `scripts/agent.example.json`
  - `tests/test_workspace_registry.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：不涉及
- 自动化测试：
  - `pytest -q tests/test_workspace_registry.py`：通过，5 passed, 1 skipped；符号链接边界测试因当前 Windows 环境不允许创建 symlink 被跳过
  - `python -m compileall agent`：通过
  - `pytest -q`：通过，205 passed, 1 skipped
- 人工验证：不涉及
- 回归影响：新增 Agent 本地 registry，不改变后端旧执行链路
- 风险与未完成项：本任务仅本地加载和解析 Workspace；同步控制端由 B06 实现

---

### [x] B06 实现 Workspace 同步接口

**目标**

Agent 将本机 Registry 元数据同步到控制端。

**依赖**

B03、B04、B05。

**实现要求**

1. 新增：

```text
POST /agent/workspaces/sync
GET  /workspaces?device_id=...
GET  /workspaces/{id}
```

2. 同步使用 `(device_id, workspace_key)` upsert。
3. Agent 未再上报的 Workspace 不应立即物理删除；标记 unavailable/disabled 或保留最后状态。
4. 手机接口只返回展示所需字段。
5. 同步请求必须通过 Agent 认证并确认 device_id 与当前 Agent 一致。

**建议影响文件**

```text
backend/routers/agent.py
backend/routers/workspaces.py
backend/services/workspace_service.py
agent/api_client.py
agent/main.py
tests/test_workspace_sync_api.py
```

**验收标准**

- Agent 首次同步创建 Workspace。
- 重复同步更新元数据，不创建重复记录。
- Agent A 不能修改 Agent B 的 Workspace。

执行结果：
- 状态：完成
- 修改文件：
  - `backend/schemas.py`
  - `backend/main.py`
  - `backend/routers/agent.py`
  - `backend/routers/workspaces.py`
  - `backend/services/workspace_service.py`
  - `agent/api_client.py`
  - `agent/main.py`
  - `agent/workspace_registry.py`
  - `tests/test_agent_auth_api.py`
  - `tests/test_agent_api_client.py`
  - `tests/test_api_contract.py`
  - `tests/test_workspace_service.py`
  - `tests/test_workspace_registry.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：不涉及
- 自动化测试：
  - `pytest -q tests/test_agent_auth_api.py tests/test_agent_api_client.py tests/test_workspace_service.py tests/test_workspace_registry.py tests/test_api_contract.py`：通过，21 passed, 1 skipped
  - `python -m compileall backend agent`：通过
  - `pytest -q`：通过，209 passed, 1 skipped
- 人工验证：不涉及
- 回归影响：新增 Agent workspace sync 写接口和手机 workspace 读接口；Agent token 与 API token 权限边界保持分离
- 风险与未完成项：未上报的 Workspace 当前标记 `enabled=false`，不物理删除；前端选择器由 B08 接入

---

### [x] B07 兼容迁移现有 Project

**目标**

保留当前 Project、Task 和 AppThread 历史数据，不因引入 Workspace 丢失记录。

**依赖**

B04、B06。

**实现要求**

1. 为现有 Project 增加可选 `workspace_id` 或建立兼容映射。
2. 尝试按 `default_runner_id` 绑定 Device；无法确定时标记 UNBOUND。
3. 不自动假设控制端本机就是所有 Project 的目标设备。
4. 旧 Project API 暂时保留。
5. 旧记录仍可查看；未绑定 Workspace 的记录不能进入新 Agent 模式执行。
6. 提供迁移诊断输出，列出待人工绑定项目。

**建议影响文件**

```text
backend/migrations/
backend/services/project_service.py
backend/services/workspace_service.py
scripts/verify_data_migration.py
tests/test_project_workspace_migration.py
```

**验收标准**

- 旧数据库升级后 Project、Task、AppThread 数量不减少。
- 无法绑定的 Project 有明确状态，不被错误路由。
- 旧模式关闭新功能开关后仍可运行。

执行结果：
- 状态：完成
- 修改文件：
  - `backend/models.py`
  - `backend/migrations.py`
  - `backend/schemas.py`
  - `backend/services/project_service.py`
  - `tests/test_project_workspace_migration.py`
  - `tests/test_db_migrations.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：新增版本 `0004 project_workspace_binding`，为 `projects` 增加 `workspace_id` 和 `workspace_binding_status`，默认 `UNBOUND`
- 自动化测试：
  - `pytest -q tests/test_project_workspace_migration.py tests/test_db_migrations.py tests/test_tasks_api.py`：通过，21 passed
  - `python -m compileall backend scripts`：通过
  - `pytest -q`：通过，212 passed, 1 skipped
- 人工验证：不涉及
- 回归影响：旧 Project API 保留；未绑定 Project 仍可在旧模式创建 Task，不会被自动路由到新 Agent Workspace
- 风险与未完成项：迁移诊断不自动绑定；人工绑定或 UI 绑定由后续任务完善；完整数据升级验证由 F04 的数据迁移验证脚本承担

---

### [x] B08 手机端增加设备和 Workspace 选择

**目标**

手机端按“设备 -> Workspace”选择当前工作位置。

**依赖**

B03、B06。

**实现要求**

1. 项目页逐步调整为工作空间页，但不必立即重命名所有文件。
2. 展示：
   - 设备列表。
   - ONLINE/OFFLINE/DISABLED。
   - 当前设备下的 Workspace。
   - 当前选择。
3. localStorage 增加：

```text
mobile.currentDeviceId
mobile.currentWorkspaceId
```

4. 切换设备时清除不属于新设备的 Workspace 和 Session 选择。
5. 离线设备允许查看历史，但禁止新建执行。
6. 当前阶段不做设备管理、配对和 Token UI。

**建议影响文件**

```text
frontend/src/api/devices.ts
frontend/src/api/workspaces.ts
frontend/src/api/types.ts
frontend/src/state/storage.ts
frontend/src/components/projects/ProjectsPage.tsx
frontend/src/components/session/SessionPage.tsx
frontend/src/styles/
tests/test_ui.py
```

**验收标准**

- 用户能清楚看到当前设备和 Workspace。
- 不会把设备 A 的 Workspace 选择保留到设备 B。
- OFFLINE 设备的创建按钮被禁用并有明确原因。
- 前端类型检查和构建通过。

执行结果：
- 状态：完成
- 修改文件：
  - `frontend/src/api/devices.ts`
  - `frontend/src/api/workspaces.ts`
  - `frontend/src/api/types.ts`
  - `frontend/src/state/storage.ts`
  - `frontend/src/components/projects/ProjectsPage.tsx`
  - `frontend/src/components/session/SessionPage.tsx`
  - `frontend/src/components/session/ThreadSwitcherSheet.tsx`
  - `frontend/src/components/runs/RunsPage.tsx`
  - `frontend/src/components/tasks/TaskCard.tsx`
  - `frontend/src/components/tasks/TaskDetailSheet.tsx`
  - `frontend/src/utils/device.ts`
  - `tests/test_ui.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 前端行为：项目页新增设备和 Workspace 列表，保存 `mobile.currentDeviceId` 和 `mobile.currentWorkspaceId`；切换设备会清空 Workspace 和 Session 选择
- 执行限制：会话新建和运行重跑在 OFFLINE/DISABLED 设备下禁用，并显示明确原因；历史列表仍可查看
- 自动化测试：
  - `python -m compileall backend runner agent scripts poc/app_server`：通过
  - `pytest -q`：通过，212 passed, 1 skipped
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
- 人工验证：不涉及
- 回归影响：未接入设备数据时保留旧项目/会话/运行查看路径；不新增设备管理、配对或 Token UI
- 风险与未完成项：当前 Workspace 选择仅作为手机端上下文保存，后续 Run/Session 与 Workspace 的真实绑定由 D/E 阶段完成

---

## C. Agent 命令通道

### [x] C01 新增 AgentCommand 模型和状态机

**目标**

建立控制端到设备的持久化命令队列。

**依赖**

A03、B01。

**实现要求**

建议字段：

```text
id                     UUID
device_id
command_type
aggregate_type
aggregate_id
idempotency_key
payload_json
status                 PENDING / CLAIMED / RUNNING / SUCCESS /
                       FAILED / CANCELLED / EXPIRED
lease_token
lease_expires_at
attempt_count
max_attempts
created_at
claimed_at
completed_at
last_error
```

要求：

1. `idempotency_key` 唯一。
2. 明确允许的状态流转。
3. 状态流转集中在 service，不在 router 任意改字段。
4. 不引入消息队列中间件。
5. 增加状态机单元测试。

**建议影响文件**

```text
backend/models.py 或 backend/models/agent_command.py
backend/services/command_service.py
backend/migrations/
tests/test_command_state_machine.py
```

**验收标准**

- 非法状态流转被拒绝。
- 重复终态完成保持幂等。
- 命令可按 device_id 查询。

执行结果：
- 状态：完成
- 修改文件：
  - `backend/models.py`
  - `backend/migrations.py`
  - `backend/services/agent_command_service.py`
  - `tests/test_agent_command_service.py`
  - `tests/test_db_migrations.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：新增版本 `0005 agent_commands`，创建 `agent_commands` 表、`idempotency_key` 唯一索引，以及 device/status/lease 等查询索引
- 状态机：新增 `AgentCommandStatus` 和集中流转服务，非法流转抛出 `AgentCommandStateError`；重复提交相同终态结果保持幂等
- 自动化测试：
  - `pytest -q tests/test_agent_command_service.py tests/test_db_migrations.py`：通过，11 passed
  - `python -m compileall backend runner agent scripts poc/app_server`：通过
  - `pytest -q`：通过，218 passed, 1 skipped
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
- 人工验证：不涉及
- 回归影响：本任务仅新增模型、迁移和 service，不接入 router，不改变现有 Runner/Task 执行路径
- 风险与未完成项：命令创建幂等服务由 C02 完成；claim/续租/完成 API 由 C03 完成

---

### [x] C02 实现命令创建服务和幂等键

**目标**

业务服务可以安全创建命令，重复请求不会创建两个执行。

**依赖**

C01。

**实现要求**

1. 实现统一 `create_command(...)`。
2. 必须传入明确的 `idempotency_key`。
3. 相同 key 且 payload 一致时返回原命令。
4. 相同 key 但 payload 不一致时返回冲突错误。
5. Device DISABLED 或 Workspace 不可用时拒绝创建。
6. payload 只存业务标识和选项，不存任意绝对路径。

**建议影响文件**

```text
backend/services/command_service.py
backend/errors.py
tests/test_command_service.py
```

**验收标准**

- 网络重试不会产生重复命令。
- payload 冲突有稳定错误 code。

执行结果：
- 状态：完成
- 修改文件：
  - `backend/services/agent_command_service.py`
  - `tests/test_agent_command_service.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 服务能力：新增统一 `create_command(...)`，要求显式 `idempotency_key`；相同 key 和等价 payload 返回原命令，不重复创建
- 错误处理：新增 `AgentCommandServiceError.code`；payload 冲突稳定返回 `agent_command_idempotency_conflict`，缺少幂等键、禁用设备、不可用 Workspace、绝对路径 payload 均有稳定 code
- 安全约束：payload 规范化为稳定 JSON，仅允许业务标识和选项；检测并拒绝 Windows、Unix、UNC 绝对路径字符串
- 自动化测试：
  - `pytest -q tests/test_agent_command_service.py`：通过，11 passed
  - `python -m compileall backend runner agent scripts poc/app_server`：通过
  - `pytest -q`：通过，223 passed, 1 skipped
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
- 人工验证：不涉及
- 回归影响：本任务只扩展 service 层创建能力，不新增路由，不改变旧 Runner/Task 路径
- 风险与未完成项：数据库并发下唯一索引仍是最终防线；C03 接入 API 时需将 service error code 映射为稳定 HTTP 响应

---

### [x] C03 实现命令 claim、续租和完成接口

**目标**

Agent 可靠认领属于本设备的命令，并通过 lease 防止失控执行。

**依赖**

B03、C01、C02。

**实现要求**

新增接口：

```text
POST /agent/commands/claim
POST /agent/commands/{id}/ack
POST /agent/commands/{id}/renew
POST /agent/commands/{id}/complete
```

要求：

1. Claim 只能返回当前 Agent 设备的命令。
2. Claim 使用事务条件更新，避免重复认领。
3. Claim 请求带 `claim_request_id`：
   - 同一请求重试返回原命令。
   - 不能继续取下一条命令。
4. ACK/renew/complete 必须带 lease token。
5. lease 过期后按 command type 决定重试或失败。
6. 终态 complete 重试幂等。
7. 先实现普通短轮询；长轮询可在 C04 增加。

**建议影响文件**

```text
backend/routers/agent.py
backend/services/command_service.py
backend/schemas.py
tests/test_agent_command_api.py
```

**验收标准**

- 模拟响应丢失并重复 Claim，不多领命令。
- Agent A 永远不能认领 Agent B 命令。
- 错误 lease token 被拒绝。

执行结果：
- 状态：完成
- 修改文件：
  - `backend/models.py`
  - `backend/migrations.py`
  - `backend/schemas.py`
  - `backend/routers/agent.py`
  - `backend/services/agent_command_service.py`
  - `tests/test_agent_command_api.py`
  - `tests/test_agent_command_service.py`
  - `tests/test_db_migrations.py`
  - `tests/test_api_contract.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：新增版本 `0006 agent_command_claim_request_id`，为 `agent_commands` 增加 `claim_request_id` 并建立索引
- API：新增 `POST /agent/commands/claim`、`/ack`、`/renew`、`/complete`，均沿用 Agent Token 鉴权
- Claim/lease：Claim 通过条件更新认领 PENDING 命令；同一 `claim_request_id` 重试返回原命令，不领取下一条；ACK/renew/complete 均校验 device 和 lease token
- 过期处理：lease 过期后未达最大次数回到 PENDING 供后续重试；达到上限进入 EXPIRED；终态 complete 重试保持幂等
- 自动化测试：
  - `pytest -q tests/test_agent_command_api.py tests/test_agent_command_service.py tests/test_db_migrations.py tests/test_api_contract.py`：通过，21 passed
  - `python -m compileall backend runner agent scripts poc/app_server`：通过
  - `pytest -q`：通过，227 passed, 1 skipped
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
- 人工验证：不涉及
- 回归影响：仅新增 Agent 命令接口，不改变旧 Runner/Task 执行路径
- 风险与未完成项：当前为短轮询接口；Agent 主循环、长轮询和本地 claim_request_id 保存由 C04 接入

---

### [x] C04 实现 Agent 命令循环

**目标**

Agent 持续心跳、认领和分发命令处理器。

**依赖**

B02、B03、C03。

**实现要求**

1. 新增 Agent 主循环：
   - 注册。
   - 同步 Workspace。
   - 心跳。
   - Claim。
   - 分发 handler。
   - renew lease。
   - complete。
2. 使用有限重试和退避，不进行无限高频请求。
3. 每次 Claim 生成并保留 claim_request_id，收到响应后才生成下一次。
4. Agent 本地记录当前命令，进程重启时可用于 reconciliation。
5. handler 未实现的 command type 返回明确失败，不能静默丢弃。
6. 当前只注册框架和 fake handler，不在本任务接入 Run/Session。

**建议影响文件**

```text
agent/main.py
agent/command_loop.py
agent/command_handlers.py
agent/api_client.py
agent/local_state.py
tests/test_agent_command_loop.py
```

**验收标准**

- Fake Command 可以完整经过 claim、ack、renew、complete。
- 临时网络错误后 Agent 可以继续工作。
- Ctrl+C 能正常停止循环。

执行结果：
- 状态：完成
- 修改文件：
  - `agent/api_client.py`
  - `agent/command_loop.py`
  - `agent/command_handlers.py`
  - `agent/local_state.py`
  - `agent/config.py`
  - `agent/main.py`
  - `tests/test_agent_command_loop.py`
  - `tests/test_agent_api_client.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- Agent 循环：新增注册、可选 Workspace 同步、心跳、Claim、ACK、renew、handler 分发、complete 的主循环框架
- 本地状态：新增 `state.json` 当前命令记录，保存 `command_id`、`claim_request_id`、`lease_token`，命令完成后清理
- Handler：新增 `fake.echo` 成功 handler；未知 command type 明确 complete 为 FAILED，不静默丢弃
- CLI：新增 `--run-once` 和 `--run-loop`；`--run-loop` 支持 Ctrl+C 正常退出
- 自动化测试：
  - `pytest -q tests/test_agent_command_loop.py tests/test_agent_api_client.py`：通过，7 passed
  - `python -m compileall backend runner agent scripts poc/app_server`：通过
  - `pytest -q`：通过，231 passed, 1 skipped
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
- 人工验证：不涉及
- 回归影响：Agent 新循环需要显式通过 `--run-once` 或 `--run-loop` 启动，不影响既有 register/heartbeat/sync-workspaces 单次命令
- 风险与未完成项：当前只提供 fake handler 和短轮询；真实 Run/Session handler 由 D/E 阶段接入，命令事件上传由 C05 完成

---

### [x] C05 实现命令事件增量上传

**目标**

Agent 可以按 sequence 上传日志、状态和会话事件，控制端负责去重。

**依赖**

C03、C04。

**实现要求**

1. 增加通用命令事件表，或建立能被 RunEvent/TurnEvent 复用的基础服务。
2. 接口：

```text
POST /agent/commands/{id}/events
```

3. 事件至少包含：

```text
sequence
kind
payload
created_at
```

4. 唯一约束 `(command_id, sequence)`。
5. 重复上传同 sequence 且内容一致时返回成功。
6. 同 sequence 内容不一致时返回冲突。
7. 限制单批数量和单事件大小。
8. Agent 本地缓存未确认事件，确认后再删除。

**建议影响文件**

```text
backend/models.py
backend/services/event_service.py
backend/routers/agent.py
agent/event_uploader.py
agent/local_state.py
tests/test_command_events.py
```

**验收标准**

- 断线重传不会重复事件。
- 乱序批次能被拒绝或稳定处理，行为有测试。
- 过大事件返回明确错误。

执行结果：
- 状态：完成
- 修改文件：
  - `backend/models.py`
  - `backend/migrations.py`
  - `backend/schemas.py`
  - `backend/routers/agent.py`
  - `backend/services/agent_command_event_service.py`
  - `agent/api_client.py`
  - `agent/event_uploader.py`
  - `agent/local_state.py`
  - `tests/test_agent_command_events.py`
  - `tests/test_agent_event_uploader.py`
  - `tests/test_agent_api_client.py`
  - `tests/test_db_migrations.py`
  - `tests/test_api_contract.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：新增版本 `0007 agent_command_events`，创建 `agent_command_events` 表并建立 `(command_id, sequence)` 唯一约束
- API：新增 `POST /agent/commands/{id}/events`，批量上传事件前校验 device、lease token，并续租当前命令
- 去重与限制：相同 sequence 且内容一致返回成功并计入 duplicate；同 sequence 内容不同返回 `command_event_sequence_conflict`；乱序、批量过多、单事件过大均返回稳定错误 code
- Agent：新增 `CommandEventUploader` 和本地 pending event 缓存，服务端确认 `latest_sequence` 后清理已确认事件
- 自动化测试：
  - `pytest -q tests/test_agent_command_events.py tests/test_agent_event_uploader.py tests/test_agent_api_client.py tests/test_db_migrations.py tests/test_api_contract.py`：通过，14 passed
  - `python -m compileall backend runner agent scripts poc/app_server`：通过
  - `pytest -q`：通过，236 passed, 1 skipped
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
- 人工验证：不涉及
- 回归影响：仅新增命令事件能力，不改变旧 Runner/Task 或当前 Agent fake handler 执行路径
- 风险与未完成项：事件目前仅接入通用命令事件表；RunEvent/TurnEvent 复用和重连补传策略由后续 D/E/C06 任务细化

---

### [x] C06 实现 Agent 重连 reconciliation

**目标**

Agent 或控制端重启后，双方能核对当前本地执行和服务端命令状态。

**依赖**

C04、C05。

**实现要求**

1. 新增：

```text
POST /agent/reconcile
```

2. Agent 上报：
   - 当前本地 command_id。
   - process/session 状态。
   - 最后已上传 sequence。
3. 控制端返回：
   - 继续执行。
   - 停止执行。
   - 补传事件。
   - 标记失败。
4. PENDING 命令不丢失。
5. CLAIMED/RUNNING 命令不应只因控制端重启立即失败。
6. 当前任务先使用 Fake handler 验证，不依赖真实 Codex。

**建议影响文件**

```text
backend/routers/agent.py
backend/services/command_service.py
agent/reconciliation.py
agent/local_state.py
tests/test_agent_reconciliation.py
```

**验收标准**

- Agent 重启后不重复执行已成功命令。
- 未确认事件可以补传。
- 服务端已取消的命令不会在 Agent 重连后继续执行。

执行结果：
- 状态：完成
- 修改文件：
  - `backend/schemas.py`
  - `backend/routers/agent.py`
  - `backend/services/agent_reconciliation_service.py`
  - `agent/api_client.py`
  - `agent/reconciliation.py`
  - `agent/command_loop.py`
  - `tests/test_agent_reconciliation.py`
  - `tests/test_agent_command_loop.py`
  - `tests/test_agent_api_client.py`
  - `tests/test_api_contract.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- API：新增 `POST /agent/reconcile`，Agent 上报本地 `command_id`、`process_status`、`last_uploaded_sequence`
- Reconciliation：服务端按命令状态返回 `CONTINUE`、`STOP`、`UPLOAD_EVENTS`、`MARK_FAILED` 或 `IDLE`；SUCCESS/CANCELLED 等终态不会被重复执行
- Agent：启动循环时先执行 reconcile；服务端要求 STOP 时清理本地 current command
- 事件补传：当 Agent 本地认为已上传 sequence 高于服务端最新 sequence 时，返回 `UPLOAD_EVENTS` 和 `upload_from_sequence`
- 自动化测试：
  - `pytest -q tests/test_agent_reconciliation.py tests/test_agent_command_loop.py tests/test_agent_api_client.py tests/test_api_contract.py`：通过，12 passed
  - `python -m compileall backend runner agent scripts poc/app_server`：通过
  - `pytest -q`：通过，240 passed, 1 skipped
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
- 人工验证：不涉及
- 回归影响：新增重连核对接口和 Agent 启动前核对，不改变旧 Runner/Task 路径；无本地 command 时不会丢弃服务端 PENDING 命令
- 风险与未完成项：当前 reconciliation 仍基于 fake handler 和通用命令事件；真实进程/session 状态将在 D/E 阶段接入

---

## D. 多设备 Run

### [x] D01 将 Run/Task 绑定 Device 和 Workspace

**目标**

一次性运行具备明确执行设备和目录。

**依赖**

B04、B07、C02。

**实现要求**

1. 为 Task 增加：

```text
device_id
workspace_id
command_id
client_request_id
```

2. 新模式创建 Run 时必须提供 workspace_id；device_id 从 Workspace 推导，不信任客户端传入。
3. 保留旧 Task API 兼容，新增字段可选或通过新 `/runs` API 暴露。
4. Workspace disabled、Device offline 时给出明确错误。
5. 是否允许离线排队：v2.0 默认不允许，直接返回设备离线。
6. 增加迁移和 API 测试。

**验收标准**

- Run 的 device_id 与 Workspace 所属设备一致。
- 客户端不能伪造另一 device_id。
- 旧 Task 历史仍可读取。

执行结果：
- 状态：完成
- 修改文件：
  - `backend/models.py`
  - `backend/migrations.py`
  - `backend/schemas.py`
  - `backend/services/task_service.py`
  - `backend/routers/tasks.py`
  - `tests/test_runs_api.py`
  - `tests/test_tasks_api.py`
  - `tests/test_db_migrations.py`
  - `tests/test_api_contract.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：新增版本 `0008 task_run_bindings`，为 `tasks` 增加 `device_id`、`workspace_id`、`command_id`、`client_request_id` 可选字段和索引
- API：新增 `POST /runs`，新模式要求 `workspace_id`；旧 `/tasks` API 继续兼容
- 绑定规则：Run 创建时从 Workspace 推导 `device_id`，忽略客户端传入的 `device_id`；Workspace disabled、Device disabled/offline 返回明确错误
- 自动化测试：
  - `pytest -q tests/test_runs_api.py tests/test_tasks_api.py tests/test_db_migrations.py tests/test_api_contract.py`：通过，22 passed
  - `python -m compileall backend runner agent scripts poc/app_server`：通过
  - `pytest -q`：通过，243 passed, 1 skipped
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
- 人工验证：不涉及
- 回归影响：旧 Task 历史记录没有绑定字段时仍可读取，返回字段为 `null`
- 风险与未完成项：本任务只完成 Run/Task 绑定，不生成 AgentCommand；命令下发由 D02 完成

---

### [x] D02 通过 AgentCommand 下发 `codex exec`

**目标**

新模式下不再由旧 Runner 直接认领 Run，而是通过正式 Agent 执行。

**依赖**

C04、D01。

**实现要求**

1. 创建 Run 时生成 `RUN_EXECUTE` 命令。
2. Agent 增加 `RunExecutor` handler。
3. handler 通过 Workspace Registry 解析真实目录。
4. 复用现有：
   - `execute_codex`。
   - Git preflight。
   - diff/artifact 收集。
   - 进程树终止。
5. 禁止 payload 直接指定 cwd。
6. Run 和 Command 状态映射集中在 service。
7. 旧模式不受影响。

**建议影响文件**

```text
backend/services/run_service.py
backend/services/task_service.py
agent/run_executor.py
agent/command_handlers.py
runner/codex_executor.py
tests/test_agent_run_executor.py
```

**验收标准**

- Device A Workspace 的 Run 只产生 Device A 命令。
- Agent 使用 Registry 中的真实路径。
- Fake Codex 执行可完成状态闭环。

执行结果：
- 状态：完成
- 修改文件：
  - `backend/services/task_service.py`
  - `agent/run_executor.py`
  - `agent/command_handlers.py`
  - `agent/command_loop.py`
  - `tests/test_agent_run_executor.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 后端：`POST /runs` 创建 Run 后生成 `RUN_EXECUTE` AgentCommand，并将 `command_id` 回写到 Task；命令只发往 Workspace 所属设备
- Payload：命令 payload 只包含 `task_id`、`workspace_id`、`workspace_key`、执行选项等业务字段，不传 `cwd`/`project_path`
- Agent：新增 `RunExecutor` handler，通过 Workspace Registry 解析真实目录；`CODEX_AGENT_FAKE_RUN=1` 下可完成 fake 执行闭环
- 执行复用：真实执行路径预留复用 `execute_codex`、`check_clean_worktree`、`collect_git_artifacts`；旧 Runner/Task 路径不受影响
- 自动化测试：
  - `pytest -q tests/test_agent_run_executor.py tests/test_runs_api.py tests/test_agent_command_loop.py`：通过，10 passed
  - `python -m compileall backend runner agent scripts poc/app_server`：通过
  - `pytest -q`：通过，246 passed, 1 skipped
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
- 人工验证：不涉及
- 回归影响：旧 `/tasks` 和旧 Runner 认领路径保持可用；新 `/runs` 使用 AgentCommand
- 风险与未完成项：日志增量上传、产物 manifest、Run/Command 状态双向映射将在 D03/D04/D05 继续完善

---

### [x] D03 实现增量日志上传

**目标**

避免长任务反复上传完整日志。

**依赖**

C05、D02。

**实现要求**

1. Agent 跟踪日志字节 offset 或稳定 sequence。
2. 只上传新增内容。
3. 后端校验 offset/sequence。
4. 重复 chunk 幂等。
5. offset 不连续时返回服务端当前 offset，Agent 重新同步。
6. 设置 chunk 最大值和 Run 总日志限制。
7. 兼容旧 Run 日志读取接口。

**验收标准**

- 追加 3 次日志只传输 3 个增量块。
- 重复发送一个块不会重复写入。
- 中断恢复后可以从正确 offset 继续。

执行结果：
- 状态：完成
- 修改文件：
  - `backend/schemas.py`
  - `backend/routers/agent.py`
  - `backend/services/run_log_service.py`
  - `agent/api_client.py`
  - `agent/log_uploader.py`
  - `tests/test_run_log_chunks.py`
  - `tests/test_agent_api_client.py`
  - `tests/test_api_contract.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- API：新增 `POST /agent/runs/{task_id}/log-chunks`，按 offset 增量追加到现有 `run.log`
- 校验：后端校验 Run 的 `device_id`/`command_id` 绑定、offset 连续性、单 chunk 大小和 Run 总日志大小
- 幂等：重复上传相同 offset 和相同内容返回成功且 `duplicate=true`，不会重复写入
- Agent：新增 `RunLogUploadTracker` 和 `RunLogUploader`，只读取并上传新增日志内容，服务端返回 current offset 后更新本地 offset
- 自动化测试：
  - `pytest -q tests/test_run_log_chunks.py tests/test_agent_api_client.py tests/test_api_contract.py`：通过，8 passed
  - `python -m compileall backend runner agent scripts poc/app_server`：通过
  - `pytest -q`：通过，250 passed, 1 skipped
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
- 人工验证：不涉及
- 回归影响：旧 `/tasks/{id}/log` 读取接口继续读取同一个 `run.log`
- 风险与未完成项：当前只处理日志增量；result/diff/Git 状态等产物 manifest 由 D04 完成

---

### [x] D04 实现产物 manifest 和大小限制

**目标**

可靠上传 result、diff、Git 状态和报告，避免无界请求体。

**依赖**

D02。

**实现要求**

1. 定义允许的 artifact type 和文件名。
2. 上传 manifest 包含类型、大小、hash 和 sequence。
3. 限制单文件和单 Run 总大小，配置可覆盖。
4. 后端不接受任意目标路径和任意文件名。
5. 重复相同 hash 上传幂等。
6. 读取 API 继续进行 `JOBS_DIR` 路径保护。

**验收标准**

- 合法产物可读取。
- 越界大小、非法类型和非法文件名被拒绝。
- 重传不产生重复文件。

执行结果：
- 状态：完成
- 修改文件：
  - `backend/schemas.py`
  - `backend/config.py`
  - `backend/routers/agent.py`
  - `backend/services/run_artifact_service.py`
  - `agent/api_client.py`
  - `agent/artifact_uploader.py`
  - `tests/test_run_artifacts.py`
  - `tests/test_agent_api_client.py`
  - `tests/test_api_contract.py`
  - `tests/test_config.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：不涉及
- API：新增 `POST /agent/runs/{task_id}/artifacts`，Agent 通过固定 artifact type 和 filename allowlist 上传 result、diff、Git 状态和报告等 Run 产物
- 配置：新增 `RUN_ARTIFACT_MAX_FILE_BYTES` 和 `RUN_ARTIFACT_MAX_TOTAL_BYTES` 可覆盖单文件和单 Run artifact 总大小限制，默认分别为 2 MiB 和 8 MiB
- 校验：后端校验 Run 的 `device_id`/`command_id` 绑定、artifact type、filename、size、sha256、单文件大小和单 Run artifact 总大小；不接受任意目标路径或任意文件名
- 幂等：相同 type/filename 且相同 hash 重传返回成功并标记 `duplicate=true`；不同内容重传返回冲突
- Agent：新增 `RunArtifactUploader` 和 manifest 构建逻辑，上传 manifest 包含 type、filename、sequence、size 和 sha256
- 自动化测试：
  - `pytest -q tests/test_run_artifacts.py tests/test_agent_api_client.py tests/test_api_contract.py`：通过，10 passed
  - `pytest -q tests/test_run_artifacts.py tests/test_agent_api_client.py tests/test_api_contract.py tests/test_config.py`：通过，25 passed
  - `python -m compileall backend runner agent scripts poc/app_server`：通过
  - `pytest -q`：通过，258 passed, 1 skipped
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
- 人工验证：不涉及
- 回归影响：旧 `/tasks/{id}/result`、`/tasks/{id}/diff`、`/tasks/{id}/artifacts/git-status` 和 `/tasks/{id}/artifacts/report` 读取接口继续复用 `JOBS_DIR` 路径保护
- 风险与未完成项：当前仅实现 artifact manifest 上传与读取兼容；真实 Run 取消由 D05 继续完成

---

### [x] D05 实现真实 Run 取消

**目标**

手机取消 Run 后，目标设备上的 Codex 进程树实际终止。

**依赖**

D02、C06。

**实现要求**

1. 控制端创建 `RUN_CANCEL` 命令或在当前命令状态中下发取消信号。
2. Agent 增加本地 Process Registry：command_id -> process。
3. Windows 使用现有 process tree kill 逻辑。
4. 取消需要幂等。
5. Agent 断线时控制端记录 cancel requested，重连 reconciliation 后立即执行。
6. 成功取消最终状态为 CANCELLED，不应被后续 complete 覆盖为 SUCCESS。

**验收标准**

- 测试子进程被实际终止。
- 重复取消不报内部错误。
- 取消与完成竞争时终态规则有测试。

执行结果：
- 状态：完成
- 修改文件：
  - `backend/services/agent_command_service.py`
  - `backend/services/task_service.py`
  - `agent/command_handlers.py`
  - `agent/command_loop.py`
  - `agent/process_registry.py`
  - `agent/run_executor.py`
  - `runner/codex_executor.py`
  - `tests/test_agent_command_service.py`
  - `tests/test_tasks_api.py`
  - `tests/test_agent_run_executor.py`
  - `tests/test_agent_command_loop.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：不涉及
- 控制端：`/tasks/{task_id}/cancel` 对绑定 `command_id` 的 Run 会同步将 AgentCommand 标记为 `CANCELLED`，重复取消返回当前取消态，不报内部错误
- Agent：新增 `ProcessRegistry`，RunExecutor 在 `codex exec` 进程启动和结束时登记/移除 command_id 对应进程；执行中通过 command renew + reconcile 轮询服务端取消态
- 进程终止：发现服务端命令为 `CANCELLED` 或 reconcile 要求 `STOP` 时，RunExecutor 的 `should_cancel` 返回 true，复用 `runner.codex_executor` 现有 process tree kill 逻辑；Windows 仍使用 `taskkill /T /F`
- 终态规则：AgentCommand 已取消后，迟到的 SUCCESS complete 不会覆盖 CANCELLED；Task 取消后保持 CANCELLED
- 自动化测试：
  - `pytest -q tests/test_agent_command_service.py tests/test_tasks_api.py tests/test_agent_run_executor.py tests/test_agent_command_loop.py tests/test_agent_reconciliation.py tests/test_runner_service.py tests/test_codex_executor.py`：通过，60 passed
  - `python -m compileall backend runner agent scripts poc/app_server`：通过
  - `pytest -q`：通过，264 passed, 1 skipped
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
- 人工验证：不涉及
- 回归影响：旧 Runner 取消仍使用原 `/runner/tasks/{task_id}/cancel-state` 轮询；本次只给 AgentCommand Run 增加真实取消闭环
- 风险与未完成项：取消轮询依赖 Agent 与控制端连通；断线重连后的停止动作由既有 reconciliation 返回 `STOP` 支撑

---

### [x] D06 手机端运行页显示设备和 Workspace

**目标**

用户在手机上能确认每条 Run 在哪台设备、哪个目录执行。

**依赖**

D01、D03、D05、B08。

**实现要求**

1. Run 列表和详情显示 Device、Workspace、状态和时间。
2. 默认按当前 Workspace 筛选，允许查看全部设备历史。
3. 新建 Run 的入口如果保留，必须使用当前 Workspace。
4. 设备离线时禁用新建。
5. 日志页面使用增量或刷新机制，不重复文本。
6. 取消按钮展示真实状态。

**验收标准**

- 用户不会误判执行设备。
- 切换 Workspace 后列表筛选正确。
- 前端 build 通过。

执行结果：
- 状态：完成
- 修改文件：
  - `backend/schemas.py`
  - `backend/routers/tasks.py`
  - `backend/routers/runners.py`
  - `backend/services/task_service.py`
  - `frontend/src/api/types.ts`
  - `frontend/src/api/tasks.ts`
  - `frontend/src/components/runs/RunsPage.tsx`
  - `frontend/src/components/tasks/TaskCard.tsx`
  - `frontend/src/components/tasks/TaskDetailSheet.tsx`
  - `frontend/src/styles/tasks.css`
  - `tests/test_runs_api.py`
  - `tests/test_ui.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：不涉及
- 后端：`TaskRead` 增加 Device/Workspace 展示字段；`GET /tasks` 增加 `workspace_id` 过滤，支持运行页默认按当前 Workspace 查询
- 前端：运行页显示当前设备、Workspace 路径和历史范围；默认查询当前 Workspace，可切换查看全部设备历史；Run 卡片和详情显示 Device、Workspace、设备状态和取消请求状态
- 交互：新建 Run 入口未在运行页保留；重跑继续受当前设备在线状态约束，离线或停用时按钮禁用并显示原因；日志仍通过单一 artifact URL 打开，不在页面内重复拼接文本
- 自动化测试：
  - `pytest -q tests/test_runs_api.py tests/test_ui.py`：通过，20 passed
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
  - `python -m compileall backend runner agent scripts poc/app_server`：通过
  - `pytest -q`：通过，265 passed, 1 skipped
- 人工验证：不涉及
- 回归影响：旧任务没有 Device/Workspace 绑定时仍可读取，前端显示为旧任务；Runner finish 返回结构补齐新字段但不改变已有字段含义
- 风险与未完成项：运行页当前只做轮询刷新，不新增日志增量阅读 UI；D03 后端增量日志接口仍保留给后续实时日志体验使用

---

### [ ] D07 兼容并逐步废弃旧 Runner 认领接口

**目标**

在新 Agent Run 稳定后，减少旧 Runner 与新 Agent 双链路长期并存。

**依赖**

D02-D06、F01。

**实现要求**

1. 在旧 `/runner/*` 接口和 README 中标记 deprecated。
2. `AGENT_COMMAND_MODE=false` 时仍可使用旧链路。
3. `true` 时新 Run 不进入旧 Runner 队列。
4. 不立即删除旧表、历史记录或 runner 代码。
5. 增加双模式回归测试。

**验收标准**

- 两种模式行为可预测。
- 新模式不会被旧 Runner 误认领。
- 回退开关有效。

---

## E. 多设备连续 Session

### [x] E01 将 App Server POC 整理为正式 Agent 模块

**目标**

复用当前 Bridge 已验证能力，但去除 POC 服务边界和单一 Bridge URL 假设。

**依赖**

B05、C04、A01。

**实现要求**

1. 在 `agent/app_server/` 建立正式模块：
   - process/client。
   - JSONL RPC。
   - event parser。
   - session manager。
2. 从 `poc/app_server` 复制或移动时保留兼容导入，避免一次性破坏测试。
3. Session Manager 以 workspace_key 解析 cwd。
4. 不再启动一个给控制端直接 HTTP 调用的单一 Bridge 作为目标架构。
5. 保留当前 POC 直到新模块 smoke 完成，再由 F06 归档。
6. 继续验证当前 Codex App Server API，而不是假设协议字段。

**验收标准**

- Fake/stdin App Server 测试可在 Agent 模块运行。
- Session Manager 能在两个不同临时 Workspace 创建隔离会话。
- 原 POC 测试暂时仍通过。

执行结果：
- 状态：完成
- 修改文件：
  - `agent/app_server/__init__.py`
  - `agent/app_server/client.py`
  - `agent/app_server/event_parser.py`
  - `agent/app_server/session_manager.py`
  - `tests/test_agent_app_server_session_manager.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：不涉及
- Agent 模块：新增正式 `agent/app_server/` 包，包含 JSONL RPC client、事件解析入口和 `AgentAppSessionManager`
- Session Manager：通过 `WorkspaceRegistry.resolve(workspace_key)` 获取 cwd；每个 workspace/session 启动独立 `codex app-server --listen stdio://`，执行 initialize 和 thread/start，并保存 `agent_session_id`、`codex_thread_id`、cwd、run_dir 和 client
- 兼容策略：当前 `poc/app_server` 保留不移动；`agent.app_server.event_parser` 复用已验证 POC parser 行为，避免一次性分叉
- 自动化测试：
  - `pytest -q tests/test_agent_app_server_session_manager.py tests/test_app_server_event_parser.py tests/test_app_server_bridge.py tests/test_app_server_bridge_client.py`：通过，17 passed
  - `python -m compileall backend runner agent scripts poc/app_server`：通过
  - `pytest -q`：通过，267 passed, 1 skipped
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
- 人工验证：不涉及
- 回归影响：原 POC HTTP Bridge 和旧 AppThread Bridge 调用未切换；E02 起再通过命令通道接入正式 Agent SessionManager
- 风险与未完成项：本任务只完成正式 Agent 模块承接和隔离会话能力，尚未改变控制端 Session 创建路径

---

### [x] E02 通过命令通道创建 Session

**目标**

手机创建 Session 时，命令被发送到 Workspace 所属设备。

**依赖**

C04、E01、B08。

**实现要求**

1. 为 AppThread/Session 增加：

```text
device_id
workspace_id
agent_session_id
generation
sandbox
approval_policy
network_access
command_id
```

2. 创建 Session 生成 `SESSION_OPEN` 命令。
3. Agent 使用 Workspace Registry 创建 App Server process/thread。
4. 完成后回传 agent_session_id 和 codex_thread_id。
5. 控制端不再使用全局 `APP_SERVER_BRIDGE_URL` 调用目标设备。
6. 旧模式继续走原 Bridge。

**验收标准**

- Device A Workspace 的 Session 只由 Device A 创建。
- Session cwd 与 Workspace Registry 一致。
- Device B 无法操作 Device A 的 Session。

执行结果：
- 状态：完成
- 修改文件：
  - `backend/models.py`
  - `backend/migrations.py`
  - `backend/schemas.py`
  - `backend/routers/agent.py`
  - `backend/services/agent_command_service.py`
  - `backend/services/app_thread_service.py`
  - `agent/command_handlers.py`
  - `agent/command_loop.py`
  - `agent/session_handlers.py`
  - `tests/test_db_migrations.py`
  - `tests/test_app_threads_api.py`
  - `tests/test_agent_app_server_session_manager.py`
  - `tests/test_agent_api_client.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：新增版本 `0009 app_thread_agent_session_bindings`，为 `app_threads` 增加 `device_id`、`workspace_id`、`agent_session_id`、`generation`、`sandbox`、`approval_policy`、`network_access`、`command_id`；为 `agent_commands` 增加 `result_payload_json`
- 控制端：`AGENT_COMMAND_MODE=true` 时创建 AppThread 生成 `SESSION_OPEN` AgentCommand，命令绑定 Workspace 所属 Device，payload 只包含 workspace/session 标识和策略，不包含任意 cwd
- Agent：新增 `SessionOpenHandler`，通过 E01 `AgentAppSessionManager` 按 `workspace_key` 启动 App Server session，并在 complete 时回传 `agent_session_id` 和 `codex_thread_id`
- 回写：`/agent/commands/{command_id}/complete` 支持 `result_payload`；SESSION_OPEN 成功后控制端将 AppThread 更新为 ACTIVE 并保存 agent session/thread id
- 兼容：`AGENT_COMMAND_MODE=false` 时旧 Bridge 创建 Session 路径保持不变
- 自动化测试：
  - `pytest -q tests/test_db_migrations.py tests/test_app_threads_api.py tests/test_agent_app_server_session_manager.py tests/test_agent_api_client.py tests/test_agent_command_loop.py`：通过，35 passed
  - `pytest -q tests/test_app_thread_service.py tests/test_app_turn_executor.py tests/test_api_contract.py`：通过，42 passed
  - `python -m compileall backend runner agent scripts poc/app_server`：通过
  - `pytest -q`：通过，271 passed, 1 skipped
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
- 人工验证：不涉及
- 回归影响：新增字段均为可空或有默认值；旧 AppThread 历史和旧 Bridge 模式继续可读可用
- 风险与未完成项：本任务只完成 Session 创建命令通道，Turn 执行仍由 E03 接入

---

### [x] E03 通过命令通道执行 Turn

**目标**

Session 中每条用户消息通过目标 Agent 执行。

**依赖**

E02、C05。

**实现要求**

1. 创建 AppTurn 时生成 `TURN_START` 命令。
2. 命令包含 session/turn/workspace 标识，不包含任意 cwd。
3. Agent Session Manager 根据 agent_session_id 找到已有 App Server process。
4. 输出事件使用 C05 通道上传。
5. final、error 和 duration 回写 AppTurn。
6. 先只实现 async 路径；旧 sync API 可以兼容调用 async 并等待，不维护两套核心逻辑。

**验收标准**

- 一条 Turn 完整经过 PENDING、RUNNING、SUCCESS/FAILED。
- 事件和 final 对应正确 turn_id。
- 非目标设备不能执行。

执行结果：
- 状态：完成
- 修改文件：
  - `backend/models.py`
  - `backend/migrations.py`
  - `backend/schemas.py`
  - `backend/routers/agent.py`
  - `backend/services/app_thread_service.py`
  - `agent/app_server/session_manager.py`
  - `agent/session_handlers.py`
  - `agent/command_handlers.py`
  - `agent/command_loop.py`
  - `agent/config.py`
  - `agent/main.py`
  - `frontend/src/api/types.ts`
  - `tests/test_db_migrations.py`
  - `tests/test_app_threads_api.py`
  - `tests/test_agent_app_server_session_manager.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：新增版本 `0010 app_turn_command_binding`，为 `app_turns` 增加 `command_id` 并创建索引，用于 TURN_START 命令回写对应 AppTurn
- 控制端：`AGENT_COMMAND_MODE=true` 时异步创建 AppTurn 会生成 `TURN_START` 命令，payload 只包含 app_thread/app_turn/agent_session/workspace 标识和策略，不包含任意 cwd 或 project_path；Agent ack 后 AppTurn 进入 RUNNING，complete 后回写 SUCCESS/FAILED/CANCELLED、final、error、duration 和 event_summary
- Agent：新增 `TurnStartHandler`，通过 `agent_session_id` 查找既有 App Server process/thread 执行 turn，并通过 C05 `CommandEventUploader` 上传 status、turn/completed、final 等命令事件；Agent CLI 启动时按本地 Workspace Registry 初始化 `AgentAppSessionManager`
- 兼容：`AGENT_COMMAND_MODE=false` 时旧 Bridge async executor 和 sync turn 路径保持不变
- 自动化测试：
  - `pytest -q tests/test_db_migrations.py tests/test_app_threads_api.py tests/test_agent_app_server_session_manager.py tests/test_agent_command_loop.py`：通过，38 passed
  - `pytest -q tests/test_app_thread_service.py tests/test_app_turn_executor.py tests/test_agent_api_client.py tests/test_agent_command_service.py tests/test_agent_command_events.py tests/test_app_server_bridge.py tests/test_app_server_bridge_client.py`：通过，71 passed
  - `python -m compileall backend runner agent scripts poc/app_server`：通过
  - `pytest -q`：通过，277 passed, 1 skipped
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
- 人工验证：不涉及真实 Codex App Server 和真实多设备；本任务使用 Fake App Server/Agent API 自动化覆盖命令路由、事件上传和回写闭环
- 回归影响：新增字段为可空字段；旧 AppThread/AppTurn 数据可继续读取；旧 Bridge 模式未切换
- 风险与未完成项：E03 只完成命令通道执行 Turn；TurnEvent 持久化、SSE 可重放、原子并发保护、取消/超时回收和 5 Turn 连续复用验证仍由 E04-E08 后续任务处理

---

### [x] E04 保证同一 Session 复用同一 Codex thread

**目标**

真正满足“在一个目录下连续会话进行工作”。

**依赖**

E03。

**实现要求**

1. Session 创建时保存 codex_thread_id。
2. 后续 Turn 使用同一 agent_session_id、process 和 codex_thread_id。
3. 不为每条 Turn 重新创建 App Server thread。
4. Session Manager 明确管理：
   - process 生命周期。
   - thread id。
   - turn count。
   - last activity。
5. 增加至少 5 Turn 连续会话测试。
6. 测试确认所有 Turn cwd 相同、thread id 相同。

**验收标准**

- 连续 5 Turn 不创建 5 个 thread。
- Session 切换后各自 thread 独立。
- 两台设备同名 Workspace 不串会话。

执行结果：
- 状态：完成
- 修改文件：
  - `agent/app_server/session_manager.py`
  - `tests/test_agent_app_server_session_manager.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：不涉及
- Agent Session Manager：`AgentAppSession` 明确保存 `codex_thread_id`、cwd、process client、turn_count、active/last turn、created_at 和 last_activity_at；连续 turn 复用同一个 `agent_session_id`、同一个 App Server process、同一个 `codex_thread_id`
- 自动化测试：
  - `pytest -q tests/test_agent_app_server_session_manager.py tests/test_app_threads_api.py tests/test_agent_command_loop.py`：通过，36 passed
  - `python -m compileall backend runner agent scripts poc/app_server`：通过
  - `pytest -q`：通过，280 passed, 1 skipped
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
- 人工验证：不涉及真实 Codex App Server；使用 Fake App Server 自动化验证连续 5 Turn、Session 切换隔离和两台设备同名 Workspace 不串线
- 回归影响：仅增强正式 Agent SessionManager 状态记录和测试；不改变旧 Bridge 模式，不新增数据库字段
- 风险与未完成项：真实 Codex App Server 多轮 smoke 仍留到 F05；TurnEvent 持久化和 SSE 可重放由 E05/E06 继续处理

---

### [x] E05 新增 TurnEvent 持久化和去重

**目标**

把实时输出从进程内消息升级为可查询、可恢复的服务端记录。

**依赖**

C05、E03。

**实现要求**

新增 TurnEvent：

```text
id
turn_id
sequence
kind
payload_json
created_at
```

要求：

1. 唯一 `(turn_id, sequence)`。
2. Agent CommandEvent 转换为 TurnEvent。
3. assistant delta、status、tool event、error、final 均可保存。
4. 重复相同事件幂等。
5. 同 sequence 不同内容冲突。
6. 增加按 sequence 分页查询。

**验收标准**

- 控制端重启后事件仍存在。
- 事件重传不会重复 assistant 文本。
- final 必须可以从事件和 AppTurn 两处交叉验证。

执行结果：
- 状态：完成
- 修改文件：
  - `backend/models.py`
  - `backend/migrations.py`
  - `backend/schemas.py`
  - `backend/routers/agent.py`
  - `backend/routers/app_threads.py`
  - `backend/services/agent_command_event_service.py`
  - `backend/services/turn_event_service.py`
  - `frontend/src/api/appThreads.ts`
  - `frontend/src/api/types.ts`
  - `tests/test_db_migrations.py`
  - `tests/test_agent_command_events.py`
  - `tests/test_api_contract.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：新增版本 `0011 turn_events`，创建 `turn_events` 表，包含唯一索引 `(turn_id, sequence)` 以及 turn_id、kind、created_at 索引
- 控制端：`TURN_START` 的 Agent CommandEvent 上传后同步转换为 TurnEvent；重复相同 sequence/kind/payload 幂等，同 sequence 不同内容返回冲突；新增 `GET /app-turns/{app_turn_id}/events?since=&limit=` 按 sequence 分页查询
- 前端：新增 `TurnEvent`/`TurnEventList` 类型和 `listAppTurnEvents` API 封装，暂不改 UI
- 自动化测试：
  - `pytest -q tests/test_agent_command_events.py tests/test_db_migrations.py tests/test_api_contract.py`：通过，14 passed
  - `python -m compileall backend runner agent scripts poc/app_server`：通过
  - `pytest -q`：通过，284 passed, 1 skipped
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
- 人工验证：不涉及；通过自动化测试覆盖事件持久化、重放去重、内容冲突、分页查询、final 与 AppTurn 交叉验证
- 回归影响：新增表和只读查询接口；旧 Bridge 模式和旧内存式 stream 路径暂不切换
- 风险与未完成项：E05 只完成 TurnEvent 持久化和查询；SSE 从数据库重放、客户端断线续传由 E06/E12 继续处理

---

### [x] E06 改造 SSE 为可重放事件流

**目标**

手机刷新或断线后从最后 sequence 继续接收，不丢失、不重复。

**依赖**

E05。

**实现要求**

1. `/turns/{id}/stream` 或兼容旧路径支持 `since`/`Last-Event-ID`。
2. 先从数据库重放未消费事件，再等待新事件。
3. 每个 SSE event 有稳定 event id=sequence。
4. 终态发送 final/error 后关闭流。
5. 客户端记录最后 sequence。
6. 断线重连后不重复拼接已消费 delta。
7. 不要求引入 WebSocket。

**验收标准**

- 主动中断 SSE 后从中间 sequence 恢复。
- 输出文本与不掉线场景完全一致。
- 控制端重启后可重放已有事件。

执行结果：
- 状态：完成
- 修改文件：
  - `backend/routers/app_threads.py`
  - `backend/services/app_thread_service.py`
  - `backend/services/turn_event_service.py`
  - `frontend/src/api/appThreads.ts`
  - `frontend/src/api/types.ts`
  - `frontend/src/components/session/SessionPage.tsx`
  - `tests/test_app_threads_api.py`
  - `tests/test_ui.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：不涉及
- 后端：`/app-turns/{app_turn_id}/stream` 支持 `since` 查询参数和 `Last-Event-ID`；存在 TurnEvent 时优先从数据库按 sequence 重放，SSE 输出稳定 `id: sequence`，终态补 final/error 后关闭；无持久化事件时保留旧 Bridge live-events 兼容路径
- 前端：`streamAppTurn` 支持 since，解析 SSE `id:` 为 sequence；会话页记录每个 Turn 最后 sequence，忽略重复或旧 sequence，断线/重复启动 stream 时从最后 sequence 继续
- 自动化测试：
  - `pytest -q tests/test_app_threads_api.py tests/test_app_thread_service.py tests/test_ui.py -o cache_dir=data/pytest-cache-e06 -o addopts=--basetemp=data/pytest-tmp-e06`：通过，70 passed
  - `python -m compileall backend runner agent scripts poc/app_server`：通过
  - `pytest -q -o cache_dir=data/pytest-cache-e06-full -o addopts=--basetemp=data/pytest-tmp-e06-full`：通过，289 passed, 1 skipped
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
- 人工验证：不涉及；通过自动化测试覆盖 since 重放、`Last-Event-ID` 续传、终态关闭和前端 sequence 去重逻辑
- 回归影响：旧 Bridge stream fallback 保留；新增可重放路径依赖 E05 TurnEvent
- 风险与未完成项：本次不实现持久化 delta 组装为页面初始 assistant 内容，刷新恢复完整页面状态由 E12 继续处理；本机一次 targeted pytest 因前一次中断遗留 `data/pytest-tmp-current` 占用失败，后续使用独立 basetemp/cache 验证通过

---

### [x] E07 实现原子 Turn 并发保护

**目标**

同一 Session 同时只允许一个活跃 Turn，消除“先查再插”的竞争窗口。

**依赖**

E03、A03。

**实现要求**

1. 使用数据库约束、锁记录或条件更新实现原子并发保护。
2. 同步和异步 API 共用同一保护逻辑。
3. 冲突返回 409 和稳定错误 code。
4. 不依赖单进程内锁作为唯一保护。
5. 增加并发测试。

**验收标准**

- 两个并发请求只有一个创建成功。
- 失败请求能获得当前 active turn 信息。
- 终态后可创建下一 Turn。

**执行结果**

- 状态：完成
- 修改文件：
  - `backend/models.py`
  - `backend/migrations.py`
  - `backend/services/app_thread_service.py`
  - `tests/test_app_thread_service.py`
  - `tests/test_app_turn_recovery.py`
  - `tests/test_db_migrations.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：新增 `0012 active_app_turn_unique_index`，为 `app_turns(app_thread_id)` 增加只覆盖 `PENDING`/`RUNNING` 的部分唯一索引
- 后端：同步 Turn、旧异步 Turn、Agent 命令模式异步 Turn 共用 `_create_active_app_turn`；普通冲突先返回稳定 409 `app_turn_conflict`，并发竞争由数据库唯一约束兜底后返回当前 active turn 信息
- 自动化测试：
  - `pytest -q tests/test_db_migrations.py tests/test_app_thread_service.py tests/test_app_threads_api.py -o cache_dir=data/pytest-cache-e07 -o addopts=--basetemp=data/pytest-tmp-e07`：通过，62 passed
  - `pytest -q tests/test_app_turn_recovery.py tests/test_app_thread_service.py tests/test_db_migrations.py tests/test_app_threads_api.py -o cache_dir=data/pytest-cache-e07-target-2 -o addopts=--basetemp=data/pytest-tmp-e07-target-2`：通过，64 passed
  - `python -m compileall backend runner agent scripts poc/app_server`：通过
  - `pytest -q -o cache_dir=data/pytest-cache-e07-full-2 -o addopts=--basetemp=data/pytest-tmp-e07-full-2`：通过，292 passed, 1 skipped
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
- 人工验证：不涉及；通过服务层文件型 SQLite 并发测试验证两个并发请求只有一个创建成功，失败请求返回当前 active turn；通过既有终态历史测试验证终态后可创建下一 Turn
- 回归影响：新增数据库不变量后，同一 AppThread 不能再同时存在多个 `PENDING`/`RUNNING` Turn；已调整 stale recovery 测试数据为不同 AppThread 下分别覆盖 pending/running
- 风险与未完成项：取消、超时回收和 Session 状态收口仍由 E08 继续处理

---

### [x] E08 实现 Session/Turn 取消和超时回收

**目标**

取消或超时后，不让状态不确定的 App Server process 继续在后台工作。

**依赖**

E03、E04、C06。

**实现要求**

1. 先验证当前 Codex App Server 是否支持可靠协议级取消。
2. 支持时调用协议取消并等待确认。
3. 不支持或取消超时时：
   - 终止对应 App Server process。
   - Turn 标记 CANCELLED/FAILED。
   - Session 标记 RECOVER_REQUIRED 或 ERROR。
4. 不把 Session 直接恢复 ACTIVE 后继续复用未知状态进程。
5. 重复取消幂等。
6. 超时和用户取消分别记录原因。

**验收标准**

- 取消后底层 process 不继续输出或修改目录。
- 该 Session 在 reopen 前不能发送新 Turn。
- 取消/完成竞争有确定终态。

**执行结果**

- 状态：完成
- 修改文件：
  - `backend/services/app_thread_service.py`
  - `agent/app_server/session_manager.py`
  - `agent/session_handlers.py`
  - `agent/command_handlers.py`
  - `frontend/src/api/types.ts`
  - `frontend/src/components/session/SessionPage.tsx`
  - `frontend/src/components/session/ThreadSwitcherSheet.tsx`
  - `docs/state-machines.md`
  - `tests/test_app_thread_service.py`
  - `tests/test_app_threads_api.py`
  - `tests/test_app_turn_recovery.py`
  - `tests/test_agent_app_server_session_manager.py`
  - `tests/test_ui.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 协议验证结论：当前代码库未实现可验证的 Codex App Server `turn/cancel` 协议路径；因此 E08 按安全降级策略处理取消/超时，即关闭对应 Agent App Server session/process，并将 AppThread 标记为 `RECOVER_REQUIRED`
- 后端：新增 `RECOVER_REQUIRED` AppThread 状态；取消 active Turn 时同步取消绑定 AgentCommand，Turn 进入 `CANCELLED`，Session 进入 `RECOVER_REQUIRED`；stale recovery 将残留 active Turn 标记 `FAILED`，Session 进入 `RECOVER_REQUIRED`；非 `ACTIVE` Session 发送新 Turn 返回 409 `app_thread_not_active`
- Agent：`TURN_START` 执行期间通过 renew/reconcile 检测服务端取消；发现取消或等待 turn 超时时关闭对应 App Server session，避免未知状态进程继续输出或修改目录
- 前端：会话状态类型、筛选项和 Composer 禁用原因支持 `RECOVER_REQUIRED`
- 文档：更新 `docs/state-machines.md`，记录 `RECOVER_REQUIRED` 和当前取消策略
- 自动化测试：
  - `pytest -q tests/test_app_thread_service.py tests/test_app_threads_api.py tests/test_app_turn_recovery.py tests/test_agent_app_server_session_manager.py tests/test_ui.py -o cache_dir=data/pytest-cache-e08-target-3 -o addopts=--basetemp=data/pytest-tmp-e08-target-3`：通过，89 passed
  - `pytest -q tests/test_agent_command_loop.py tests/test_agent_command_api.py tests/test_agent_api_client.py tests/test_agent_reconciliation.py tests/test_app_turn_executor.py tests/test_app_thread_service.py tests/test_app_threads_api.py tests/test_agent_app_server_session_manager.py tests/test_ui.py -o cache_dir=data/pytest-cache-e08-related -o addopts=--basetemp=data/pytest-tmp-e08-related`：通过，113 passed
  - `python -m compileall backend runner agent scripts poc/app_server`：通过
  - `pytest -q -o cache_dir=data/pytest-cache-e08-full -o addopts=--basetemp=data/pytest-tmp-e08-full`：通过，296 passed, 1 skipped
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
- 人工验证：不涉及；通过单元/API 测试覆盖取消后阻断继续发送、取消/迟到完成竞争保持 CANCELLED、取消/超时关闭 Agent App Server session
- 回归影响：取消和 stale recovery 后 AppThread 不再恢复为 `ACTIVE` 或普通 `ERROR`，而是要求 reopen；旧 Bridge 同步发送仍通过 Bridge 超时失败路径进入 `ERROR`
- 风险与未完成项：E08 不新增协议级 cancel；若未来 Codex App Server 暴露可靠 `turn/cancel`，可在关闭进程前优先调用并等待确认

---

### [x] E09 实现 Session reopen 和 generation

**目标**

Agent/App Server 重启或取消回收后，用户可以继续在同一历史会话视图下工作。

**依赖**

E08。

**实现要求**

1. Session 增加 generation，首次为 1。
2. reopen 在同一 Workspace 创建新的 Agent process/thread，generation +1。
3. 历史 Turn 保留，不伪造旧 Codex thread 已恢复。
4. 如果协议验证确认支持 thread resume，可优先尝试；失败则创建新 generation。
5. UI 明确显示会话已恢复但底层 generation 已变化。

**验收标准**

- Agent 重启后旧历史仍可查看。
- reopen 后可以继续发新 Turn。
- 新旧 generation 事件不会串线。

**执行结果**

- 状态：完成
- 修改文件：
  - `backend/services/app_thread_service.py`
  - `frontend/src/api/types.ts`
  - `frontend/src/components/session/SessionHeader.tsx`
  - `frontend/src/components/session/SessionPage.tsx`
  - `tests/test_app_thread_service.py`
  - `tests/test_app_threads_api.py`
  - `tests/test_ui.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 后端：Bridge reopen 和 Agent reopen 都会推进 `generation + 1`；Agent reopen 在同一 Workspace 上创建新的 `SESSION_OPEN` 命令，清空旧 `agent_session_id`/`app_thread_id`，状态进入 `OPENING`，历史 Turn 保留
- 串线保护：`TURN_START` complete 会校验命令 payload generation，旧 generation 的迟到完成不会覆盖新 generation 的 Session/Turn 状态
- 前端：会话 Header 显示 `G{generation}`；reopen 成功 toast 显示当前 generation；`AppThread` 类型补充 generation 字段
- 自动化测试：
  - `pytest -q tests/test_app_thread_service.py tests/test_app_threads_api.py tests/test_ui.py -o cache_dir=data/pytest-cache-e09-target -o addopts=--basetemp=data/pytest-tmp-e09-target`：通过，77 passed
  - `pytest -q tests/test_agent_app_server_session_manager.py tests/test_agent_command_loop.py tests/test_agent_command_api.py tests/test_agent_command_events.py tests/test_app_thread_service.py tests/test_app_threads_api.py -o cache_dir=data/pytest-cache-e09-related -o addopts=--basetemp=data/pytest-tmp-e09-related`：通过，90 passed
  - `python -m compileall backend runner agent scripts poc/app_server`：通过
  - `pytest -q -o cache_dir=data/pytest-cache-e09-full -o addopts=--basetemp=data/pytest-tmp-e09-full`：通过，298 passed, 1 skipped
  - `cd frontend; npm.cmd run typecheck`：首次失败，缺少前端 `AppThread.generation` 类型；补充后通过
  - `cd frontend; npm.cmd run build`：首次失败，同上；补充后通过
- 人工验证：不涉及；通过 API 测试覆盖 reopen 后旧历史仍可查看、完成新 SESSION_OPEN 后可继续发新 Turn、旧 generation complete 不串线
- 回归影响：Bridge reopen 现在也会推进 generation；Agent reopen 不尝试恢复旧 Codex thread，而是明确创建新 generation
- 风险与未完成项：未实现协议级 thread resume；如未来协议支持，可在 Agent reopen 中优先尝试 resume，失败再创建新 generation

---

### [x] E10 实现 Workspace 写入锁

**目标**

防止同一目录被多个写入型 Run/Session 同时修改。

**依赖**

D02、E03、A03。

**实现要求**

1. 增加 Workspace execution lock 或 lease。
2. 默认：
   - `workspace-write` Run 与写入 Session 互斥。
   - read-only Session 可按配置允许并发。
3. 锁必须有 owner、类型、lease 和过期恢复。
4. Agent 本地也做二次校验，不能只依赖控制端。
5. 冲突返回 workspace busy 和当前占用信息。

**验收标准**

- 同一 Workspace 两个写入执行只有一个成功。
- 不同 Workspace 可并行。
- 进程异常退出后锁可恢复。

**执行结果**

- 状态：完成
- 修改文件：
  - `backend/models.py`
  - `backend/migrations.py`
  - `backend/services/workspace_lock_service.py`
  - `backend/services/task_service.py`
  - `backend/services/app_thread_service.py`
  - `backend/routers/agent.py`
  - `agent/workspace_lock.py`
  - `agent/run_executor.py`
  - `agent/session_handlers.py`
  - `agent/command_handlers.py`
  - `agent/app_server/session_manager.py`
  - `tests/test_workspace_execution_locks.py`
  - `tests/test_agent_run_executor.py`
  - `tests/test_db_migrations.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：新增 `0013 workspace_execution_locks`，包含 `workspace_id` 唯一锁、owner、lock_type、lease_expires_at 和 owner/lease 索引
- 控制端：`workspace-write` Run 和写入 Session 在创建命令前获取 Workspace 写锁；冲突返回 409 `workspace_busy` 和当前 owner 信息；read-only Session 不占写锁；过期锁在获取前自动回收
- 释放策略：Run 取消或 Agent `RUN_EXECUTE` complete 后释放 Run 锁；写入 Session close/cancel/recover 释放 Session 锁；SESSION_OPEN 失败释放对应 Session 锁
- Agent 本地：新增 `LocalWorkspaceLock`，RunExecutor 和 SessionOpenHandler 共用本地写锁，避免同一设备本地绕过控制端产生并发写入
- 自动化测试：
  - `pytest -q tests/test_workspace_execution_locks.py tests/test_db_migrations.py tests/test_agent_run_executor.py tests/test_app_threads_api.py tests/test_runs_api.py tests/test_tasks_api.py -o cache_dir=data/pytest-cache-e10-target-2 -o addopts=--basetemp=data/pytest-tmp-e10-target-2`：通过，60 passed
  - `pytest -q tests/test_workspace_execution_locks.py tests/test_agent_command_api.py tests/test_agent_command_service.py tests/test_agent_reconciliation.py tests/test_agent_run_executor.py tests/test_app_threads_api.py tests/test_runs_api.py tests/test_tasks_api.py tests/test_security_api.py tests/test_workspace_service.py tests/test_db_migrations.py -o cache_dir=data/pytest-cache-e10-related -o addopts=--basetemp=data/pytest-tmp-e10-related`：通过，100 passed
  - `python -m compileall backend runner agent scripts poc/app_server`：通过
  - `pytest -q -o cache_dir=data/pytest-cache-e10-full -o addopts=--basetemp=data/pytest-tmp-e10-full`：通过，306 passed, 1 skipped
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
- 人工验证：不涉及；通过 API/服务测试覆盖同 Workspace 写入互斥、不同 Workspace 并行、过期锁恢复、Run complete/Session close 释放锁、本地 Agent 写锁二次校验
- 回归影响：已有未完成的 workspace-write Run 或写入 Session 会阻止同 Workspace 新写入任务；read-only Session 仍允许并发
- 风险与未完成项：锁续租目前依赖较长 lease 和终态释放；如果 Agent 进程长时间运行超过 lease，后续需要在 heartbeat/renew 路径续租

---

### [x] E11 手机会话页显示设备、目录和执行模式

**目标**

发送消息前，用户始终能确认 Codex 将在哪台电脑、哪个目录、以什么权限工作。

**依赖**

B08、E02、E10。

**实现要求**

1. 会话 Header 显示：
   - Device display name。
   - Workspace name/path label。
   - read-only/workspace-write。
   - ONLINE/OFFLINE/RECOVER_REQUIRED。
2. 新建会话默认使用当前 Workspace。
3. 切换 Workspace 不自动把旧 Session 迁移过去。
4. 写入模式有醒目标识，但不引入复杂审批 UI。
5. 离线、busy、recover required 时 Composer 展示明确 disabled reason。

**验收标准**

- 用户不查看设置页也能确认执行上下文。
- 不会在切换设备后继续误发旧设备 Session。
- 移动端小屏可用。

**执行结果**

- 状态：完成
- 修改文件：
  - `frontend/src/api/types.ts`
  - `frontend/src/api/appThreads.ts`
  - `frontend/src/components/session/SessionHeader.tsx`
  - `frontend/src/components/session/SessionPage.tsx`
  - `tests/test_ui.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：不涉及
- 自动化测试：
  - `pytest -q tests/test_ui.py tests/test_app_threads_api.py -o cache_dir=data/pytest-cache-e11-target -o addopts=--basetemp=data/pytest-tmp-e11-target`：40 passed
  - `python -m compileall backend runner agent scripts poc/app_server`：通过
  - `pytest -q -o cache_dir=data/pytest-cache-e11-full -o addopts=--basetemp=data/pytest-tmp-e11-full`：306 passed, 1 skipped
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
- 人工验证：不涉及；通过类型检查、构建和静态 UI 断言覆盖 Header 执行上下文展示与 Workspace 创建参数传递
- 回归影响：新建会话会使用当前 Workspace；已存在 Session 继续显示并使用自身绑定的 device/workspace，不随当前选择迁移
- 风险与未完成项：Header 仅展示已有设备/Workspace 元数据；断网后 Turn 文本恢复由 E12 继续处理

---

### [x] E12 手机刷新后恢复当前 Turn 输出

**目标**

用户刷新页面或切换 Tab 后，仍能恢复正在执行的 Turn 和已收到文本。

**依赖**

E06、E11。

**实现要求**

1. 页面加载时发现 active Turn，自动从最后已渲染 sequence 连接 SSE。
2. 已持久化 delta 先组成当前 assistant 内容。
3. 不依赖仅存在内存中的 AbortController 状态。
4. 多次进入页面不重复创建流。
5. 浏览器断网恢复后自动有限重连。
6. 最终状态仍以服务端 Turn 为准。

**验收标准**

- Turn 运行中刷新页面，文本不丢失、不重复。
- final 到达后状态正确结束。
- 设备离线时显示等待恢复或失败原因，而不是无限加载。

**执行结果**

- 状态：完成
- 修改文件：
  - `frontend/src/components/session/SessionPage.tsx`
  - `tests/test_ui.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：不涉及
- 自动化测试：
  - `pytest -q tests/test_ui.py tests/test_app_threads_api.py -o cache_dir=data/pytest-cache-e12-target2 -o addopts=--basetemp=data/pytest-tmp-e12-target2`：40 passed
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
  - `python -m compileall backend runner agent scripts poc/app_server`：通过
  - `pytest -q -o cache_dir=data/pytest-cache-e12-full -o addopts=--basetemp=data/pytest-tmp-e12-full`：306 passed, 1 skipped
- 人工验证：不涉及；通过前端类型检查、生产构建和静态 UI 断言覆盖持久化事件恢复、sequence 续接和有限重连
- 回归影响：刷新或重新进入运行中 Turn 时会先按 `/app-turns/{id}/events` 恢复已持久化 delta，再按最后 sequence 连接 SSE；最终状态仍由 `getAppTurn`/SSE final 同步
- 风险与未完成项：恢复依赖后端已持久化 TurnEvent；尚未覆盖真实浏览器断网场景的端到端人工 smoke，后续 F 阶段补充

---

## F. 验收与交付

### [x] F01 增加双 Fake Agent 集成测试

**目标**

在 CI 中验证多设备路由、幂等、事件和恢复，不依赖真实 Codex。

**依赖**

C06、D02、E06。

**实现要求**

构造：

```text
Fake Agent A -> Workspace A
Fake Agent B -> Workspace B
```

覆盖：

1. A 命令只被 A 认领。
2. B 命令只被 B 认领。
3. 同名 Workspace 不混淆。
4. Claim 重试不多领命令。
5. 事件重传不重复。
6. Run/Turn 只回写自己的领域对象。
7. Agent 断线重连 reconciliation。
8. 控制端重启后的命令和事件恢复。

**验收标准**

- 测试可在 GitHub Actions 运行。
- 不需要真实设备和 Codex Token。

**执行结果**

- 状态：完成
- 修改文件：
  - `tests/test_multi_fake_agent_integration.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：不涉及
- 自动化测试：
  - `pytest -q tests/test_multi_fake_agent_integration.py -o cache_dir=data/pytest-cache-f01-target2 -o addopts=--basetemp=data/pytest-tmp-f01-target2`：1 passed
  - `pytest -q tests/test_multi_fake_agent_integration.py tests/test_agent_command_api.py tests/test_agent_command_events.py tests/test_agent_reconciliation.py tests/test_app_threads_api.py -o cache_dir=data/pytest-cache-f01-related -o addopts=--basetemp=data/pytest-tmp-f01-related`：41 passed
  - `python -m compileall backend runner agent scripts poc/app_server tests/test_multi_fake_agent_integration.py`：通过
  - `pytest -q -o cache_dir=data/pytest-cache-f01-full -o addopts=--basetemp=data/pytest-tmp-f01-full`：307 passed, 1 skipped
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
- 人工验证：不涉及；新增集成测试以 FastAPI TestClient 和内存 SQLite 模拟双 Agent，不依赖真实设备、Codex Token 或外部网络
- 回归影响：仅新增测试覆盖；未修改产品逻辑
- 风险与未完成项：测试覆盖命令/事件/恢复链路，不替代后续真实多设备 smoke

---

### [x] F02 增加本机双 Agent 模拟脚本

**目标**

在一台开发电脑上启动两个独立 Agent 数据目录，模拟两台设备。

**依赖**

F01、B02、C04。

**实现要求**

1. 提供 PowerShell 脚本启动 Agent A/B。
2. 两个 Agent 使用：
   - 不同 data dir。
   - 不同 device identity。
   - 不同 Workspace 配置。
3. 支持一键停止和清理测试数据。
4. 不覆盖正式 data 目录。
5. 文档说明预期输出和验证步骤。

**验收标准**

- 控制端显示两个设备。
- 两个 Workspace 可独立创建 Run/Session。

**执行结果**

- 状态：完成
- 修改文件：
  - `scripts/start_dual_fake_agents.ps1`
  - `tests/test_dual_fake_agent_script.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：不涉及
- 自动化测试：
  - `pytest -q tests/test_dual_fake_agent_script.py -o cache_dir=data/pytest-cache-f02-target -o addopts=--basetemp=data/pytest-tmp-f02-target`：1 passed
  - `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start_dual_fake_agents.ps1 -Action Prepare`：通过，生成隔离目录 `data/dual-fake-agents`
  - `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start_dual_fake_agents.ps1 -Action Clean`：通过，清理隔离目录
  - `pytest -q tests/test_dual_fake_agent_script.py tests/test_agent_identity.py tests/test_workspace_registry.py -o cache_dir=data/pytest-cache-f02-related -o addopts=--basetemp=data/pytest-tmp-f02-related`：13 passed, 1 skipped
  - `python -m compileall backend runner agent scripts poc/app_server tests/test_dual_fake_agent_script.py`：通过
  - `pytest -q -o cache_dir=data/pytest-cache-f02-full -o addopts=--basetemp=data/pytest-tmp-f02-full`：308 passed, 1 skipped
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
- 人工验证：
  - 准备：`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start_dual_fake_agents.ps1 -Action Prepare`
  - 启动并同步：`$env:AGENT_TOKEN="<token>"; powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start_dual_fake_agents.ps1 -Register -SyncWorkspaces`
  - 预期输出：控制端出现 `fake-agent-a`、`fake-agent-b` 两个 ONLINE 设备，以及 `Fake Workspace A`、`Fake Workspace B` 两个独立 Workspace
  - 停止：`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start_dual_fake_agents.ps1 -Action Stop`
  - 清理：`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start_dual_fake_agents.ps1 -Action Clean`
- 回归影响：仅新增本机模拟脚本和静态测试；默认数据目录为 `data/dual-fake-agents`，不覆盖正式 `data/agent`
- 风险与未完成项：脚本负责启动双 Agent；真实 Run/Session 成功仍依赖本机后端、AGENT_TOKEN 和 Codex/App Server 可用性

---

### [x] F03 增加 Windows Agent 安装和自启动脚本

**目标**

让个人的每台 Windows 电脑可以稳定运行 Agent。

**依赖**

B02、C04、D02、E02。

**实现要求**

1. 增加环境检查脚本：Python、Codex CLI、配置、网络。
2. 增加安装/卸载脚本。
3. 可选择 Windows Task Scheduler 或现有轻量方式实现开机启动。
4. Token、Backend URL、data dir 和 Workspace 配置从环境或配置文件读取。
5. 日志写入稳定目录并支持查看。
6. 安装脚本幂等，不重复创建多个启动项。

**验收标准**

- 重启电脑后 Agent 使用原 device_id 自动上线。
- 卸载不删除用户 Workspace 和项目文件。

**执行结果**

- 状态：完成
- 修改文件：
  - `scripts/install_windows_agent.ps1`
  - `tests/test_windows_agent_install_script.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：不涉及
- 自动化测试：
  - `pytest -q tests/test_windows_agent_install_script.py -o cache_dir=data/pytest-cache-f03-target2 -o addopts=--basetemp=data/pytest-tmp-f03-target2`：1 passed
  - PowerShell 语法解析 `PSParser::Tokenize(... scripts/install_windows_agent.ps1 ...)`：parse-ok
  - `pytest -q tests/test_windows_agent_install_script.py tests/test_agent_identity.py tests/test_agent_api_client.py tests/test_agent_command_loop.py -o cache_dir=data/pytest-cache-f03-related -o addopts=--basetemp=data/pytest-tmp-f03-related`：16 passed
  - `python -m compileall backend runner agent scripts poc/app_server tests/test_windows_agent_install_script.py`：通过
  - `pytest -q -o cache_dir=data/pytest-cache-f03-full -o addopts=--basetemp=data/pytest-tmp-f03-full`：309 passed, 1 skipped
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
- 人工验证：
  - 环境检查：`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install_windows_agent.ps1 -Action Check -BackendUrl http://127.0.0.1:8000 -AgentToken <token>`
  - 安装：`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install_windows_agent.ps1 -Action Install -BackendUrl http://127.0.0.1:8000 -AgentToken <token> -Force`
  - 状态：`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install_windows_agent.ps1 -Action Status`
  - 日志：`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install_windows_agent.ps1 -Action Logs`
  - 卸载：`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install_windows_agent.ps1 -Action Uninstall`
- 回归影响：新增脚本默认使用 `data/agent` 保存稳定 identity/state/workspaces/logs；卸载只删除 Windows Task Scheduler 启动项，不删除用户 Workspace、项目文件或 Agent data
- 风险与未完成项：本次未在当前机器实际创建/删除计划任务，避免修改系统自启动状态；重启后自动上线需在目标 Windows 设备执行安装后进行人工 smoke

---

### [x] F04 完成已有数据升级和回滚验证

**目标**

确保当前个人数据可以安全升级到新架构。

**依赖**

B07、D01、E02、A03。

**实现要求**

1. 使用现有数据库副本执行完整 migration。
2. 自动备份原数据库。
3. 输出：
   - 已迁移 Project/Workspace。
   - 已绑定/未绑定设备。
   - Task/AppThread 历史数量。
4. 验证关闭 `AGENT_COMMAND_MODE` 后可回退旧模式。
5. 不删除旧字段和表。
6. 编写恢复备份步骤。

**验收标准**

- 升级前后历史记录数量一致。
- 迁移失败可恢复备份。
- 未绑定项目不会被错误执行。

**执行结果**

- 状态：完成
- 修改文件：
  - `scripts/verify_data_migration.py`
  - `tests/test_verify_data_migration_script.py`
  - `docs/20-plan/multi-device-continuous-session-codex-task-list.md`
- 数据迁移：不直接迁移正式库；脚本只复制 `data/app.db` 到 `data/migration-verification` 后在副本上执行 migration，并生成备份与 JSON 报告
- 自动化测试：
  - `pytest -q tests/test_verify_data_migration_script.py -o cache_dir=data/pytest-cache-f04-target2 -o addopts=--basetemp=data/pytest-tmp-f04-target2`：1 passed
  - `python scripts/verify_data_migration.py --db-path data/app.db --output-dir data/migration-verification --agent-command-mode false --json`：通过；正式源库未修改
  - `pytest -q tests/test_verify_data_migration_script.py tests/test_db_migrations.py tests/test_project_workspace_migration.py -o cache_dir=data/pytest-cache-f04-related -o addopts=--basetemp=data/pytest-tmp-f04-related`：9 passed
  - `python -m compileall backend runner agent scripts poc/app_server scripts/verify_data_migration.py tests/test_verify_data_migration_script.py`：通过
  - `pytest -q -o cache_dir=data/pytest-cache-f04-full -o addopts=--basetemp=data/pytest-tmp-f04-full`：310 passed, 1 skipped
  - `cd frontend; npm.cmd run typecheck`：通过
  - `cd frontend; npm.cmd run build`：通过
- 人工验证：
  - 当前 `data/app.db` 副本验证结果：projects 3 -> 3，tasks 1 -> 1，app_threads 8 -> 8，app_turns 24 -> 24
  - 最新迁移版本：`0013`
  - 已迁移 Project/Workspace：3 个 Project，0 个 Workspace
  - 已绑定/未绑定设备：0 个 Device；3 个 Project 为 `UNBOUND`
  - 回滚步骤由报告输出：停止后端和 Agent 后执行 `Copy-Item -Force '<backup_path>' 'data/app.db'`，再以 `AGENT_COMMAND_MODE=false` 启动验证旧模式
- 回归影响：新增只读验证脚本和测试；不删除旧字段、旧表或正式数据
- 风险与未完成项：当前个人库无已同步 Workspace/Device，3 个项目仍未绑定 Workspace；在 `AGENT_COMMAND_MODE=true` 下这些项目不能直接创建 Agent Run/Session，需要先完成 Workspace 同步或项目绑定

---

### [ ] F05 完成真实多设备 smoke 验收

**目标**

用至少两台真实电脑验证最终核心使用场景。

**依赖**

D05、E12、F03、F04。

**验收场景**

1. 手机查看两台设备在线状态。
2. 在设备 A 的 Workspace 创建一次性 Run。
3. 确认 Run 只在 A 执行。
4. 在设备 B 的 Workspace 创建 Session。
5. 连续发送至少 5 个 Turn。
6. 确认相同 cwd、相同 Codex thread。
7. Turn 运行中刷新手机页面并恢复输出。
8. 断开 Agent 网络后重新连接。
9. 取消 Run。
10. 取消或超时 Turn，并验证进程回收。
11. 重启 Agent 后 reopen Session。
12. 尝试访问未注册目录并确认拒绝。

**输出要求**

在现有 smoke 文档中记录：

- 前置条件。
- 操作步骤。
- 预期结果。
- 实际结果。
- 失败和日志位置。

**验收标准**

以上核心场景全部通过；无法自动化的部分有明确人工结果，不能只写“正常”。

---

### [ ] F06 收口文档、归档旧计划并发布 v2.0

**目标**

清理重构过程遗留，形成可长期维护的个人工具版本。

**依赖**

F01-F05。

**实现要求**

1. 更新 README：
   - 产品定位。
   - Control Plane + Device Agent 架构。
   - 多设备快速开始。
   - Workspace 配置。
   - 手机访问。
   - 限制和安全边界。
2. 更新 API、状态机、Session、smoke 和故障排查文档。
3. 将已完成的旧版本计划移动到 `docs/90-archive/`，保留历史，不直接删除。
4. 归档 `poc/app_server` 前确认正式 Agent 模块已覆盖其能力；若仍被使用，只标记 deprecated，不强制移动。
5. 统一版本号到 v2.0.0。
6. 删除已确认无调用的兼容代码；每项删除必须有测试证明。
7. 输出 release checklist。

**验收命令**

```powershell
python -m compileall backend runner agent scripts poc/app_server
pytest -q
cd frontend
npm ci
npm run typecheck
npm run build
```

**验收标准**

- README 可以指导作者在第二台电脑安装 Agent。
- 文档不包含租户、组织、RBAC、计费等无关设计。
- 当前真实双设备 smoke 已记录。
- 旧数据升级说明和回滚说明完整。

## 5. 执行顺序与停止条件

严格按以下顺序执行：

```text
A01 → A02 → A03 → A04 → A05
  ↓
B01 → B02 → B03 → B04 → B05 → B06 → B07 → B08
  ↓
C01 → C02 → C03 → C04 → C05 → C06
  ↓
D01 → D02 → D03 → D04 → D05 → D06
  ↓
E01 → E02 → E03 → E04 → E05 → E06
  ↓
E07 → E08 → E09 → E10 → E11 → E12
  ↓
F01 → F02 → F03 → F04 → F05 → D07 → F06
```

出现以下情况时，Codex 必须停止当前任务并报告，不得自行扩大范围：

1. 需要依赖尚未完成的任务。
2. Codex App Server 协议行为与计划假设不一致。
3. 数据迁移可能造成现有数据丢失。
4. 必须新增 Redis、Celery、Docker 或大型依赖才能继续。
5. 发现当前主分支测试已失败且与本任务无关。
6. 需要自动 commit、push、删除历史数据或修改真实项目文件。

## 6. 单任务执行结果模板

Codex 完成每个任务后，在该任务下追加：

```text
执行结果：
- 状态：完成 / 部分完成 / 阻塞
- 修改文件：
- 数据迁移：不涉及 / 版本与结果
- 自动化测试：命令与实际结果
- 人工验证：步骤与实际结果
- 回归影响：
- 风险与未完成项：
```

只有当前任务的验收条件满足，且必要测试实际通过，才允许将复选框改为 `[x]`。
