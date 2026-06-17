# v1.5 Mobile 会话页核心体验专项开发计划

## 1. 背景

当前 mobile 已完成：

```text
v1.0.0：稳定版收口、README/docs、smoke 验收矩阵
v1.1.x：第一轮 UI/UX 重构，完成 Tab、卡片、toast、气泡会话
v1.2.x：App 化信息架构，完成 首页 / 任务 / 会话 / 我的、Sheet、更多菜单、发送 toggle
v1.3.x：试用稳定性增强，完成状态持久化、自动刷新、错误分类、空状态优化
v1.4.x：设计系统与交互体系，完成 CSS tokens、组件规范、首页/任务/会话/我的结构优化、mobile.py 函数拆分
```

现在页面整体已经从“工程调试页”进化成“移动端工作台”。但这个应用的核心不是首页，也不是任务列表，而是：

```text
App Server 会话页
```

用户真正想做的是：

```text
打开手机 -> 进入会话 -> 选择/创建会话 -> 输入目标 -> 发送 -> 等待 Codex 回复 -> 继续追问/调整 -> 必要时恢复失败
```

所以 v1.5 不再平均优化所有页面，而是集中打磨“会话页核心体验”。

---

## 2. v1.5 总目标

版本目标：

```text
v1.5.x：App Server 会话页核心体验专项优化
```

最终目标：

```text
1. 会话页成为 mobile 的核心主页面。
2. 用户无需理解 AppThread / AppTurn / Bridge 这些工程概念，也能完成对话。
3. 选择会话、新建会话、发送消息、查看回复、失败恢复的路径更短。
4. 运行中状态明确，不会让用户误以为卡死。
5. 回复内容更好读，失败内容更好恢复。
6. 调试能力保留，但彻底退到二级入口。
```

判断标准：

```text
用户打开“会话”页后，第一眼看到的是当前对话和输入框，而不是一堆系统按钮。
用户知道当前能不能发送、为什么不能发送、发送后发生了什么。
失败后用户知道下一步是重试、取消、重开，还是查看 Bridge。
```

---

## 3. 总体约束

必须遵守：

```text
1. 不引入 Vue / React / Svelte。
2. 不引入 npm / 前端构建。
3. 不新增复杂后端 API。
4. 不修改 Runner/codex exec 主链路。
5. 不修改 App Server Bridge sidecar 架构。
6. 不把 poc/app_server/app_server_bridge.py 合并进 backend/main.py。
7. 不做 SSE / WebSocket。
8. 不做审批 UI。
9. 不做 diff UI。
10. 不做多用户系统。
11. 保留现有 AppThread / AppTurn API。
12. 保留现有 smoke 脚本。
13. 每阶段必须 pytest -q 通过。
14. 不自动 commit。
15. 不 push。
```

---

## 4. 会话页当前主要问题

从产品视角看，当前会话页仍有以下问题：

```text
1. 当前会话区信息还偏工程化，AppThread/AppTurn 概念仍然明显。
2. 新建会话和切换会话在同一个 Sheet 中，功能可用但层次还不够自然。
3. 输入区可用，但缺少“当前上下文/发送模式/运行状态”的明确反馈。
4. 消息气泡已有，但助手回复的阅读体验还不够好，长回复、失败、运行中都还可以优化。
5. 失败恢复已经有入口，但没有形成“失败卡片 -> 重试/复制/重开”的自然闭环。
6. 会话更多菜单虽然分组了，但仍然偏工程维护，普通用户入口还可以再瘦身。
7. 调试入口仍保留较多隐藏按钮，后续维护上容易反弹成按钮仓库。
```

---

## 5. v1.5 分阶段计划

建议拆成四个小版本：

```text
v1.5.0：会话页主路径重构
v1.5.1：消息流阅读与运行中体验优化
v1.5.2：失败恢复与重试闭环
v1.5.3：会话管理与调试入口收口
```

不要一次执行全部 v1.5。

---

# 6. v1.5.0：会话页主路径重构

## 6.1 目标

让“会话”页打开后，用户第一眼看到的就是：

```text
当前会话是谁
现在能不能发送
输入框在哪里
下一步该做什么
```

而不是 AppThread 元信息和工程按钮。

## 6.2 页面结构调整

当前结构保持四 Tab 不变：

```text
首页 / 任务 / 会话 / 我的
```

但会话 Tab 内部重构为三段：

```text
1. 会话顶部栏 session-header
2. 消息流 message-list
3. 底部输入 composer
```

推荐结构：

```html
<section id="tab-app" class="tab-page page app-console" data-tab-page="app">
  <div class="session-header">...</div>
  <div class="message-list">...</div>
  <div class="session-composer">...</div>
</section>
```

如果暂时不想大改 DOM 名称，可以保留现有 id，但补充更清晰的 class。

## 6.3 会话顶部栏设计

顶部栏展示：

```text
左侧：会话标题
副标题：状态 + turns 数 + 最近更新时间
右侧：切换 / 更多
```

不要默认展示：

```text
bridge_thread_id
project_id
last_error 全文
```

这些放到详情 Sheet。

无会话时顶部栏展示：

```text
标题：开始一次 Codex 会话
说明：选择或新建会话后，就可以连续发送消息。
主操作：新建会话
次操作：选择已有
```

## 6.4 新建会话入口拆分

当前“切换会话”Sheet 同时承担新建和选择。v1.5.0 建议拆成两层：

```text
会话顶部：
- 新建会话
- 切换会话
```

实现可以仍然使用同一个 Sheet，但视觉上拆为：

```text
1. 快速新建
   - 标题输入
   - 项目选择
   - 创建按钮

2. 最近会话
   - 列表
   - 筛选折叠
```

默认优先展示“最近会话”，新建表单可以折叠或放在顶部紧凑卡片。

## 6.5 输入区状态

输入区必须明确显示当前状态：

```text
可发送：输入消息后即可发送
未选择会话：请先新建或选择会话
会话关闭：当前会话已关闭，请重开后继续
Turn 运行中：正在等待回复，可以继续编辑，但暂时不能发送
Bridge 异常：Bridge 不可用，发送可能失败
```

要求：

```text
1. 发送按钮禁用时必须有原因。
2. 输入框禁用/只读时必须有原因。
3. 运行中时发送按钮 disabled，但输入框可以继续编辑。
```

## 6.6 发送模式文案

继续保留底层同步/异步 API，但对用户使用更自然的文案：

```text
快速发送：后台执行，适合长任务
等待回复：当前页面等待完成，适合短问答
```

会话页默认：

```text
快速发送
```

UI 上建议用小型 segmented/toggle，不要大 checkbox。

第一版可以保留 checkbox，但文案必须为：

```text
快速发送
```

切换后显示：

```text
等待回复
```

## 6.7 v1.5.0 验收标准

```text
1. 会话页首屏只有：会话顶部、消息流、输入区。
2. 无会话状态有明确新建/选择入口。
3. 发送按钮禁用时有明确原因。
4. 发送模式文案是“快速发送/等待回复”，不直接暴露“异步/同步”为主文案。
5. 调试按钮不出现在主屏。
6. pytest -q 通过。
```

---

# 7. v1.5.1：消息流阅读与运行中体验优化

## 7.1 目标

优化消息流，让回复更像可阅读的结果，而不是数据库记录。

## 7.2 用户消息气泡

用户气泡显示：

```text
消息正文
发送时间/状态弱化显示
```

不要默认显示：

```text
turn id
bridge_turn_id
完整 meta
```

## 7.3 助手回复气泡

助手回复气泡显示：

```text
assistant_final / error_message 摘要
状态 badge
耗时
```

对于长回复：

```text
1. 默认展示前 800～1200 字。
2. 提供“展开全文”。
3. 展开后可“收起”。
```

不要让超长回复撑爆页面。

## 7.4 运行中气泡

当 AppTurn 为 PENDING/RUNNING：

```text
显示一个 assistant loading 气泡：
- 正在思考 / 正在执行
- 已等待 xx 秒，如有 duration_seconds
- 取消当前 Turn 小按钮
```

运行中顶部状态条同步显示。

## 7.5 消息流自动滚动

发送消息或收到新回复后：

```text
1. 如果用户当前在消息流底部，自动滚动到底部。
2. 如果用户正在向上看历史，不强行滚动。
3. 可以先简化实现：发送后滚到底部，刷新后不强制滚动。
```

## 7.6 当前 Turn 选择弱化

当前 `selectedAppTurnId` 是工程概念，不应该强展示。

建议：

```text
1. 点击气泡才选中 turn。
2. 选中后打开 Turn 详情 Sheet。
3. 主屏只显示当前运行中的状态，不显示 selectedAppTurnId。
```

## 7.7 v1.5.1 验收标准

```text
1. 消息流读起来像对话。
2. 长回复不会撑爆页面。
3. 运行中状态明显。
4. 用户知道是否可以取消当前 Turn。
5. 点击气泡可看详情，但详情不干扰主阅读。
6. pytest -q 通过。
```

---

# 8. v1.5.2：失败恢复与重试闭环

## 8.1 目标

把失败从“报错”变成“可恢复”。

## 8.2 失败气泡设计

失败气泡应显示：

```text
这次回复失败
简短原因
建议操作
```

操作按钮：

```text
复制重试
查看错误
重开会话
```

不同错误建议不同：

### unknown bridge thread id

```text
说明：Bridge 重启后旧会话失效
主操作：重开会话
次操作：查看错误
```

### app_turn_conflict / 409

```text
说明：已有回复正在运行
主操作：刷新当前回复
次操作：取消当前 Turn
```

### Bridge 不可用

```text
说明：Bridge sidecar 没启动或不可用
主操作：查看启动提示
次操作：稍后重试
```

### Token 错误

```text
说明：Token 无效
主操作：去我的页保存 Token
```

## 8.3 重试策略

第一版不要做复杂自动重放。

建议实现：

```text
复制重试：把该 turn 的 user_message 填回输入框
```

用户确认后再手动发送。

后续可选：

```text
一键重试：复制 user_message + 发送快速模式
```

但 v1.5.2 不强制。

## 8.4 失败后的输入区行为

失败后：

```text
1. 输入区可用。
2. appWaiting 清空。
3. 发送按钮恢复。
4. 当前失败消息提供恢复操作。
```

## 8.5 v1.5.2 验收标准

```text
1. FAILED turn 在主消息流中显示恢复卡片。
2. 能把失败 turn 的 user_message 复制回输入框。
3. unknown bridge thread id 能引导重开会话。
4. Bridge 不可用能引导查看启动提示。
5. 错误详情仍可查看，但默认折叠。
6. pytest -q 通过。
```

---

# 9. v1.5.3：会话管理与调试入口收口

## 9.1 目标

会话核心页不能再次变成按钮仓库。v1.5.3 专门收口二级入口。

## 9.2 会话更多菜单分层

会话更多 Sheet 分为：

```text
1. 常用
   - 刷新会话
   - 查看最终回复
   - 切换会话

2. 会话管理
   - 重开会话
   - 关闭会话

3. 调试与维护（折叠）
   - 查看事件摘要
   - 查看调试输出
   - 检查 Bridge
   - 恢复卡住 Turn

4. 清理归档（折叠）
   - 清理 CLOSED
   - 清理 ERROR
```

危险操作放底部，必须 confirm。

## 9.3 会话列表优化

会话列表 Sheet 中：

```text
1. 最近会话优先。
2. 筛选折叠。
3. archived 默认不显示。
4. 当前选中会话高亮。
5. 关闭/错误会话使用弱化样式。
```

## 9.4 会话标题显示优化

如果 title 为空：

```text
显示：未命名会话 #id
```

如果 title 太长：

```text
主屏截断，详情里展示完整标题。
```

## 9.5 调试入口收口

主屏不出现：

```text
App Events
Bridge Health
raw summary
bridge_turn_id
recover stale
cleanup CLOSED/ERROR
```

这些只允许出现在：

```text
会话更多 -> 调试与维护
我的 -> 维护操作
```

## 9.6 v1.5.3 验收标准

```text
1. 主会话页没有工程调试按钮。
2. 会话更多菜单分层清楚。
3. 会话列表更像聊天列表。
4. 维护操作不会干扰普通发送消息。
5. pytest -q 通过。
```

---

## 10. 代码范围

v1.5 主要允许修改：

```text
backend/mobile.py
tests/test_ui.py
```

可选修改：

```text
docs/mobile-v1.5-app-session-core-plan.md
README.md（如果需要补充 Mobile UI 当前迭代说明）
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

---

## 11. 测试计划

继续用静态 UI 测试为主，但不要过度依赖细碎文案。

`tests/test_ui.py` 应覆盖：

```text
1. 会话页主结构：session-header / message-list / session-composer
2. 无会话状态：新建会话 / 选择已有
3. 发送模式：快速发送 / 等待回复
4. 输入区状态：未选择、可发送、运行中、已关闭
5. 运行中 Turn：inline status / 取消当前 Turn
6. 失败 Turn：复制重试 / 查看错误 / 重开会话
7. 会话更多菜单分组：常用 / 会话管理 / 调试与维护 / 清理归档
8. 调试入口仍存在但不在主屏显眼区域
9. 关键 API 仍存在：/app-threads、/turns、/turns/async、/app-turns/{id}/cancel、/events、/reopen
10. escapeHtml 仍覆盖动态字段
```

每阶段必须运行：

```powershell
python -m compileall backend runner scripts poc/app_server
pytest -q
```

---

## 12. 本次不做

v1.5 不做：

```text
1. 不做 SSE。
2. 不做 WebSocket。
3. 不做真正流式输出。
4. 不做审批 UI。
5. 不做 diff UI。
6. 不做多用户权限。
7. 不做复杂后端队列。
8. 不做真正强杀 App Server turn。
9. 不引入前端框架。
10. 不引入 npm。
```

---

## 13. Codex 执行建议

建议先执行：

```text
v1.5.0：会话页主路径重构
```

不要一次性执行 v1.5.0 ~ v1.5.3。

### v1.5.0 指令摘要

```text
请阅读 docs/mobile-v1.5-app-session-core-plan.md，先执行 v1.5.0：会话页主路径重构。

目标：
1. 会话页首屏聚焦：当前会话、消息流、输入区。
2. 无会话状态有明确新建/选择入口。
3. 会话顶部栏展示标题、状态、turns、更新时间、切换/更多。
4. 输入区清晰显示当前能否发送及原因。
5. 发送模式文案使用“快速发送 / 等待回复”。
6. 调试按钮不出现在主屏。

约束：
- 不改后端 API。
- 不改 Runner 主链路。
- 不改 App Server Bridge 架构。
- 不引入前端框架。
- 不自动 commit。
- 不 push。

完成后运行：
python -m compileall backend runner scripts poc/app_server
pytest -q
```

---

## 14. 最终目标

v1.5 完成后，会话页应该从：

```text
具备聊天样式的 App Server 控制面板
```

升级为：

```text
真正以会话为中心的 Codex 手机端工作区
```

核心体验应该是：

```text
选会话很自然
发消息很清楚
等回复不焦虑
失败后能恢复
调试不打扰主流程
```
