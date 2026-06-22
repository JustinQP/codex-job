# Codex Remote Runner 多设备连续会话开发路线图

> 状态：执行规划  
> 基线：`main`，截至 2026-06-22  
> 目标版本：v2.0.0  
> 适用范围：单用户、多个可信设备、多个设备本地工作目录、手机端统一控制

## 1. 产品目标

本路线图围绕以下三个核心预期展开：

1. 用户可以在手机端控制电脑上的 Codex 执行任务。
2. 用户可以管理多台电脑，每个项目或工作目录可以位于不同电脑。
3. 用户可以在选定电脑的指定目录中创建连续会话，并在同一上下文中持续工作。

最终产品应形成以下体验：

```text
手机浏览器
  ↓
选择设备
  ↓
选择该设备上的工作目录
  ↓
创建或继续会话
  ↓
连续发送多轮指令
  ↓
目标电脑中的 Codex 在同一目录、同一会话上下文中执行
  ↓
手机实时查看过程、结果、错误和文件改动
```

## 2. v2.0 完成标准

v2.0.0 只有同时满足以下条件才视为完成：

1. 一套控制端可以同时管理至少两台设备。
2. 每台设备具有稳定且可持久化的设备身份，重启后不会生成新的设备记录。
3. 工作目录由设备本地注册，控制端不直接检查或访问远程设备路径。
4. 手机端可以按“设备 -> 工作目录”选择执行目标。
5. 一次性 Run 必须只在工作目录所属设备上执行。
6. 连续 Session 必须只在工作目录所属设备上创建。
7. 同一 Session 的连续 Turn 必须复用同一个 Codex App Server 会话，并保持相同工作目录。
8. 手机刷新或短暂断网后，可以重新读取会话历史并继续接收当前 Turn 的输出。
9. 设备离线、Agent 重启、命令重复投递、Turn 超时和取消都必须有明确状态闭环。
10. 写入模式只能操作已注册工作目录，不允许控制端通过请求下发任意本地路径。
11. 当前 `codex exec` 主链路和 App Server 会话能力均有自动化测试与 smoke 验收。
12. 所有关键改造都具备数据库迁移、兼容策略和回滚入口。

## 3. 当前基线

### 3.1 已具备能力

当前项目已经具备以下可复用基础：

- FastAPI 控制端和 SQLite/SQLModel 数据层。
- Runner 注册、心跳、任务认领、Codex 执行、取消检查和产物上传。
- App Server Bridge、AppThread、AppTurn、同步/异步执行和 stale recovery。
- AppThread 创建和 reopen 已能把 Project 路径传给 Bridge 作为 `cwd`。
- AppTurn 已有 SSE 输出入口，手机端能够增量显示 assistant 输出。
- React + TypeScript + Vite 手机前端。
- “会话 / 项目 / 运行 / 我的”会话优先信息架构。
- 项目筛选、最近会话、最近运行和 Runner/Bridge 诊断。
- Python 单元测试和 App Server smoke 脚本。

### 3.2 当前架构无法满足多设备目标的原因

当前实现仍以“后端、Runner、Bridge 位于同一台或可共享本地路径的电脑”为主要假设：

1. `Project.path` 是控制端数据库中的全局路径，创建项目时由控制端检查路径是否存在。
2. App Server Bridge 通过单一 `APP_SERVER_BRIDGE_URL` 配置，不能按设备路由。
3. Runner 和 Bridge 是两套独立执行通道，没有统一设备身份和命令协议。
4. App Server 会话状态主要保存在 Bridge 进程内存，Bridge 或 Agent 重启后的恢复能力有限。
5. Bridge 当前仍带有 POC 属性，工作目录、sandbox、审批策略和进程生命周期没有形成正式 Agent 边界。
6. Task 认领、事件上传和部分状态接口缺少完整幂等语义。
7. 日志上传仍偏向全量覆盖，不适合长时间、多设备任务。
8. 当前 Project 更接近“本机目录配置”，尚未成为“属于某台设备的 Workspace”。

因此，v2.0 不应继续在现有单机 Bridge 调用方式上叠加设备选择，而应重构为明确的控制面和设备执行面。

## 4. 目标架构

### 4.1 总体结构

```text
┌─────────────────────────────┐
│ Mobile Web / React Frontend │
└──────────────┬──────────────┘
               │ HTTPS / SSE
               ▼
┌──────────────────────────────────────────────┐
│ Control Plane / FastAPI                      │
│                                              │
│ Device API                                   │
│ Workspace API                                │
│ Run API                                      │
│ Session / Turn API                           │
│ Agent Command Queue                          │
│ Event Store / Artifact Metadata              │
│ SQLite（v2.0）                               │
└──────────────┬───────────────────────────────┘
               │ Agent 主动发起的 HTTPS 长轮询
               │ 命令认领 / 心跳 / 事件上传
       ┌───────┴────────┐
       ▼                ▼
┌───────────────┐  ┌───────────────┐
│ Device Agent A│  │ Device Agent B│
│               │  │               │
│ Workspace     │  │ Workspace     │
│ Registry      │  │ Registry      │
│ Run Executor  │  │ Run Executor  │
│ Session Mgr   │  │ Session Mgr   │
│ App Server    │  │ App Server    │
└───────┬───────┘  └───────┬───────┘
        │                  │
        ▼                  ▼
  Computer A          Computer B
  Codex CLI           Codex CLI
  Local Paths         Local Paths
```

### 4.2 架构决策

1. **控制端只保存目录标识和展示信息，不直接访问设备本地目录。**
2. **每台电脑运行一个 Device Agent。** Agent 统一承载 Runner 和 App Server Session Manager。
3. **Agent 主动连接控制端。** 不要求每台电脑开放可被控制端访问的入站端口。
4. **命令通过数据库持久化队列投递。** v2.0 先使用 SQLite，不引入 Redis/Celery。
5. **手机端只连接控制端。** 手机不直接连接各个设备 Agent。
6. **Run 和 Session 保留不同领域模型。** 两者共享 Agent 命令传输层，不强行合并业务语义。
7. **所有设备命令只引用 `workspace_id`。** Agent 根据本地注册表解析真实路径，命令中不接受任意 `cwd`。
8. **实时输出由 Agent 上传到控制端，再由控制端通过 SSE 推送给手机。** 控制端必须可重放已持久化事件。
9. **单用户优先。** v2.0 不引入复杂组织、租户和 RBAC，但设备凭证与手机凭证必须分离。
10. **继续复用现有技术栈。** 保留 FastAPI、SQLModel、React、Vite、pytest 和当前 Codex 执行器。

## 5. 核心领域模型

### 5.1 Device

代表一台可执行 Codex 的电脑。

建议字段：

```text
device_id              稳定 UUID，Agent 首次启动生成并持久化
display_name           手机端显示名称
hostname               主机名
os_name / os_version   操作系统信息
agent_version          Agent 版本
capabilities_json      codex exec、app-server、支持模型等能力
status                 ONLINE / OFFLINE / DISABLED
last_heartbeat_at      最近心跳
lease_expires_at       在线租约
created_at / updated_at
```

约束：

- `device_id` 必须稳定，不能再默认使用 `hostname + pid`。
- Agent 身份保存在本地 `data/agent.json` 或等价配置中。
- 每台设备使用独立 Device Token。

### 5.2 Workspace

代表某台设备上的一个允许 Codex 工作的目录。

建议字段：

```text
id
workspace_key          Agent 本地稳定标识
device_id
name
path_label             控制端展示名称，不要求暴露完整绝对路径
local_path             仅 Agent 本地配置保存；控制端可选加密保存或不保存
repo_root_label
enabled
default_model
default_reasoning_effort
default_sandbox
default_approval_policy
require_clean_worktree
created_at / updated_at
```

控制端数据库建议仅保存必要路径元数据。执行时由 Agent 使用本地 Workspace Registry 将 `workspace_id` 映射到真实路径。

唯一约束：

```text
unique(device_id, workspace_key)
```

同名目录可以存在于不同设备，不应发生冲突。

### 5.3 AgentCommand

作为控制端到设备的统一可靠命令信封。

建议字段：

```text
id                     UUID
device_id
command_type           RUN_EXECUTE / RUN_CANCEL / SESSION_OPEN /
                       TURN_START / TURN_CANCEL / SESSION_CLOSE
aggregate_type         RUN / SESSION / TURN
aggregate_id
idempotency_key        唯一
payload_json
status                 PENDING / CLAIMED / RUNNING / SUCCESS /
                       FAILED / CANCELLED / EXPIRED
lease_token
lease_expires_at
attempt_count
max_attempts
created_at / claimed_at / completed_at
last_error
```

关键规则：

- Claim 必须幂等。
- Agent 重试同一个请求时返回原 Command，而不是继续认领下一条。
- 所有 ACK、事件和完成请求必须携带 `command_id + lease_token`。
- 终态 Command 重复完成时返回当前终态，不重复执行业务副作用。

### 5.4 Run

当前 `Task` 的产品化名称，表示一次性 `codex exec` 执行。

建议在迁移期保留 `Task` 表和旧 API，通过服务层映射到 Run 语义；完成兼容迁移后再决定是否正式改表名。

新增或明确字段：

```text
workspace_id
device_id
command_id
client_request_id
log_offset
artifact_manifest_json
```

### 5.5 Session / Turn

当前 `AppThread` / `AppTurn` 的产品化领域模型。

Session 建议新增：

```text
workspace_id
device_id
agent_session_id       Agent 本地会话标识
codex_thread_id
generation             Agent 重建会话时递增
sandbox
approval_policy
network_access
status
last_event_sequence
```

Turn 建议新增：

```text
command_id
client_request_id
last_event_sequence
cancel_requested
```

### 5.6 TurnEvent

用于持久化和重放连续输出。

```text
id
turn_id
sequence
kind                   STATUS / ASSISTANT_DELTA / TOOL_EVENT /
                       APPROVAL / ERROR / FINAL
payload_json
created_at
```

唯一约束：

```text
unique(turn_id, sequence)
```

这样即使 Agent 重复上传，控制端也不会产生重复文本。

## 6. 分阶段开发路线

## M0：v2.0.0-alpha.1 工程基线与重构护栏

### 目标

在领域模型和进程结构重构前，先建立可回归、可迁移和可回滚的工程基线。

### 开发内容

1. 建立最小 CI：
   - `python -m compileall backend runner scripts poc/app_server`
   - `pytest -q`
   - `npm ci`
   - `npm run typecheck`
   - `npm run build`
2. 增加数据库 `schema_version` 和顺序迁移机制，替代持续堆叠 `_ensure_sqlite_columns`。
3. 为现有数据库增加自动备份入口和迁移失败回滚说明。
4. 对 FastAPI 路由进行按领域拆分：
   - `routers/devices.py`
   - `routers/workspaces.py`
   - `routers/runs.py`
   - `routers/sessions.py`
   - `routers/agent.py`
5. 保留 `backend/main.py` 作为应用装配入口，不在该文件继续堆积领域逻辑。
6. 增加 `request_id`、`device_id`、`workspace_id`、`run_id`、`session_id` 日志上下文。
7. 清理版本号和文档命名不一致：README、FastAPI version、Mobile iteration 和版本计划统一。
8. 增加功能开关：
   - `AGENT_COMMAND_MODE=false` 时保留当前本地模式。
   - `AGENT_COMMAND_MODE=true` 时启用新设备命令链路。
9. 冻结当前接口契约，为 Projects、Tasks、Runners、AppThreads、AppTurns 增加回归测试。
10. 对 Codex App Server 协议做技术验证并记录结果：
    - thread 是否支持恢复或 resume。
    - turn 是否支持协议级取消。
    - workspace-write sandbox 参数。
    - approval 事件结构。
    - app-server 进程重启后的 thread 行为。

### 验收标准

- 当前单机 Run 和 Session 流程不回归。
- 新旧模式可以通过配置切换。
- 数据库迁移可在已有 `app.db` 副本上成功执行。
- CI 能阻止 Python 测试、前端类型检查或构建失败的提交。
- App Server 协议不确定项形成明确测试结论，不以假设直接进入正式实现。

## M1：v2.0.0-alpha.2 Device 与 Workspace

### 目标

建立多设备和设备本地工作目录的正式领域模型。

### 开发内容

1. 新增 Device、Workspace 数据模型和迁移。
2. 新建 `agent/` 包，作为正式设备端入口：

```text
agent/
  main.py
  config.py
  identity.py
  api_client.py
  heartbeat.py
  workspace_registry.py
```

3. Agent 首次启动生成稳定 `device_id`，后续重启复用。
4. Device 注册和心跳接口使用独立 Device Token。
5. Agent 从本地配置加载允许访问的 Workspace：

```yaml
workspaces:
  - key: codex-job
    name: Codex Job
    path: F:\JustinKing\codex-job
    enabled: true
```

6. Agent 本地验证：
   - 路径存在。
   - 路径为目录。
   - 路径位于本机 allowlist。
   - 可选检查 Git 仓库。
7. Agent 向控制端同步 Workspace 元数据。
8. 控制端不再对新 Workspace 调用本机 `Path.exists()`。
9. 兼容迁移现有 Project：
   - 有 `default_runner_id` 的 Project 映射到对应 Device。
   - 无法确定设备的 Project 标记为 `UNBOUND`，由用户在手机端或配置中绑定。
10. 手机端项目页改为“设备 / 工作空间”结构：
    - 查看设备在线状态。
    - 选择设备。
    - 查看该设备已注册 Workspace。
    - 选择当前 Workspace。
11. current selection 从单一 `mobile.currentProjectId` 扩展为设备和 Workspace 组合。

### 验收标准

- 两个 Agent 可以同时注册且重启后 Device 记录不增加。
- 两个设备可以注册同名 Workspace。
- 设备 A 的 Workspace 不出现在设备 B 的执行选项中。
- 控制端所在机器不需要存在远程 Workspace 路径。
- 禁用 Workspace 后不能创建新的 Run 或 Session。
- Device Token 与手机 API Token 互不通用。

## M2：v2.0.0-beta.1 Agent 命令通道

### 目标

用统一、持久化、幂等的 Agent Command 协议替代控制端对单一 Runner/Bridge 的直接调用假设。

### 开发内容

1. 新增 `agent_commands` 表和状态机。
2. 新增 Agent API：

```text
POST /agent/register
POST /agent/heartbeat
POST /agent/workspaces/sync
POST /agent/commands/claim
POST /agent/commands/{id}/ack
POST /agent/commands/{id}/events
POST /agent/commands/{id}/complete
```

3. Claim 使用长轮询，Agent 主动连接控制端，不要求设备开放端口。
4. 增加 Claim 幂等键和 Agent 当前命令恢复逻辑。
5. 增加命令 lease、续租、过期恢复和最大重试次数。
6. Agent 端增加：

```text
agent/command_loop.py
agent/command_handlers.py
agent/event_uploader.py
agent/process_registry.py
```

7. 传输层统一，但保留 RunExecutor 和 SessionManager 两种业务处理器。
8. 事件上传使用递增 sequence，服务端按唯一约束去重。
9. 控制端重启后，PENDING Command 保留；CLAIMED/RUNNING Command 根据 lease 恢复。
10. Agent 重连后先报告当前本地运行中的 process/session，再继续认领新命令。

### 验收标准

- 模拟响应丢失后重复 Claim，不会导致同一 Agent 意外认领第二条命令。
- 重复 ACK、事件和 complete 不会造成重复状态变化或重复输出。
- 控制端重启后未开始命令仍可继续被认领。
- Agent 离线后命令不会被其他设备错误执行。
- 所有命令都能追踪到 Device、Workspace 和领域对象。

## M3：v2.0.0-beta.2 多设备 Run

### 目标

首先完成稳定的一次性远程执行链路，验证多设备路由和 Agent 通道。

### 开发内容

1. 创建 Run 时只提交 `workspace_id`，由控制端解析所属 `device_id`。
2. 控制端生成 `RUN_EXECUTE` Command。
3. Agent 根据 Workspace Registry 获取真实目录并调用现有 `execute_codex`。
4. 复用现有 Git preflight、Codex command builder、进程树终止和 artifact 收集逻辑。
5. 日志上传改为增量协议：

```text
run_id
sequence
offset
content
```

6. 后端校验 offset/sequence，支持断线重传和去重。
7. 产物使用 manifest 管理，限制单文件和总上传大小。
8. Run 取消必须实际终止 Agent 上对应进程树。
9. 每个 Agent 支持可配置 Run 并发数，默认保持保守值。
10. 每个 Workspace 默认只允许一个写入型 Run 或 Session，避免目录并发修改。
11. 手机端运行页显示：
    - Device。
    - Workspace。
    - 当前状态。
    - 日志增量。
    - result/diff/artifact。
    - 取消和重跑。
12. 旧 `/runner/*` 接口在迁移期保留兼容适配，完成验证后再废弃。

### 验收标准

- 在手机选择 Device A 的 Workspace 后，Run 只在 Device A 执行。
- Device B 不会认领 Device A 的 Run。
- 网络中断后 Agent 可以继续本地执行并在恢复连接后补传日志和结果。
- 取消 Run 后 Codex 进程树被终止，状态最终为 CANCELLED。
- 长日志不会每次全量重传。
- 同一 `client_request_id` 重复提交不会创建两个 Run。

## M4：v2.0.0-beta.3 多设备连续 Session

### 目标

实现用户预期中的核心能力：在手机端选择某台电脑的一个目录，并在该目录内持续进行多轮 Codex 会话工作。

### 开发内容

1. 将 App Server Bridge 能力迁入正式 Agent Session Manager：

```text
agent/session_manager.py
agent/app_server/client.py
agent/app_server/event_parser.py
agent/app_server/process.py
```

2. `poc/app_server` 在功能迁移完成前保留，测试通过后再归档，不直接删除历史实现。
3. 控制端创建 Session 时生成 `SESSION_OPEN` Command。
4. Agent 只根据 `workspace_id` 查找本地目录，不接受控制端传入任意路径。
5. Session 固定绑定：

```text
device_id + workspace_id + agent_session_id + codex_thread_id
```

6. 同一个 Session 的所有 Turn 必须复用相同 Agent Session 和 Codex thread。
7. 创建 Turn 时生成 `TURN_START` Command。
8. Agent 将 App Server 增量事件按 sequence 上传到控制端。
9. 控制端持久化 TurnEvent，并通过现有 SSE 入口向手机重放和推送。
10. 手机刷新后按最后 event sequence 继续读取，不重复拼接 assistant 文本。
11. 每个 Session 同一时间只允许一个活跃 Turn，约束必须在数据库或原子状态更新层实现。
12. 增加 Workspace 写锁：
    - 写入型 Session 和 Run 默认互斥。
    - 只读 Session 可按配置并发。
13. 将 Bridge 中硬编码的只读策略改为 Session 配置：
    - `READ_ONLY`：仅分析和问答。
    - `WORKSPACE_WRITE`：允许修改已注册 Workspace。
14. sandbox、approval policy 和 network access 必须经过 Agent 本地策略校验，控制端不能突破本地上限。
15. 默认关闭网络访问；启用写入能力时在手机端明确显示当前执行模式。
16. 会话页头部始终显示当前 Device 和 Workspace，避免误操作其他电脑或目录。
17. 支持会话创建、切换、重命名、关闭、reopen 和历史 Turn 查看。
18. UI 不再暴露 `bridge_thread_id` 等实现细节，使用 Session/Turn 产品语义。

### 验收标准

- 在 Device A / Workspace X 创建 Session 后连续发送至少 5 个 Turn，所有 Turn 使用相同 `cwd` 和 Codex thread。
- 切换到 Device B / Workspace Y 后，新 Session 只在 Device B 上运行。
- Device A 与 Device B 的会话和事件不会串线。
- 手机刷新页面后可以恢复历史内容，并继续查看正在运行 Turn 的增量输出。
- 重复的事件上传不会造成 assistant 文本重复。
- 同一 Session 的并发 Turn 返回明确 409 或进入受控队列。
- 写入模式只能修改 Workspace X 内文件，不能通过请求切换到其他本地路径。
- Workspace 已被写入型 Run 占用时，新的写入型 Session 给出明确 busy 状态。

## M5：v2.0.0-rc.1 恢复、取消与安全收口

### 目标

补齐长时间连续使用必需的异常恢复、强取消和安全边界。

### 开发内容

1. Turn 取消优先使用已验证的 App Server 协议级取消能力。
2. 如果协议不支持可靠取消：
   - 终止该 Session 的 App Server 子进程。
   - 将当前 Turn 标记为 CANCELLED。
   - 将 Session 标记为 RECOVER_REQUIRED。
   - 用户执行 reopen 后创建新 generation。
3. Turn 超时采用同样的进程隔离策略，不继续复用状态不确定的 App Server 进程。
4. Agent 保存本地 Session Registry 和进程元数据。
5. Agent 重启后执行 Session reconciliation：
   - 协议支持恢复时尝试恢复 `codex_thread_id`。
   - 不支持时保留 UI 历史，并明确标记需要 reopen。
6. 控制端重启后，不把所有活跃 Turn 直接无条件失败；先等待 Agent reconciliation 窗口，再决定恢复或失败。
7. 增加离线状态策略：
   - 默认新命令 fail-fast，不静默排队到未知时间。
   - 可选允许用户显式选择“设备上线后执行”。
8. 增加资源限制：
   - 每台设备最大 Session 数。
   - 每个 Workspace 最大活跃写入操作数。
   - 事件、日志和产物大小限制。
   - Bridge/App Server 空闲回收。
9. 凭证拆分：
   - Mobile API Token。
   - Device Token。
   - 可选一次性设备配对码。
10. Token 只保存哈希，支持轮换和吊销。
11. 推荐部署在可信局域网或私有网络；不把当前版本直接暴露到公网。
12. 增加审计日志：设备、Workspace、Run、Session、Turn、取消、失败和配置变化。
13. 所有对外错误返回稳定 code，不直接暴露服务器或设备绝对路径。
14. 增加数据清理、Session 归档、事件压缩和产物保留策略。

### 验收标准

- Agent 中断、控制端中断和网络中断均有可预测状态。
- 取消或超时后的 App Server 进程不会继续在后台修改目录。
- Agent 重连后不会重复执行已成功或已取消命令。
- 已吊销 Device Token 无法继续心跳、认领或上传事件。
- 手机 API 响应不泄露设备绝对路径、Token 或内部运行目录。
- 恶意或错误的 `workspace_id` 不能访问 Agent 未注册路径。

## M6：v2.0.0 产品验收与发布收口

### 目标

围绕真实多设备使用场景完成手机体验、部署和验收材料。

### 开发内容

1. 手机端信息架构最终收口为：

```text
会话 / 工作空间 / 运行 / 我的
```

2. 工作空间页支持：
   - 设备列表和在线状态。
   - 当前设备。
   - 当前 Workspace。
   - 最近会话。
   - 最近运行。
3. 会话页支持：
   - Device / Workspace 上下文提示。
   - 新建连续会话。
   - 实时输出。
   - 取消。
   - reopen/recover。
   - 写入模式醒目标识。
4. 我的页支持：
   - 控制端状态。
   - Device Agent 版本与诊断。
   - Token 管理。
   - 数据清理。
   - smoke 命令。
5. 提供 Windows Agent 安装和自启动脚本：
   - `install_agent.ps1`
   - `uninstall_agent.ps1`
   - 环境检查。
6. 增加双 Agent 本机模拟脚本，便于在一台电脑上验证多设备路由。
7. 更新 README、API、状态机、部署、迁移、故障排查和验收文档。
8. 清理或归档历史计划，避免 docs 根目录继续堆积版本草稿。
9. 完成 v2.0 release checklist 和数据库升级说明。

### 验收标准

- 新用户按 README 可以部署一个 Control Plane 和至少一个 Device Agent。
- 第二台电脑加入后不需要修改控制端代码或新增独立后端实例。
- 手机上可以清晰判断当前操作的是哪台电脑和哪个目录。
- 核心验收矩阵全部通过。
- 从现有单机数据升级后，旧 Run 和会话历史仍可读取。

## 7. 推荐代码结构

重构应分阶段完成，不进行一次性大爆炸式迁移。

```text
backend/
  main.py
  db.py
  models/
    device.py
    workspace.py
    command.py
    run.py
    session.py
  routers/
    devices.py
    workspaces.py
    runs.py
    sessions.py
    agent.py
  services/
    device_service.py
    workspace_service.py
    command_service.py
    run_service.py
    session_service.py
    event_service.py

agent/
  main.py
  config.py
  identity.py
  api_client.py
  command_loop.py
  workspace_registry.py
  process_registry.py
  run_executor.py
  session_manager.py
  event_uploader.py
  app_server/
    client.py
    process.py
    event_parser.py

frontend/src/
  api/
  components/
    devices/
    workspaces/
    runs/
    session/
    settings/
  hooks/
  state/
  utils/

tests/
  unit/
  integration/
  contract/
  e2e/
```

目录调整原则：

- 先通过兼容模块导出原有函数，再逐步移动调用方。
- 不在同一提交中同时进行模型迁移、路由迁移和 UI 大改。
- 每个里程碑完成后必须保持可启动、可回归。

## 8. API 目标草案

### 8.1 手机/控制端 API

```text
GET  /devices
GET  /devices/{id}
GET  /workspaces?device_id={id}
GET  /workspaces/{id}

POST /runs
GET  /runs
GET  /runs/{id}
POST /runs/{id}/cancel
POST /runs/{id}/rerun
GET  /runs/{id}/stream

POST /sessions
GET  /sessions
GET  /sessions/{id}
PATCH /sessions/{id}
POST /sessions/{id}/reopen
DELETE /sessions/{id}

POST /sessions/{id}/turns
GET  /sessions/{id}/turns
GET  /turns/{id}
GET  /turns/{id}/stream
POST /turns/{id}/cancel
```

### 8.2 Agent API

```text
POST /agent/register
POST /agent/heartbeat
POST /agent/workspaces/sync
POST /agent/commands/claim
POST /agent/commands/{id}/ack
POST /agent/commands/{id}/events
POST /agent/commands/{id}/complete
POST /agent/reconcile
```

### 8.3 兼容策略

迁移期保留：

```text
/projects
/tasks
/runner/*
/app-threads
/app-turns
```

旧 API 调用新服务层或返回弃用提示，不在 v2.0 重构初期直接删除。

## 9. 数据迁移策略

1. M0 引入版本化 migration runner。
2. 创建 `devices`、`workspaces`、`agent_commands`、`turn_events` 新表。
3. 从 `runner_records` 回填 Device：
   - 仅把显式稳定 Runner ID 自动迁移为 Device。
   - 由 PID 组成的不稳定 Runner ID 标记待确认。
4. 从 `projects` 回填 Workspace：
   - 通过 `default_runner_id` 尝试绑定 Device。
   - 无法绑定的项目进入 UNBOUND 状态。
5. 给 Task/AppThread 增加 `workspace_id`、`device_id` 等字段。
6. 迁移期双读，不进行长期双写：
   - 新记录优先写新字段。
   - 旧记录通过兼容适配读取。
7. AppThread/AppTurn 历史不强制迁移为可恢复 Agent Session，只保留历史展示。
8. 完成 v2.0 验收后再清理旧字段和旧接口。
9. 每次迁移前自动创建数据库备份。
10. 回滚时允许关闭 `AGENT_COMMAND_MODE` 返回旧本地模式。

## 10. 测试与验收矩阵

### 10.1 单元测试

必须覆盖：

- Device identity 持久化。
- Workspace 本地路径校验和控制端映射。
- AgentCommand 状态机。
- Claim 幂等和 lease。
- Run/Session 路由到正确 Device。
- TurnEvent sequence 去重。
- Workspace 写锁。
- 取消、超时、重试和终态幂等。
- 数据迁移和回滚。

### 10.2 集成测试

使用两个 Fake Agent 和两个临时 Workspace：

```text
Agent A -> Workspace A
Agent B -> Workspace B
```

验证：

1. A 的命令只被 A 认领。
2. B 的命令只被 B 认领。
3. 同名 Workspace 不混淆。
4. Agent 重试 Claim 不多领命令。
5. 控制端重启后命令和事件不丢失。
6. Agent 断线后补传事件不重复。
7. 手机 SSE 重连后从 sequence 继续。

### 10.3 前端测试

引入最小必要的 Vitest + React Testing Library：

- Device/Workspace 切换。
- 当前上下文显示。
- 离线设备禁用发送。
- Session 连续消息渲染。
- SSE 重连和事件去重。
- Run/Turn 取消状态。

仅对核心路径增加少量 E2E：

```text
选择设备 -> 选择 Workspace -> 新建 Session -> 连续发送 -> 查看输出
```

### 10.4 真实 Smoke

至少保留以下场景：

1. 单设备 Run。
2. 双设备 Run 路由。
3. 单设备连续 5 Turn Session。
4. 双设备 Session 隔离。
5. 手机刷新恢复。
6. Agent 断线重连。
7. Run 取消。
8. Turn 取消或进程回收。
9. 控制端重启恢复。
10. Workspace 越权路径拒绝。

## 11. 优先级

### P0：未完成前不进入稳定版

- Device 稳定身份。
- Workspace 绑定 Device。
- 控制端不访问远程路径。
- AgentCommand 幂等、lease 和恢复。
- Run 精确设备路由。
- Session 精确设备和 Workspace 路由。
- 同一 Session 连续使用同一 Codex thread。
- 事件 sequence、持久化和重放。
- 实际取消或进程回收。
- Device Token 隔离。
- CI 和迁移机制。

### P1：v2.0 应完成

- Agent 自启动安装脚本。
- Workspace 写锁。
- Agent/控制端重启 reconciliation。
- Session reopen 和 generation。
- 增量日志和产物限制。
- 手机端 Device/Workspace 上下文。
- 双 Agent 自动化 smoke。
- 审计日志和数据清理。

### P2：v2.0 后续增强

- 公网部署方案和完整用户认证。
- 多用户、组织和 RBAC。
- Approval UI。
- 可视化 diff 与文件浏览。
- Push notification。
- PostgreSQL、Redis 或分布式控制面。
- 多 Control Plane 高可用。
- 跨设备 Workspace 同步。
- 自动 Git branch/worktree 隔离。

## 12. 明确不做

v2.0 不包含：

1. 任意远程 Shell。
2. 控制端下发任意绝对路径。
3. 多租户 SaaS。
4. 默认公网暴露。
5. 自动跨设备同步代码或文件。
6. 自动 push。
7. 未经确认自动修改 Git 远端。
8. 为了架构统一而删除当前稳定的 `codex exec` 能力。
9. 在没有协议验证的情况下依赖 Codex App Server 未确认接口。
10. 仅为“技术先进”引入 Redis、Celery、Kafka 或 Kubernetes。

## 13. 实施顺序

严格按以下顺序推进：

```text
M0 工程基线
  ↓
M1 Device / Workspace
  ↓
M2 Agent Command
  ↓
M3 多设备 Run
  ↓
M4 连续 Session
  ↓
M5 恢复、安全、取消
  ↓
M6 产品验收与发布
```

不得先做大规模 UI 美化，也不得在 Device/Workspace 和 AgentCommand 尚未稳定时直接实现多设备 App Server 直连。

## 14. 每个里程碑的交付要求

每个里程碑必须单独输出：

```text
本次完成：
- 功能清单

修改文件：
- 新增
- 修改
- 归档
- 删除

数据迁移：
- migration version
- 备份方式
- 回滚方式

验证结果：
- 自动化测试命令和结果
- smoke 步骤和结果
- 人工验收步骤和结果

风险与未完成项：
- 已知风险
- 未验证路径
- 后续依赖
```

禁止把多个里程碑合并成一次不可回滚的大提交。