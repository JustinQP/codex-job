# v1.3 Mobile 试用稳定性与可维护性增强计划

## 1. 背景

当前项目已经完成：

```text
v1.0.0：稳定版收口、README/docs、smoke 验收矩阵
v1.1.x：Mobile 第一轮 UI/UX 重构，完成四 Tab、卡片、toast、气泡会话
v1.2.x：Mobile App 产品化第二版，完成首页/任务/会话/我的、Sheet、更多菜单、发送 toggle、任务筛选
```

v1.2 已经把 mobile 从“移动端控制台”推进到“手机 App 风格工作台”。下一版不建议继续大改页面结构，而应该进入：

```text
真实试用稳定性 + 前端代码可维护性增强
```

核心原因：

- mobile 页面功能越来越多，`backend/mobile.py` 已经很长。
- 当前 UI 已经可用，继续堆功能会增加维护难度。
- 实际试用时最影响体验的，不再是“有没有按钮”，而是状态是否能保持、错误是否可理解、运行中是否自动刷新、操作是否容易恢复。

---

## 2. v1.3 总目标

版本目标：

```text
v1.3.x：Mobile 试用稳定性与可维护性增强
```

最终目标：

```text
1. 用户刷新页面后，Tab、筛选、当前会话、发送模式能保留。
2. RUNNING/PENDING 状态能自动刷新，不需要频繁手点刷新。
3. 错误提示从 raw error 变成可操作的恢复建议。
4. mobile 前端代码从一个巨大字符串继续拆分，降低后续维护成本。
5. 不新增复杂后端能力，不破坏 Runner/codex exec 主链路。
```

---

## 3. 重要约束

必须遵守：

```text
1. 不引入 Vue / React / Svelte。
2. 不引入前端构建工具。
3. 不引入新依赖。
4. 不做多用户权限系统。
5. 不做公网部署。
6. 不做 SSE。
7. 不做审批 UI。
8. 不做 diff UI。
9. 不修改 Runner/codex exec 主链路语义。
10. 不修改 App Server Bridge sidecar 架构。
11. 不把 poc/app_server/app_server_bridge.py 合并进 backend/main.py。
12. 保留现有 API 和 smoke 脚本。
13. 每阶段都必须 pytest -q 通过。
```

---

## 4. 分阶段计划

建议分三阶段执行：

```text
v1.3.0：Mobile 状态持久化与自动刷新
v1.3.1：错误恢复与空状态优化
v1.3.2：mobile.py 前端代码治理
```

不要一次性执行全部 v1.3。

---

# 5. v1.3.0：Mobile 状态持久化与自动刷新

## 5.1 目标

解决真实试用时最常见的问题：刷新页面、切换页面、任务运行中时，用户不想重新找状态，也不想频繁手点刷新。

## 5.2 需要持久化的 UI 状态

使用 `localStorage` 保存：

```text
1. 当前 Tab：home / tasks / app / settings
2. 任务状态筛选：taskStatusFilter
3. AppThread 状态筛选：appThreadStatusFilter
4. 是否显示 archived：appIncludeArchived
5. 当前 selectedAppThreadId
6. App 发送模式：async / sync
7. Token 已经在 localStorage，继续保留
```

建议 key 命名：

```text
mobile.activeTab
mobile.taskStatusFilter
mobile.appThreadStatusFilter
mobile.appIncludeArchived
mobile.selectedAppThreadId
mobile.appSendMode
```

## 5.3 启动时恢复状态

页面加载时：

```text
1. 读取 activeTab，默认 home。
2. 恢复 taskStatusFilter。
3. 恢复 appThreadStatusFilter。
4. 恢复 appIncludeArchived。
5. 恢复 appSendMode。
6. loadAll() 后，如果 selectedAppThreadId 存在，尝试恢复当前会话。
```

恢复 selectedAppThreadId 时：

```text
1. 如果该 thread 在 appThreadsCache 中，直接选中。
2. 如果不在当前筛选结果中，仍保留 selectedAppThreadId，但提示“当前会话不在当前筛选结果中”。
3. 如果 GET /app-threads/{id} 可用，可以尝试读取详情；如果暂不使用该 API，也可以等用户从列表切换。
```

## 5.4 自动刷新策略

不要做 SSE。

使用轻量轮询：

### 任务 Tab 自动刷新

当任务列表中存在：

```text
PENDING / RUNNING
```

每 5 秒刷新一次 tasks。

要求：

```text
1. 只在当前 Tab 为 home 或 tasks 时刷新。
2. 没有 PENDING/RUNNING 时停止自动刷新。
3. 刷新失败 toast warning，不要刷屏。
4. 避免多重 setInterval 泄漏。
```

### App 会话自动刷新

当前已有异步 AppTurn 轮询。v1.3.0 要整理为统一策略：

```text
1. selectedAppTurnId 正在 PENDING/RUNNING：继续轮询该 turn。
2. 当前会话中有 PENDING/RUNNING turn，但 selectedAppTurnId 丢失：自动选中最近一个活动 turn 并轮询。
3. terminal 后停止轮询。
```

## 5.5 页面可见性优化

使用 `document.visibilityState`：

```text
1. 页面隐藏时暂停非必要刷新。
2. 页面恢复可见时立即 loadAll()。
3. 不影响正在轮询的关键 AppTurn，但要避免重复 interval。
```

## 5.6 v1.3.0 验收标准

```text
1. 刷新页面后，仍停留在上次 Tab。
2. 任务筛选状态能保留。
3. App 发送模式能保留。
4. 当前 AppThread 尽量保留。
5. 存在 RUNNING/PENDING 任务时会自动刷新。
6. 没有运行中任务时不会无意义轮询。
7. 异步 AppTurn 轮询不重复启动多个 interval。
8. pytest -q 通过。
```

## 5.7 v1.3.0 测试要求

修改 `tests/test_ui.py`，静态覆盖：

```text
- mobile.activeTab
- mobile.taskStatusFilter
- mobile.appThreadStatusFilter
- mobile.appIncludeArchived
- mobile.selectedAppThreadId
- mobile.appSendMode
- document.visibilityState
- startTaskAutoRefresh / stopTaskAutoRefresh 或等价函数
- clearInterval 防重复
```

---

# 6. v1.3.1：错误恢复与空状态优化

## 6.1 目标

把错误从“技术错误文本”变成“用户知道下一步怎么做”。

## 6.2 错误分类

新增前端 helper：

```javascript
function classifyError(errorText) { ... }
```

至少识别：

```text
1. 401 / invalid API token
2. Bridge 不可用 / 503
3. unknown bridge thread id
4. app turn conflict / 409
5. app thread is closed
6. network failed / fetch failed
7. task cancel not allowed / terminal task
```

## 6.3 错误展示

新增统一错误 Sheet：

```javascript
showErrorSheet(title, message, actions)
```

不同错误给不同操作建议：

### Token 错误

```text
提示：Token 无效或未保存
操作：跳转“我的”页，聚焦 Token 输入框
```

### Bridge 不可用

```text
提示：App Server Bridge 未启动或配置错误
操作：打开“我的”页，展示启动命令
```

### unknown bridge thread id

当前已有 `showStaleBridgeThreadSheet()`，保留并完善。

### app turn conflict

```text
提示：当前会话已有一个异步 turn 正在运行
操作：刷新当前 Turn / 取消当前 Turn
```

## 6.4 空状态优化

每个空状态都必须有下一步动作：

任务空状态：

```text
还没有任务
按钮：新建任务
```

Runner 空状态：

```text
没有在线 Runner
说明：启动 runner/runner.py 或 scripts/start.bat runner
```

会话空状态：

```text
还没有会话
按钮：新建会话
```

Bridge 异常空状态：

```text
Bridge 不可用
按钮：查看启动命令
```

## 6.5 v1.3.1 验收标准

```text
1. 常见错误都有可读解释。
2. 用户看到错误后知道下一步动作。
3. raw error 仍可在详情里查看。
4. 空状态不再只是“暂无”。
5. pytest -q 通过。
```

---

# 7. v1.3.2：mobile.py 前端代码治理

## 7.1 目标

当前 `backend/mobile.py` 已包含大量 CSS/HTML/JS。继续增长会变得难维护。

v1.3.2 目标是在不引入前端工程化的前提下，让代码更可维护。

## 7.2 推荐方案 A：继续 Python 函数化拆分

如果暂时不想引入静态文件路由，可以先拆函数：

```python
def mobile_head() -> str

def mobile_body() -> str

def mobile_home_tab() -> str

def mobile_tasks_tab() -> str

def mobile_app_tab() -> str

def mobile_settings_tab() -> str

def mobile_sheet() -> str

def mobile_nav() -> str

def mobile_script() -> str
```

进一步把 JS 字符串拆成：

```python
def mobile_script_core() -> str

def mobile_script_state() -> str

def mobile_script_home() -> str

def mobile_script_tasks() -> str

def mobile_script_app() -> str

def mobile_script_events() -> str
```

## 7.3 推荐方案 B：拆成静态 CSS/JS 文件

如果愿意做一次更干净的治理，可以新增：

```text
backend/static/mobile.css
backend/static/mobile.js
```

然后 FastAPI 挂载静态文件：

```python
from fastapi.staticfiles import StaticFiles
app.mount('/static', StaticFiles(directory='backend/static'), name='static')
```

HTML 中引用：

```html
<link rel="stylesheet" href="/static/mobile.css">
<script src="/static/mobile.js"></script>
```

注意：

```text
1. 不引入构建工具。
2. 不引入 npm。
3. 只是拆静态文件。
4. 要确保 /mobile 在局域网访问时仍正常。
```

## 7.4 推荐执行策略

优先采用方案 A。

原因：

```text
1. 改动小。
2. 不涉及 StaticFiles 挂载。
3. 风险低。
4. 当前测试更容易适配。
```

如果 v1.3.2 之后 mobile.py 仍然过长，再考虑方案 B。

## 7.5 v1.3.2 验收标准

```text
1. mobile.py 结构更清晰。
2. 每个 Tab 的 HTML 有独立函数。
3. JS 至少按 core/home/tasks/app 分段。
4. 页面功能不丢失。
5. tests/test_ui.py 不因过度脆弱而频繁失败。
6. pytest -q 通过。
```

---

## 8. 本次不做

v1.3 不做：

```text
1. 不做 Vue/React。
2. 不做前端构建。
3. 不做 SSE。
4. 不做 WebSocket。
5. 不做审批 UI。
6. 不做 diff UI。
7. 不做多用户权限。
8. 不做公网部署。
9. 不新增复杂后端 API。
10. 不改 Runner/codex exec 主链路。
```

---

## 9. Codex 执行建议

建议先执行：

```text
v1.3.0：Mobile 状态持久化与自动刷新
```

不要一次执行 v1.3.0 ~ v1.3.2。

### v1.3.0 允许修改

```text
backend/mobile.py
tests/test_ui.py
```

### v1.3.0 原则上不要修改

```text
backend/main.py
backend/models.py
backend/schemas.py
backend/services/
runner/
poc/app_server/
scripts/smoke_app_server_flow.py
```

### v1.3.0 完成后输出格式

```text
本次完成：
-

修改文件：
-

验证结果：
- python -m compileall backend runner scripts poc/app_server
- pytest -q

风险与未完成项：
-

后续建议：
-
```

---

## 10. 最终目标

v1.3 完成后，mobile 不仅“看起来像 App”，还应该具备真实试用所需的稳定性：

```text
状态能保留
运行中能自动刷新
错误能指导恢复
代码能继续维护
```
