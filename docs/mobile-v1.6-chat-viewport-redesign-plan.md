# v1.6 Mobile 会话页聊天视口重构开发计划

## 1. 背景

v1.5 已经完成会话页核心体验专项优化：

```text
1. 会话页 DOM 已拆成 session-header / message-list / session-composer。
2. 支持快速发送 / 等待回复。
3. 支持长回复折叠、展开全文、失败恢复、复制重试、运行中取消。
4. 会话更多菜单已经分组。
5. 调试入口已经后退到二级入口。
```

但从真实手机截图看，v1.5 的实际效果仍然不理想：

```text
1. 顶部会话卡片太厚，挤压消息区。
2. 消息流不是视觉主角，被顶部卡和底部输入区夹住。
3. 底部输入区太像表单，不像聊天输入栏。
4. “切换会话 / 更多”仍然是大按钮，顶部操作太重。
5. 当前布局仍是普通页面流 + sticky composer，不是真正聊天 App 的 viewport 布局。
6. 页面中间内容被输入区遮挡，滚动体验割裂。
```

这说明当前问题不再是“功能缺失”，而是：

```text
布局范式错了。
```

v1.6 目标是把会话页从：

```text
卡片式控制台 + 聊天气泡 + 表单输入区
```

重构为：

```text
真正的聊天式工作区
```

---

## 2. v1.6 总目标

版本目标：

```text
v1.6.x：会话页聊天视口重构
```

核心目标：

```text
1. 会话页改成固定视口三段式布局。
2. 顶部会话区从大卡片改成轻量 header bar。
3. 消息流成为唯一主滚动区域，占满剩余空间。
4. 输入区从大表单卡片改成紧凑聊天 composer。
5. 切换会话 / 更多改成小按钮或文本入口，不再是大按钮。
6. 保留 v1.5 已完成的会话逻辑：发送、轮询、失败恢复、长回复折叠、复制重试。
7. 不新增后端能力，不改 AppThread / AppTurn API。
```

最终判断标准：

```text
打开会话页后，第一眼应该像聊天 App，而不是移动后台管理页。
消息区应该是主角。
输入区应该紧凑，不遮挡大块内容。
顶部栏应该轻，不抢视觉焦点。
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
8. 不做真正流式输出。
9. 不做审批 UI。
10. 不做 diff UI。
11. 不做多用户系统。
12. 保留现有 AppThread / AppTurn API。
13. 保留现有 smoke 脚本。
14. 每阶段必须 pytest -q 通过。
15. 不自动 commit。
16. 不 push。
```

---

## 4. 当前截图暴露的问题

## 4.1 顶部区域太重

当前截图中顶部会话卡显示：

```text
t1
状态 ACTIVE · 3 轮 · 更新时间
切换会话
更多
```

问题：

```text
1. 外层 card + 内层 detail-card 造成双层卡片感。
2. “切换会话”是大按钮，占一整行。
3. “更多”也是大按钮。
4. 顶部区域高度接近一个表单卡片，不像聊天 App 的 header。
```

目标：

```text
压缩为 48~60px 的轻量会话栏。
```

---

## 4.2 消息流被挤压

截图中间的助手回复被底部输入区挡住，消息区显得很短。

问题：

```text
1. message-list 不是独立滚动容器。
2. composer 使用 sticky bottom，仍参与页面流。
3. 消息区没有 flex: 1 占满剩余空间。
4. 底部 composer 和底部 Tab 叠加后视觉压迫强。
```

目标：

```text
消息流必须成为唯一滚动区域，占满 header 与 composer 之间的剩余高度。
```

---

## 4.3 输入区太像表单

截图中输入区显示：

```text
发送消息
textarea 大输入框
输入消息后即可发送
0 字
等待回复 checkbox
发送大按钮
```

问题：

```text
1. 输入区太高。
2. textarea 默认高度过大。
3. 发送模式和发送按钮占用一整行。
4. 视觉上像一个表单卡片，而不是聊天输入框。
```

目标：

```text
改成 compact composer：默认 44~56px，高度随内容增长，最多 120px。
```

---

## 4.4 操作按钮仍然偏后台

“切换会话 / 更多 / 发送”这些按钮仍偏后台系统。

目标：

```text
1. 顶部切换 / 更多改成小型按钮。
2. 发送按钮保持主操作，但不再又宽又厚。
3. 发送模式降级为小标签或轻量 toggle。
```

---

# 5. v1.6 分阶段计划

建议拆成四个小版本：

```text
v1.6.0：会话页 fixed viewport 布局
v1.6.1：轻量 session header
v1.6.2：紧凑 composer 与输入体验
v1.6.3：消息流视觉密度与滚动体验
```

不要一次性执行全部 v1.6。

---

# 6. v1.6.0：会话页 fixed viewport 布局

## 6.1 目标

把会话页从普通页面流改成真正聊天 App 的视口布局。

目标结构：

```text
#tab-app
├── session-header       固定高度，不滚动
├── message-list         flex: 1，唯一滚动区域
└── session-composer     固定底部，不参与消息流滚动
```

## 6.2 CSS 目标

建议新增或调整：

```css
#tab-app.app-console {
  height: calc(100vh - var(--app-top-height) - var(--bottom-nav-height));
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding-bottom: 0;
}

#tab-app .session-header {
  flex: 0 0 auto;
}

#tab-app .message-list {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: var(--space-3);
}

#tab-app .session-composer {
  flex: 0 0 auto;
}
```

如果当前全局 `main` padding 会影响布局，可以只对会话页做局部覆盖。

## 6.3 避免遮挡底部 Tab

底部 composer 应该位于 bottom nav 上方，但不要大面积悬浮阴影。

建议：

```css
.session-composer {
  position: relative;
  bottom: auto;
  box-shadow: none;
  border-top: 1px solid var(--border);
}
```

不要再使用大卡片悬浮阴影。

## 6.4 关键要求

```text
1. 会话页内部滚动只发生在 message-list。
2. 顶部 session-header 和底部 composer 不随消息滚动。
3. 消息不会被 composer 遮挡。
4. 切换到其他 Tab 不受影响。
5. 首页 / 任务 / 我的 仍保持原布局。
```

## 6.5 v1.6.0 验收标准

```text
1. #tab-app 是 flex column 布局。
2. message-list 设置 overflow-y: auto。
3. session-header 和 session-composer 不参与消息流滚动。
4. composer 不再用大 sticky card 覆盖消息区。
5. pytest -q 通过。
```

---

# 7. v1.6.1：轻量 session header

## 7.1 目标

把顶部会话卡从“详情卡片”改为“聊天 App 顶部栏”。

当前顶部视觉太厚。v1.6.1 改成：

```text
左侧：会话标题
副标题：ACTIVE · 3 轮 · 更新 xx
右侧：切换 / 更多 小按钮
```

## 7.2 DOM 建议

当前可以保留：

```html
<div id="appThreadCurrent"></div>
```

但渲染内容改成：

```html
<div class="session-title-area">
  <div class="session-title">t1</div>
  <div class="session-subtitle">ACTIVE · 3 轮 · 更新 2026-...</div>
</div>
<div class="session-header-actions">
  <button class="btn-icon" title="切换会话">切换</button>
  <button class="btn-icon" title="更多">更多</button>
</div>
```

## 7.3 样式建议

```css
.session-header {
  min-height: 52px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  box-shadow: none;
}

.session-header-card,
.app-current-card,
#appThreadCurrent {
  box-shadow: none;
  border-radius: 0;
}
```

尽量去掉双层卡片。

## 7.4 按钮要求

```text
1. 不再使用整行大按钮“切换会话”。
2. “切换会话”和“更多”可以是小按钮或文本按钮。
3. 小按钮宽度不超过 64px。
4. 顶部栏总高度控制在 48~64px。
```

## 7.5 无会话状态

无会话时不要显示大卡片。

显示：

```text
开始一次 Codex 会话
选择或新建会话后即可发送消息
[新建] [选择]
```

按钮仍然要小，不要撑满整行。

## 7.6 v1.6.1 验收标准

```text
1. 顶部栏高度明显降低。
2. 没有外层 card + 内层 detail-card 的双层卡片感。
3. 切换/更多不是大按钮。
4. 当前会话信息清晰但不抢消息区空间。
5. pytest -q 通过。
```

---

# 8. v1.6.2：紧凑 composer 与输入体验

## 8.1 目标

把底部输入区从“大表单卡片”改为“聊天输入栏”。

## 8.2 结构建议

当前结构：

```text
label 发送消息
textarea
hint + count
send mode row
```

建议改为：

```html
<div class="composer-status-row">
  <span id="appMessageHint">输入消息后即可发送</span>
  <button id="sendModeToggle" class="btn-text">快速发送</button>
</div>
<div class="composer-input-row">
  <textarea id="appMessage" placeholder="输入消息"></textarea>
  <button id="sendAppMessage" class="send-button">发送</button>
</div>
```

可以保留隐藏 checkbox `appSendAsync` 用于现有逻辑，但主 UI 不再展示 checkbox 样式。

## 8.3 textarea 高度

建议：

```css
.session-composer textarea {
  min-height: 44px;
  max-height: 120px;
  resize: none;
}
```

可选：输入时自动高度：

```javascript
function autoResizeComposer() {
  const input = document.getElementById('appMessage');
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 120) + 'px';
}
```

## 8.4 发送模式

主文案：

```text
快速发送
等待回复
```

交互：

```text
点击模式按钮在快速发送/等待回复之间切换。
```

底层仍然使用：

```text
快速发送 -> /turns/async
等待回复 -> /turns
```

## 8.5 状态提示

composer 状态提示只占一行，小字号：

```text
未选会话：请先选择或新建会话
运行中：正在等待回复，可以继续编辑
关闭：当前会话已关闭，请重开
可发送：快速发送，后台等待回复
```

不再占用大块空间。

## 8.6 v1.6.2 验收标准

```text
1. 输入区高度明显降低。
2. textarea 默认不再 96px 起步。
3. 发送按钮和输入框在同一行或紧凑布局。
4. 快速发送/等待回复是轻量按钮，不是 checkbox 大控件。
5. 输入区不会遮挡消息内容。
6. pytest -q 通过。
```

---

# 9. v1.6.3：消息流视觉密度与滚动体验

## 9.1 目标

让消息区成为真正主角。

## 9.2 消息区样式

建议：

```css
.message-list {
  background: var(--bg);
}

.chat-list {
  gap: 10px;
}

.bubble.user {
  max-width: 78%;
}

.bubble.assistant {
  max-width: 92%;
}
```

当前用户和助手都是 86%，用户气泡可更窄，助手更宽，符合阅读场景。

## 9.3 减少气泡内部 meta

主气泡默认只展示：

```text
状态 badge
耗时
正文
```

弱化：

```text
点击查看详情
```

如果视觉太杂，可以把“点击查看详情”只放在 hover/详情入口中，移动端也可去掉。

## 9.4 消息底部留白

消息流底部要留出 composer 的安全空间：

```css
.message-flow {
  padding-bottom: 12px;
}
```

如果 composer 固定在会话页内部，不需要额外 180px scroll-margin。

## 9.5 自动滚动

保留现有：

```javascript
scrollAppMessagesToBottom(force)
```

但调整逻辑：

```text
1. 发送后强制到底部。
2. 新消息完成时，如果用户接近底部则滚动。
3. 用户正在看历史时不要强制拉到底部。
```

## 9.6 v1.6.3 验收标准

```text
1. 消息区视觉空间明显增加。
2. 回复卡不再被输入区遮挡。
3. 用户/助手气泡宽度更合理。
4. 长回复展开不会破坏 composer 位置。
5. pytest -q 通过。
```

---

## 10. 代码范围

v1.6 主要允许修改：

```text
backend/mobile.py
tests/test_ui.py
```

可选修改：

```text
docs/mobile-v1.6-chat-viewport-redesign-plan.md
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

修改 `tests/test_ui.py`，覆盖：

```text
1. #tab-app 使用 app-console / session viewport 相关 class。
2. 存在 session-header / message-list / session-composer。
3. CSS 中存在 flex-direction: column。
4. message-list / app-main-panel 有 overflow-y: auto。
5. 顶部栏不再使用大按钮文案作为主结构。
6. composer textarea min-height 不再是 96px。
7. 存在 composer-input-row / composer-status-row 或等价结构。
8. 发送模式仍保留快速发送 / 等待回复。
9. 现有 AppThread/AppTurn API 调用仍存在。
10. escapeHtml 仍保护动态字段。
```

每阶段必须运行：

```powershell
python -m compileall backend runner scripts poc/app_server
pytest -q
```

---

## 12. 本次不做

v1.6 不做：

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
v1.6.0：会话页 fixed viewport 布局
```

不要一次性执行 v1.6.0 ~ v1.6.3。

### v1.6.0 指令摘要

```text
请阅读 docs/mobile-v1.6-chat-viewport-redesign-plan.md，先执行 v1.6.0：会话页 fixed viewport 布局。

目标：
1. 将 #tab-app.app-console 改为 flex column 固定视口布局。
2. session-header 固定在会话页顶部，不参与消息流滚动。
3. message-list 成为唯一滚动区域，overflow-y: auto。
4. session-composer 固定在会话页底部，不遮挡消息。
5. 不改 AppThread/AppTurn API。
6. 保留 v1.5 的发送、轮询、长回复折叠、失败恢复、复制重试逻辑。

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

v1.6 完成后，会话页应该从：

```text
卡片控制台式会话页
```

变成：

```text
聊天 App 式会话页
```

核心体验：

```text
顶部轻
中间大
底部紧凑
消息不被挡
输入不压迫
调试不打扰
```
