# Codex Job 审计问题修复执行计划（2026-06-30）

本文基于 2026-06-30 对 `JustinQP/codex-job` 当前代码的全面审核结果，目标是把已识别问题全部转化为可执行、可验收、可拆 PR 的修复路线。

## 1. 执行目标

当前 v2.0 主线已经收敛为：

```text
mobile / API
  -> backend/main.py
  -> AgentCommand 持久化命令队列
  -> agent/main.py on selected device
  -> workspace registry
  -> codex exec / agent-managed codex app-server
```

本计划不推倒重写，而是在现有架构上补齐四类能力：

1. 可靠性：设备断线、Agent 重启、租约过期、命令恢复都能得到确定结果。
2. 可观测性：手机端能看到 Run 日志、最终结果、diff、报告和会话事件。
3. 管理闭环：手机端可以管理 Device、Workspace、Project 的关键配置。
4. 安全边界：输入大小、token 使用、路径控制、真实部署边界都要明确。

## 2. 执行原则

- 每个 PR 只修一类问题，避免一次性大改导致回归定位困难。
- 所有后端行为变更必须补测试；所有前端 API 类型变更必须通过 `npm run typecheck`。
- 所有状态机、租约和恢复逻辑必须有明确验收场景，而不是只靠 happy path。
- fake smoke 保留为低成本回归；真实双设备 smoke 必须补成单独验收项。
- 默认仍按单用户、本地或可信局域网产品边界设计，不按公网多租户系统扩展。

## 3. 总体里程碑

| 阶段 | 目标 | 结果物 | 建议 PR |
| --- | --- | --- | --- |
| Phase 0 | 修复阻断真实使用的 P0/P1 问题 | 设备在线判断、capabilities、agent data dir、状态错误映射、输入限制 | PR 1-4 |
| Phase 1 | 补齐 AgentCommand/Agent 恢复机制 | retry/requeue 语义、reconcile 协议、续租失败策略、跨进程 workspace lock | PR 5-7 |
| Phase 2 | 完成移动端产品闭环 | Run artifact viewer、项目/设备/workspace 管理、会话高级配置 | PR 8-11 |
| Phase 3 | 运维、安全和真实验收 | 审计日志、备份清理、真实双设备 smoke、部署文档 | PR 12-15 |

## 4. 问题修复矩阵

### 4.1 P0：必须优先修复

| 编号 | 问题 | 修复方向 | 主要文件 | 验收标准 |
| --- | --- | --- | --- | --- |
| P0-1 | 创建 Run/AppThread 时可能把命令发给已 lease 过期但 DB 仍标记 ONLINE 的设备 | 增加统一在线设备检查，创建任务前刷新目标设备状态 | `backend/services/device_service.py`, `backend/services/run_service.py`, `backend/services/app_thread_service.py` | 手动构造 `lease_expires_at < now` 的设备后，创建 Run/AppThread 返回 `409 device is offline` |
| P0-2 | Agent heartbeat capability 声明与实际功能不一致，`app_server` 固定为 false | capabilities 按 Agent 实际启用能力动态生成 | `agent/heartbeat.py`, `agent/main.py`, `agent/config.py` | 启用 app session manager 时，设备 capability 显示 `app_server: true` |
| P0-3 | Agent 本地 run 输出目录使用相对 `data/agent-runs`，未纳入 `CODEX_AGENT_DATA_DIR` | 新增 `AgentConfig.run_data_dir`，传入 `RunExecutor` | `agent/config.py`, `agent/main.py`, `agent/command_handlers.py`, `agent/run_executor.py` | 从任意 cwd 启动 Agent，run 日志和产物都落在 `CODEX_AGENT_DATA_DIR/runs` |
| P0-4 | `AgentCommandStateError` 未被 router 映射，非法状态流转可能暴露 500 | 统一状态机错误类型或 router 捕获为 409 | `backend/services/agent_command_service.py`, `backend/routers/agent.py` | 非法 ack/renew/complete 返回稳定 JSON 错误，状态码为 409，不出现 500 |
| P0-5 | prompt/message/title/content 缺少完整大小限制 | schema 加 max_length / byte limit，前端显示限制 | `backend/schemas.py`, `frontend/src/components/session/*`, `frontend/src/components/runs/*` | 超大 prompt/message/artifact 被拒绝，错误码稳定，前端有提示 |

### 4.2 P1：可靠性闭环

| 编号 | 问题 | 修复方向 | 主要文件 | 验收标准 |
| --- | --- | --- | --- | --- |
| P1-1 | `AgentCommand.max_attempts` 字段存在但无实际 retry/requeue 语义 | 明确定义 CLAIMED/RUNNING 过期后的重试策略 | `backend/services/agent_command_service.py`, `backend/services/agent_command_maintenance_service.py` | 未 ack 的 CLAIMED 可按 max_attempts 回到 PENDING；RUNNING 默认不重复执行写任务 |
| P1-2 | Reconcile 的 `UPLOAD_EVENTS` 语义不够清晰 | 返回 server/client sequence，并让 Agent 按 sequence 补传 | `backend/services/agent_reconciliation_service.py`, `agent/reconciliation.py`, `agent/event_uploader.py` | Agent 重启后，本地未上传事件能按缺口补传，服务端不重复、不丢事件 |
| P1-3 | Agent 续租失败时默认继续执行，长期断网场景不可控 | 增加续租失败计数和 grace 策略 | `agent/run_executor.py`, `agent/session_handlers.py`, `agent/command_loop.py` | 连续续租失败达到阈值后能安全终止或标记 completion pending |
| P1-4 | AppTurn 默认 180 秒超时硬编码，API/前端不可控 | 为 AppThread/AppTurn 增加 timeout 配置并传到 Agent | `backend/schemas.py`, `backend/services/app_thread_service.py`, `agent/session_handlers.py`, `agent/app_server/session_manager.py`, `frontend/src/api/appThreads.ts` | 移动端可配置 turn timeout；慢任务不再固定 180 秒失败 |
| P1-5 | Agent 本地 workspace lock 仅进程内有效，多 Agent 进程会互相踩 workspace | 增加跨进程 lock file | `agent/workspace_lock.py`, `agent/run_executor.py`, `agent/session_handlers.py` | 同一机器启动两个 Agent 进程写同 workspace，第二个被拒绝 |
| P1-6 | app-server JSONL message 内存列表无界增长 | turn 完成后按 turn 落盘并裁剪内存 | `agent/app_server/client.py`, `agent/app_server/session_manager.py` | 长会话多轮后 Agent 内存不会随历史事件线性无限增长 |

### 4.3 P2：产品能力补齐

| 编号 | 问题 | 修复方向 | 主要文件 | 验收标准 |
| --- | --- | --- | --- | --- |
| P2-1 | Workspace sync 非原子，循环 upsert 内部逐条 commit | 先全量校验，再单事务 upsert/disable | `backend/services/workspace_service.py`, `tests/test_workspace_service.py` | payload 中后段出错时，前面的 workspace 不会半提交 |
| P2-2 | Workspace registry 未同步默认模型/sandbox/approval/clean-worktree | 扩展 `workspaces.json` schema 和 `to_sync_items` | `agent/workspace_registry.py`, `backend/schemas.py`, `README.md` | 本地 workspace 配置能同步到后端并显示在移动端 |
| P2-3 | Run 详情页无法查看日志、result、diff 和报告 | 增加 Run artifact viewer tabs | `frontend/src/components/runs/RunsPage.tsx`, `frontend/src/api/runs.ts`, `frontend/src/api/types.ts` | 手机端可查看 run.log、result.md、diff.patch、git status、run report |
| P2-4 | 设备管理能力不足 | 增加 rename/disable/delete 设备 API 和 UI | `backend/routers/devices.py`, `backend/services/device_service.py`, `frontend/src/components/projects/*` | 手机端可禁用失效设备、重命名设备、查看 capabilities |
| P2-5 | Project/Workspace 管理能力不足 | 增加 Project update、Workspace enable/disable/update defaults | `backend/routers/projects.py`, `backend/routers/workspaces.py`, `backend/services/project_service.py`, `backend/services/workspace_service.py` | 手机端可修改默认模型、sandbox、approval、clean-worktree、绑定 workspace |
| P2-6 | 创建 AppThread 只传 project/title/workspace，缺少高级配置 | 前端增加 sandbox、approval_policy、network_access、timeout_seconds 配置 | `frontend/src/components/session/*`, `frontend/src/api/appThreads.ts`, `backend/schemas.py` | 新建会话可选择高级配置，默认继承 Project/Workspace |
| P2-7 | SSE 流式接口是同步轮询式长连接，扩展性一般 | 改 async generator 或短 session 查询；保留 DB 回放能力 | `backend/routers/app_threads.py`, `backend/services/app_thread_service.py` | 多个 SSE 连接下 DB session 不被长期持有，断开能及时释放 |
| P2-8 | API token 存 localStorage，仅适合可信 LAN | 文档明确边界，增加可选外层认证方案 | `docs/*`, `frontend/src/components/settings/SettingsPage.tsx` | 文档明确公网部署必须使用 HTTPS/反代认证；UI 不误导为多用户安全系统 |

### 4.4 P3：测试、文档和运维

| 编号 | 问题 | 修复方向 | 主要文件 | 验收标准 |
| --- | --- | --- | --- | --- |
| P3-1 | 测试中存在字段名漂移，`app_thread_id` 与模型 `codex_thread_id` 不一致 | 修正测试字段，并启用更严格类型/字段检查 | `tests/test_multi_fake_agent_integration.py`, `backend/models.py` | 测试不依赖未知字段被忽略，能真实覆盖 codex_thread_id |
| P3-2 | 真实双设备 smoke 未完成记录 | 增加真实双设备 smoke checklist 和记录模板 | `docs/smoke-checklist.md`, `scripts/*` | 两台真实设备完成同名 workspace、Run、Session、取消、重开验收 |
| P3-3 | 运维日志和审计不足 | 增加结构化 audit log | `backend/services/*`, `backend/models.py`, `backend/migrations.py` | 创建/取消/完成 Run、Thread、Turn、Agent claim/complete 都有审计记录 |
| P3-4 | 数据保留、备份和清理策略不足 | 增加 sqlite backup、artifact/log 清理命令 | `scripts/*`, `docs/*`, `backend/config.py` | 可按天清理 archived/error/closed 记录和旧 artifact，DB 可一键备份 |
| P3-5 | CI 只跑通用测试，缺少 smoke 和依赖检查 | CI 增加 smoke、frontend build 缓存、依赖一致性检查 | `.github/workflows/ci.yml`, `requirements.txt`, `frontend/package-lock.json` | CI 覆盖 `scripts/smoke_local_e2e.py`，并核验 Python/Node 依赖 |

## 5. PR 拆分方案

### PR 1：Device liveness hardening

**目标**：所有创建任务入口都用统一在线判断，避免命令发给已断线设备。

改动：

- 新增 `device_service.refresh_device_status(session, device_id)`。
- 新增 `device_service.ensure_online_device(session, device_id)`。
- 替换 `run_service.create_run` 和 `app_thread_service._get_usable_device` 中的直接 status 判断。
- 为 Run、AppThread、Reopen、Rerun 增加过期 lease 测试。

验收：

```powershell
pytest -q tests/test_runs_api.py tests/test_app_threads_api.py tests/test_device_service.py
```

### PR 2：Agent capabilities 与 data dir 修正

**目标**：Agent 上报能力可信，产物路径稳定。

改动：

- `AgentConfig` 增加 `run_data_dir`。
- `AgentCommandLoop` / `CommandHandlerRegistry` / `RunExecutor` 传入 run data dir。
- `heartbeat.py` 根据实际是否启用 app session manager 上报 capability。
- README 更新 agent data dir 说明。

验收：

```powershell
pytest -q tests/test_agent_run_executor.py tests/test_multi_fake_agent_integration.py
python scripts\smoke_local_e2e.py
```

### PR 3：AgentCommand 错误映射和状态机加固

**目标**：所有非法状态流转都返回稳定 API 错误。

改动：

- `AgentCommandStateError` 继承或包装为 `AgentCommandServiceError`。
- `backend/routers/agent.py` 增加统一错误转换。
- 补非法 complete/renew/ack 测试。

验收：

```powershell
pytest -q tests/test_agent_command_api.py tests/test_agent_command_service.py
```

### PR 4：输入限制与 AppTurn timeout

**目标**：防止误粘贴超大输入，支持慢 turn。

改动：

- Run prompt、AppTurn message、AppThread title 增加 max_length。
- AppTurnCreate 增加 `timeout_seconds`，后端 payload 下发 Agent。
- Session UI 增加字数提示和 timeout 高级配置。

验收：

```powershell
pytest -q tests/test_app_threads_api.py tests/test_runs_api.py
cd frontend
npm.cmd run typecheck
npm.cmd run build
cd ..
```

### PR 5：AgentCommand retry/reconcile 修复

**目标**：Agent 重启、断线、事件上传中断可恢复。

改动：

- 定义 CLAIMED 未 ack 过期的 retry 规则。
- RUNNING 写任务默认不自动重试；read-only 可配置重试。
- Reconcile 返回 server/client sequence。
- Agent event uploader 支持按 sequence 补传。

验收：

```powershell
pytest -q tests/test_agent_reconciliation.py tests/test_agent_command_events.py tests/test_multi_fake_agent_integration.py
```

### PR 6：跨进程 workspace lock

**目标**：同一机器多个 Agent 进程也不会并发写同一 workspace。

改动：

- `LocalWorkspaceLock` 增加 file lock 实现。
- lock 文件放在 `CODEX_AGENT_DATA_DIR/locks`，key 使用 workspace path hash。
- 增加 stale lock 清理策略。

验收：

```powershell
pytest -q tests/test_workspace_execution_locks.py tests/test_agent_run_executor.py
```

### PR 7：app-server session 内存与事件落盘优化

**目标**：长会话不会无限增长内存。

改动：

- 每个 turn 完成后写入 turn events 文件。
- `_messages` 保留最近窗口或按 active turn 裁剪。
- SSE 恢复优先走后端持久化事件。

验收：

- 单测验证多 turn 后 `_messages` 不超过配置上限。
- fake e2e 仍能拿到 assistant_final 和 event_summary。

### PR 8：Workspace sync 原子化与 defaults 同步

**目标**：workspace registry 成为可信配置来源。

改动：

- 扩展 registry 字段：`default_model`, `default_reasoning_effort`, `default_sandbox`, `default_approval_policy`, `require_clean_worktree`。
- sync 前先校验全部 workspace，单事务提交。
- README 更新示例。

验收：

```powershell
pytest -q tests/test_workspace_service.py tests/test_multi_fake_agent_integration.py
```

### PR 9：Run artifact viewer

**目标**：移动端完成 Run 观察闭环。

改动：

- `frontend/src/api/runs.ts` 增加读取 text artifact 的函数。
- Run detail 增加 tab：日志、结果、diff、git status、report。
- 支持复制内容和空状态提示。

验收：

```powershell
cd frontend
npm.cmd run typecheck
npm.cmd run build
cd ..
python scripts\smoke_local_e2e.py
```

### PR 10：Device / Project / Workspace 管理 UI

**目标**：移动端可完成基础管理，不需要手工改 DB。

改动：

- Device：rename、disable、delete stale。
- Workspace：enable/disable、update defaults。
- Project：update defaults、bind workspace、enable/disable。
- 前端 Projects/Settings 页接入。

验收：

- API 测试覆盖权限、非法状态、绑定冲突。
- 前端 typecheck/build 通过。

### PR 11：AppThread 创建高级配置

**目标**：会话创建支持 sandbox、approval、network、timeout。

改动：

- Thread switcher 新建会话 sheet 增加高级区。
- 后端 schema 和 payload 保持兼容。
- 如果未来 `approval_policy != never`，必须在 UI 明确“不支持审批 UI”的限制。

验收：

- 创建 read-only / workspace-write 会话都能正确下发配置。
- workspace-write 会话仍被后端 lock 保护。

### PR 12：SSE 流式接口改造

**目标**：减少长期 DB session 和同步阻塞。

改动：

- 将 stream endpoint 改为 async generator。
- 每轮查询使用短生命周期 session。
- 客户端断开后及时退出。

验收：

- 断开 SSE 后服务端不继续循环。
- 多个客户端同时 stream 不互相阻塞。

### PR 13：审计日志与运维脚本

**目标**：长时间运行时可追踪、可清理、可恢复。

改动：

- 增加 `audit_events` 表。
- 记录 Run/AppThread/AppTurn/AgentCommand 关键操作。
- 增加 DB backup 和 artifact cleanup 脚本。

验收：

- 创建/取消/完成操作后 audit events 可查询。
- 清理脚本 dry-run 和 apply 模式可用。

### PR 14：真实双设备 smoke

**目标**：把未验证的真实双设备场景转为可重复验收。

改动：

- 增加 `docs/real-dual-device-smoke.md`。
- 增加可选脚本输出设备、workspace、run、thread 验收结果。
- smoke checklist 增加记录模板。

验收：

- 两台真实设备注册成功。
- 同名 workspace 不串设备。
- read-only session、workspace-write run、取消、重开都通过。

### PR 15：CI 和依赖治理

**目标**：CI 覆盖主线 smoke，依赖更可控。

改动：

- CI 增加 `python scripts/smoke_local_e2e.py`。
- 核验 `requirements.txt` 中依赖名是否符合预期。
- 可选：引入 `pip-tools` 或锁定关键依赖上限。

验收：

```powershell
python -m compileall backend agent scripts
pytest -q tests --basetemp .pytest-tmp-v2-mainline
python scripts\smoke_local_e2e.py
cd frontend
npm.cmd run typecheck
npm.cmd run build
cd ..
git diff --check
```

## 6. 推荐执行顺序

1. PR 1：Device liveness hardening。
2. PR 2：Agent capabilities 与 data dir 修正。
3. PR 3：AgentCommand 错误映射。
4. PR 4：输入限制与 AppTurn timeout。
5. PR 5：retry/reconcile 修复。
6. PR 8：Workspace sync 原子化与 defaults 同步。
7. PR 9：Run artifact viewer。
8. PR 10-11：管理 UI 和会话高级配置。
9. PR 6-7：本地跨进程锁与 app-server 内存优化。
10. PR 12-15：SSE、审计、真实 smoke、CI/依赖治理。

说明：PR 6-7 技术风险略高，但不直接阻塞当前单用户 happy path，可以在前面高收益问题修完后推进。

## 7. 每轮 PR 的统一验收清单

每个 PR 合并前至少运行：

```powershell
python -m compileall backend agent scripts
pytest -q tests --basetemp .pytest-tmp-remediation
cd frontend
npm.cmd run typecheck
npm.cmd run build
cd ..
git diff --check
```

涉及主链路的 PR 额外运行：

```powershell
python scripts\smoke_local_e2e.py
```

涉及真实 Agent、workspace-write、app-server 的 PR 额外执行真实设备 smoke。

## 8. 完成定义

本计划视为完成时，需要满足：

- P0/P1 问题全部有测试覆盖并通过。
- 手机端可以查看 Run 日志、最终结果、diff 和报告。
- 手机端可以管理 Device、Workspace、Project 的基础状态和默认配置。
- Agent 断线、重启、租约过期、事件补传有明确且已测试的行为。
- fake e2e 和真实双设备 smoke 均有通过记录。
- README、smoke checklist、运维文档同步更新。
