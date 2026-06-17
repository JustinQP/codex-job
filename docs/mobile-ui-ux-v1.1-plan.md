# v1.1 Mobile 控制台 UI/UX 重构开发计划

## 1. 背景

当前 `v1.0.0` 已完成 Codex Remote Runner + App Server Sidecar 本地控制台的功能收口：

- 主线 Runner/codex exec 任务链路可用。
- App Server sidecar 会话链路可用。
- mobile 页面已覆盖任务、Runner、AppThread、AppTurn、异步发送、取消、reopen、recover-stale、筛选、archived 清理等操作。

但当前 mobile 页面仍然是典型的“工程调试页”：

- 所有功能堆在一个长页面里。
- 任务、Runner、App Server 会话混在一起。
- App Server 区域按钮过多，主次不清。
- 用户不知道当前应该先做什么、下一步点哪里。
- 状态、错误、结果、调试输出分散在不同区域。
- JSON 输出偏多，不适合手机阅读。
- 移动端单手操作体验差。

`v1.1` 的目标不是继续新增后端能力，而是把 mobile 页面从“功能堆叠页”重构成“可长期使用的手机控制台”。

---

## 2. 总目标

版本目标：

```text
v1.1.x：Mobile 控制台 UI/UX 重构
```

最终效果：

```text
1. 页面从长表单改为底部 Tab 工作台。
2. 任务、App 会话、Runner、设置分区清晰。
3. App Server 会话从调试按钮区改为会话式操作区。
4. 任务创建流程默认只暴露常用字段，高级参数折叠。
5. 状态、错误、成功反馈使用统一 badge / toast / loading。
6. 调试 JSON 保留但默认弱化或折叠。
7. mobile 页面更适合手机单手使用。
8. 不引入 Vue/React，不引入前端工程化。
9. 不改 Runner/codex exec 主链路。
10. 不改 App Server API 语义。
```

---

## 3. 重要约束

本次 UI/UX 重构必须遵守：

```text
1. 不引入 Vue / React / Svelte 等前端框架。
2. 不引入前端构建工具。
3. 不引入新依赖。
4. 不修改 Runner/codex exec 主链路语义。
5. 不修改 App Server Bridge sidecar 架构。
6. 不把 poc/app_server/app_server_bridge.py 合并进 backend/main.py。
7. 不做 SSE。
8. 不做审批 UI。
9. 不做 diff UI。
10. 不做登录/多用户权限系统。
11. 不做公网部署相关能力。
12. 保留现有 API。
13. 保留现有 smoke 脚本。
14. 保证 pytest -q 继续通过。
```

---

## 4. 版本拆分

建议分三步推进，不要一次性把所有交互都重写完。

```text
v1.1.0：Mobile 布局与视觉系统重构
v1.1.1：App 会话体验优化
v1.1.2：任务创建与任务列表体验优化
```

---

# v1.1.0：Mobile 布局与视觉系统重构

## 目标

先解决“丑”和“一坨屎”的根因：页面结构混乱、按钮堆叠、主次不清。

本版本只做：

```text
1. 四 Tab 布局。
2. 统一视觉系统。
3. 卡片化。
4. 状态 badge。
5. toast 提示。
6. 按钮 loading。
7. 保留现有功能入口。
```

不要求在本版本完成聊天气泡、任务详情抽屉等深度交互。

## 4.1 页面结构

将 mobile 页面改为底部 Tab：

```text
1. 任务
2. App 会话
3. Runner
4. 设置
```

### 任务 Tab

用途：主线 Runner/codex exec 任务链路。

包含：

```text
- 快速创建任务卡片
- 最近任务列表
- 任务详情 / log / result / diff 入口
```

### App 会话 Tab

用途：App Server sidecar 会话链路。

包含：

```text
- Bridge 状态
- 当前 AppThread
- AppThread 列表
- AppTurn 操作区
- final / events / debug 输出入口
```

### Runner Tab

用途：查看 Runner 状态。

包含：

```text
- Runner 列表
- 在线/离线状态
- hostname / pid / supported_models
- 刷新按钮
```

### 设置 Tab

用途：低频配置和说明。

包含：

```text
- API Token
- 当前版本
- Backend 地址说明
- Bridge sidecar 说明
- Smoke 命令提示
- 当前限制
```

## 4.2 视觉系统

统一 CSS：

```text
- 页面背景：浅灰
- 内容区域：白色卡片
- 卡片圆角：12px
- 主按钮：蓝色
- 次按钮：灰色
- 危险按钮：红色
- 状态 badge：统一颜色
- 输入框：统一高度、圆角、边框
- 底部 Tab：固定在底部
- Toast：固定在顶部或底部
```

建议状态颜色：

```text
ACTIVE / SUCCESS：绿色
PENDING / RUNNING：蓝色
ERROR / FAILED：红色
CLOSED / CANCELLED：灰色
WARNING：橙色
```

## 4.3 Toast 反馈

新增统一 toast：

```javascript
showToast(message, type = "info")
```

类型：

```text
success
error
info
warning
```

替代大量直接写 `pre` 的操作反馈。

保留 `appOutput` / debug output，但默认作为“调试输出”存在，不作为主要反馈入口。

## 4.4 Loading 状态

新增通用按钮 loading helper：

```javascript
async function withButtonLoading(button, loadingText, fn) { ... }
```

要求：

```text
1. 点击后按钮 disabled。
2. 文案变为“处理中...”或传入 loadingText。
3. 成功后恢复。
4. 失败后恢复并 toast error。
```

覆盖关键操作：

```text
- 创建任务
- 刷新任务
- 取消任务
- 检查 Bridge
- 创建 AppThread
- 同步发送 AppTurn
- 异步发送 AppTurn
- 取消 AppTurn
- reopen AppThread
- recover stale
- cleanup CLOSED / ERROR
```

## 4.5 高级参数折叠

任务创建区域默认只显示：

```text
- 项目
- 任务类型
- Prompt
- 提交按钮
```

高级参数折叠：

```text
- Runner
- model
- reasoning_effort
- sandbox
- timeout_seconds
```

可以使用原生 `<details><summary>高级参数</summary>...</details>`。

## 4.6 调试输出折叠

App 会话区的 raw JSON / debug output 默认折叠：

```html
<details>
  <summary>调试输出</summary>
  <pre id="appOutput"></pre>
</details>
```

任务详情的 log/result/diff 仍保留入口，不要求本版本重做 diff UI。

## 4.7 代码组织

优先保持简单，不引入静态文件路由。

建议在 `backend/mobile.py` 内部拆分函数：

```python
def mobile_console() -> str:
    return f"""
    {mobile_head()}
    {mobile_body()}
    {mobile_script()}
    """


def mobile_head() -> str:
    ...


def mobile_body() -> str:
    ...


def mobile_script() -> str:
    ...
```

如果当前 `mobile.py` 太长，允许做内部函数化拆分，但不要改变 API。

## 4.8 v1.1.0 验收标准

完成后应满足：

```text
1. 打开 /mobile 后不再是一长页按钮堆叠。
2. 底部 Tab 可以切换：任务 / App 会话 / Runner / 设置。
3. 任务创建、App 会话、Runner 状态分区清晰。
4. 所有状态都有 badge。
5. 关键操作有 toast 提示。
6. 关键按钮有 loading/disabled 状态。
7. 高级任务参数默认折叠。
8. 调试输出默认折叠。
9. 原有功能入口不丢失。
10. pytest -q 通过。
11. smoke_app_server_flow.py 不受影响。
```

---

# v1.1.1：App 会话体验优化

## 目标

把 App Server 会话从“调试按钮区”优化成“会话操作台”。

## 5.1 当前 AppThread 固定展示

App 会话 Tab 顶部固定展示当前 AppThread：

```text
- id
- title
- status badge
- turn_count
- latest final preview
- last_error
```

操作：

```text
- 新建
- 重开
- 关闭
- 恢复卡住 turn
```

低频操作放到更多/折叠区域。

## 5.2 AppThread 列表折叠

AppThread 列表默认折叠：

```html
<details>
  <summary>AppThread 列表</summary>
  ...
</details>
```

筛选项保留：

```text
- 状态筛选
- 显示 archived
- 清理 CLOSED
- 清理 ERROR
```

## 5.3 AppTurn 聊天气泡

将 AppTurn 列表改为会话形式：

```text
用户消息：右侧气泡
助手结果：左侧气泡
RUNNING/PENDING：蓝色 loading 卡片
FAILED：红色错误卡片
CANCELLED：灰色卡片
```

每个 AppTurn 展示：

```text
- user_message
- assistant_final 或 error_message
- status badge
- duration_seconds
- created_at
```

## 5.4 底部固定输入栏

App 会话 Tab 底部固定输入区：

```text
textarea message
同步发送
异步发送
```

要求：

```text
1. 输入区在 App 会话 Tab 底部固定。
2. 异步发送后自动清空输入框。
3. 异步发送后开始轮询。
4. terminal 状态后停止轮询。
```

## 5.5 event summary 折叠展示

event summary 不再抢主视图，放到：

```html
<details>
  <summary>事件摘要</summary>
  total_events
  has_error
  event_type_counts
  assistant_text_preview
  errors
</details>
```

## 5.6 v1.1.1 验收标准

```text
1. App 会话 Tab 看起来像会话控制台，不像按钮仓库。
2. 当前 AppThread 状态清楚。
3. AppTurn 以气泡/卡片方式展示。
4. 异步 turn 运行状态明显。
5. 错误状态清晰。
6. event summary 不干扰主操作。
7. 原 App Server API 不变。
8. pytest -q 通过。
```

---

# v1.1.2：任务创建与任务列表体验优化

## 目标

优化主线 Runner/codex exec 任务体验。

## 6.1 快速创建任务卡片

任务 Tab 顶部是快速创建任务卡片：

```text
- 项目
- 任务类型
- Prompt
- 提交任务
```

高级参数折叠：

```text
- Runner
- model
- reasoning_effort
- sandbox
- timeout_seconds
```

## 6.2 最近任务列表卡片化

每个任务卡片展示：

```text
- id
- status badge
- task_type
- project_id
- runner_id / assigned_runner_id
- model
- created_at / updated_at
```

操作：

```text
- 详情
- log
- result
- diff
- 取消
```

危险操作必须 confirm。

## 6.3 任务详情卡片

任务详情不直接堆在页面中间，改成详情卡：

```text
- 基本信息
- 状态
- 参数
- 操作链接
- log/result 预览
```

本版本不做 diff UI，只保留 diff 链接。

## 6.4 Runner 信息弱化

任务 Tab 中不堆 Runner 列表，只在任务卡片显示关联 Runner。

完整 Runner 状态放到 Runner Tab。

## 6.5 v1.1.2 验收标准

```text
1. 创建任务流程更短。
2. 高级参数不会干扰普通使用。
3. 最近任务列表可读性明显提升。
4. 任务详情层次清楚。
5. Runner 状态不再和任务创建混在一起。
6. 主线 Runner/codex exec API 不变。
7. pytest -q 通过。
```

---

## 7. 测试计划

### 7.1 UI 静态测试

修改：

```text
tests/test_ui.py
```

覆盖：

```text
- 页面包含四个 Tab：任务 / App 会话 / Runner / 设置
- 页面包含 bottom nav
- 页面包含 toast 容器
- 页面包含 status badge 样式
- 页面包含高级参数折叠
- 页面包含调试输出折叠
- 页面保留现有关键 API 调用字符串
- 动态 innerHTML 字段继续使用 escapeHtml
```

### 7.2 文档测试

修改或新增：

```text
tests/test_docs.py
```

覆盖：

```text
- docs/mobile-ui-ux-v1.1-plan.md 存在
- README 或 docs 中能找到 v1.1 UI/UX 计划入口
```

### 7.3 回归测试

必须保持：

```powershell
python -m compileall backend runner scripts poc/app_server
pytest -q
```

如果 smoke 是手工验收，不强制在自动测试中启动真实 Bridge。

---

## 8. 不做事项

v1.1 明确不做：

```text
1. 不做 Vue/React。
2. 不做前端工程化。
3. 不做登录系统。
4. 不做多用户权限。
5. 不做 SSE。
6. 不做审批 UI。
7. 不做 diff UI。
8. 不做复杂图表。
9. 不修改 Runner 主链路。
10. 不修改 App Server API 语义。
11. 不修改 Bridge sidecar 架构。
12. 不做公网部署。
```

---

## 9. Codex 执行建议

建议先执行：

```text
v1.1.0：Mobile 布局与视觉系统重构
```

不要一次性做完 v1.1.0 ~ v1.1.2。

### v1.1.0 Codex 执行范围

允许修改：

```text
backend/mobile.py
tests/test_ui.py
tests/test_docs.py
README.md
```

允许新增：

```text
docs/mobile-ui-ux-v1.1-plan.md
```

原则上不要修改：

```text
backend/main.py
backend/models.py
backend/schemas.py
backend/services/
runner/
poc/app_server/
scripts/smoke_app_server_flow.py
```

### v1.1.0 完成后输出格式

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

v1.1 完成后，mobile 应该从：

```text
工程调试按钮堆叠页
```

变成：

```text
手机可用的 Codex Remote Runner 工作台
```

重点不是“炫”，而是：

```text
清晰、可操作、状态明确、反馈及时、手机上能长期用。
```
