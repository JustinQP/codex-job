# v1.4 Mobile 设计系统与交互体系重构方案

## 1. 背景

当前 mobile 已经经历多轮迭代：

```text
v1.0.0：稳定版收口、README/docs、smoke 验收矩阵
v1.1.x：Mobile 第一轮 UI/UX 重构，完成 Tab、卡片、toast、气泡会话
v1.2.x：Mobile App 产品化第二版，完成 首页 / 任务 / 会话 / 我的、Sheet、更多菜单、发送 toggle、任务筛选
v1.3.x：试用稳定性增强，完成 UI 状态持久化、自动刷新、错误分类、空状态优化
```

这些版本已经解决了“能不能用”和“是不是像手机页面”的问题，但还没有彻底解决“好不好用、顺不顺手、像不像一个真正的 App”的问题。

当前主要问题已经从“页面结构混乱”转变为：

```text
1. 视觉密度还不稳定，有的地方按钮/卡片仍然偏大。
2. 组件没有完整设计规范，页面靠局部 CSS 堆出来。
3. 操作分层还不够彻底，部分 Sheet 里仍然按钮过多。
4. 任务、会话、首页的交互语言不统一。
5. 关键路径不够短，部分操作需要多次进入 Sheet。
6. 真实手机上的触达区域、滚动区域、底部按钮关系还需要重新校准。
7. mobile.py 已经很长，继续堆 UI 会降低后续迭代效率。
```

v1.4 的核心目标不是再补一两个按钮，而是建立一套移动端设计系统和交互体系。

---

## 2. v1.4 总目标

版本目标：

```text
v1.4.x：Mobile 设计系统与交互体系重构
```

核心目标：

```text
1. 建立统一的移动端组件规范：按钮、卡片、列表、Sheet、空状态、错误态、状态栏、底部操作栏。
2. 减少大按钮和重复按钮，形成“主操作 + 次操作 + 更多操作”的固定规则。
3. 重新梳理首页、任务、会话、我的四个 Tab 的首屏体验。
4. 把任务和会话的关键路径压缩到最短。
5. 增强真实手机使用体验：单手操作、底部安全区、滚动区域、输入区、点击反馈。
6. 开始治理 mobile.py 结构，为后续继续迭代做准备。
```

最终判断标准：

```text
用户打开 mobile 后，不需要理解系统架构，也知道现在状态如何、下一步点哪里。
用户执行任务时，只看到任务相关内容。
用户对话时，只看到会话相关内容。
危险/低频/调试操作不会干扰主流程。
页面上的按钮数量明显减少，视觉密度稳定。
```

---

## 3. 总体设计原则

## 3.1 主路径优先

每个 Tab 只保留一个最主要路径：

```text
首页：看状态 -> 新建任务 / 打开最近
任务：看任务列表 -> 新建任务 / 打开详情
会话：当前会话 -> 输入消息 -> 发送
我的：配置 Token / 查看运行诊断
```

非主路径全部收进：

```text
更多菜单
底部 Sheet
详情 Sheet
诊断区
调试区
```

## 3.2 一屏一个重点

移动端首屏不能同时承载太多目标。

推荐规则：

```text
首页首屏：状态 + 快捷入口
任务首屏：筛选 + 任务列表
会话首屏：当前会话 + 消息流 + 输入框
我的首屏：Token 状态 + 系统诊断入口
```

## 3.3 按钮分级固定化

所有按钮按层级分类：

```text
Primary：页面唯一主操作，如 新建任务 / 发送 / 保存 Token
Secondary：普通次操作，如 刷新 / 查看详情 / 切换会话
Ghost/Text：弱入口，如 log / result / diff / 调试信息
Danger：取消 / 关闭 / 清理 / recover-stale 等危险或影响状态的操作
Icon/More：更多操作入口
```

每个主页面最多 1 个 Primary 按钮。

## 3.4 Sheet 是操作容器，不是垃圾桶

Sheet 不应该把所有按钮塞进去。

Sheet 内部也要分层：

```text
顶部：标题 + 简短说明
主体：当前任务相关内容
底部：主操作
更多：低频操作折叠
危险区：靠底部，红色，必须 confirm
```

## 3.5 调试信息默认隐藏

默认不展示：

```text
raw JSON
bridge_thread_id
event_type_counts
完整 error body
过长 log
```

这些只在“调试详情”中查看。

---

## 4. 设计系统规范

## 4.1 布局 Tokens

建议统一 CSS 变量：

```css
:root {
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --font-xs: 11px;
  --font-sm: 12px;
  --font-md: 14px;
  --font-lg: 16px;
  --touch-min: 40px;
  --bottom-nav-height: 56px;
  --composer-height: 132px;
}
```

避免到处写 `10px / 12px / 14px / 42px`。

## 4.2 页面骨架

统一页面结构：

```html
<section class="page" data-tab-page="tasks">
  <div class="page-header">...</div>
  <div class="page-body">...</div>
  <div class="page-footer">...</div>
</section>
```

当前各 Tab 的结构不完全一致，v1.4 要统一。

## 4.3 卡片规范

区分三类卡片：

```text
summary-card：概览卡，比如首页状态
list-card：列表项，比如任务卡片/会话卡片
detail-card：详情块，比如任务详情、错误恢复建议
```

建议 CSS：

```css
.summary-card { ... }
.list-card { ... }
.detail-card { ... }
```

不要所有东西都叫 `.card` 或 `.item`。

## 4.4 按钮规范

按钮尺寸分三档：

```text
btn-primary：主操作，40-44px 高
btn-secondary：次操作，36-40px 高
btn-text / btn-icon：弱入口，32-36px 高
```

限制：

```text
1. 列表卡片中禁止出现 3 个以上实心按钮。
2. Sheet 中同一组操作最多 2 个实心按钮。
3. 危险操作不和普通操作混排。
```

## 4.5 状态 Badge 规范

统一状态色和文案：

```text
PENDING：等待
RUNNING：运行中
SUCCESS：成功
FAILED：失败
CANCELLED：已取消
ACTIVE：正常
ERROR：错误
CLOSED：已关闭
```

Badge 不要过大，应该作为辅助信息，而不是卡片视觉主体。

## 4.6 空状态规范

统一空状态组件：

```html
<div class="empty-state">
  <strong>标题</strong>
  <p>解释</p>
  <button>下一步操作</button>
</div>
```

每个空状态必须告诉用户下一步。

## 4.7 错误状态规范

错误不要只 toast。

重要错误用错误 Sheet：

```text
标题：发生了什么
说明：为什么
下一步：用户能点什么
详情：raw error 折叠
```

---

## 5. 页面级重构方案

# 5.1 首页：首页从“状态卡片”升级为“今日工作台”

## 当前问题

首页已有状态和最近活动，但仍偏信息展示，缺少“今天我该做什么”的感觉。

## 新设计

首页结构：

```text
1. 顶部 Hero
   - Codex 工作台
   - Backend / Runner / Bridge 总体状态
   - 今日主操作：新建任务

2. 运行中区域
   - 正在运行的任务
   - 正在运行的 AppTurn
   - 如果没有运行中，显示“当前空闲”

3. 最近活动
   - 最近任务
   - 最近会话

4. 异常提醒
   - Runner 离线
   - Bridge 异常
   - stale turn 需要恢复
```

## 首页交互

```text
点击运行中任务 -> 任务详情 Sheet
点击运行中 AppTurn -> 会话 Tab 并打开 turn 详情
点击 Runner 异常 -> 我的 / 运行诊断
点击 Bridge 异常 -> 启动提示 Sheet
```

## 验收标准

```text
1. 首页首屏能判断系统是否能用。
2. 首页能直接看到运行中的东西。
3. 首页不会堆太多按钮。
4. 异常有明确下一步。
```

---

# 5.2 任务页：从“任务列表”升级为“任务收件箱”

## 当前问题

任务页已经有筛选和 Sheet，但任务卡片仍然偏工程信息，列表不够像 App 的任务流。

## 新设计

任务页结构：

```text
顶部：任务
- segmented filter：全部 / 运行中 / 待处理 / 已完成 / 失败
- 搜索/刷新弱入口

列表：任务收件箱
- 主标题：任务类型 + prompt 摘要
- 副标题：项目 / Runner / 模型
- 右侧：状态 badge
- 底部：更新时间 / 耗时

底部：+ 新建任务
```

## 任务卡片展示优先级

优先展示：

```text
1. task_type
2. prompt 摘要
3. status
4. updated_at
5. latest result preview，如果有
```

弱化：

```text
project_id
runner_id
model
created_at
```

这些放详情 Sheet。

## 任务详情 Sheet

重构为：

```text
顶部：状态 + 任务类型
正文：Prompt / Result / Log Preview
参数：折叠
操作：查看结果 / 查看日志 / 查看 diff / 重跑 / 取消
```

主操作：

```text
SUCCESS：查看结果
RUNNING：刷新
FAILED：查看日志 / 重跑
PENDING：取消
```

## 验收标准

```text
1. 任务列表不用看一堆技术字段。
2. 每张任务卡片最多 1 个显式操作入口。
3. 更多操作进入 Sheet。
4. 任务详情中根据状态突出最重要操作。
```

---

# 5.3 会话页：从“聊天样式”升级为“真正的会话工作流”

## 当前问题

会话已经有气泡和更多菜单，但仍有一些问题：

```text
1. 没有当前会话为空时的强引导。
2. 会话顶部还不够像聊天 App。
3. “异步” checkbox 对普通用户理解成本高。
4. 更多菜单仍然偏工程化。
```

## 新设计

会话页结构：

```text
顶部固定栏：
- 会话标题
- 状态
- 切换会话
- 更多

消息区：
- 用户气泡
- 助手气泡
- running loading
- failed recovery card

底部输入区：
- textarea
- 发送按钮
- 发送模式作为小标签：快速 / 同步
```

## 发送模式文案调整

把“异步/同步”改成用户能理解的文案：

```text
快速发送（异步）
等待回复（同步）
```

默认：快速发送。

实现上仍然走：

```text
快速发送 -> /turns/async
等待回复 -> /turns
```

## 当前无会话状态

如果没有 selectedAppThreadId：

```text
标题：还没有会话
说明：创建一个 App Server 会话，开始连续对话。
主按钮：新建会话
次按钮：切换已有会话
```

输入框禁用，并提示：

```text
请先新建或选择会话
```

## running 状态

当当前 turn 运行中：

```text
1. 输入框可继续编辑，但发送按钮 disabled。
2. 底部显示“正在等待回复”。
3. 提供一个小型“取消当前 Turn”入口。
```

## failed 状态

失败气泡底部展示恢复操作：

```text
重试
查看错误
重开会话
```

其中重试可以先不实现真正自动重发，只保留“复制上一条消息”或“重新发送当前输入”。

## 验收标准

```text
1. 会话页无会话时引导明确。
2. 默认发送模式文案更友好。
3. 运行中状态不会让用户困惑。
4. 失败后有恢复建议。
5. 更多菜单工程味降低。
```

---

# 5.4 我的页：从“设置堆叠”升级为“诊断中心”

## 当前问题

我的页已经收纳 Token、Runner、Bridge、Smoke、限制，但信息仍比较散。

## 新设计

我的页结构：

```text
1. 账户与访问
   - API Token
   - 当前连接状态

2. 运行诊断
   - Backend
   - Runner
   - Bridge
   - 数据目录/版本信息

3. 维护操作
   - recover stale
   - cleanup archived
   - smoke 命令

4. 关于
   - 当前版本
   - 当前限制
```

维护操作默认折叠。

危险操作必须 confirm。

## 验收标准

```text
1. 我的页是诊断中心，不是杂项堆叠。
2. Token、Runner、Bridge 的状态一眼可见。
3. 维护操作不干扰普通使用。
```

---

## 6. 交互模式重构

# 6.1 Segmented Control

用于状态筛选：

```text
全部 | 运行中 | 成功 | 失败
```

比 select 更像手机 App。

第一版可以用 button group 实现，不引入组件库。

# 6.2 Action Sheet

用于更多操作。

要求：

```text
1. 顶部标题明确。
2. 普通操作和危险操作分组。
3. 危险操作放底部。
4. 每个按钮文案是动作，不是接口名。
```

# 6.3 Detail Sheet

用于详情展示。

要求：

```text
1. 顶部摘要。
2. 结果优先。
3. 技术参数折叠。
4. raw 调试折叠。
```

# 6.4 Inline Recovery Card

用于错误恢复。

示例：

```text
Bridge 会话已失效
说明：App Server Bridge 重启后，旧会话不可用。
操作：重开会话 / 查看详情
```

# 6.5 Toast 使用边界

Toast 只用于短反馈：

```text
已保存
已刷新
已提交
```

复杂错误必须用 Sheet/Card。

---

## 7. 代码治理方案

v1.4 必须开始治理 `backend/mobile.py`，否则后续难以维护。

## 7.1 第一阶段：Python 函数拆分

推荐先不拆静态文件，先做低风险函数化。

目标函数结构：

```python
def mobile_console() -> str

def mobile_head() -> str

def mobile_styles() -> str

def mobile_body() -> str

def mobile_home_tab() -> str

def mobile_tasks_tab() -> str

def mobile_app_tab() -> str

def mobile_settings_tab() -> str

def mobile_sheet() -> str

def mobile_nav() -> str

def mobile_script() -> str
```

JS 再分：

```python
def mobile_script_state() -> str

def mobile_script_core() -> str

def mobile_script_home() -> str

def mobile_script_tasks() -> str

def mobile_script_app() -> str

def mobile_script_errors() -> str

def mobile_script_events() -> str
```

## 7.2 第二阶段：测试从“字符串巨量断言”改为“关键能力断言”

当前 `tests/test_ui.py` 字符串断言非常多，容易变脆。

v1.4 建议分类：

```text
1. 页面结构断言：Tab / Sheet / Toast / key containers
2. 安全断言：escapeHtml + 关键动态字段 escape
3. API 调用断言：关键 endpoints 仍存在
4. 状态持久化断言：localStorage keys
5. 交互能力断言：函数名/入口存在
```

避免过度依赖具体文案和 CSS 细节。

## 7.3 第三阶段：可选静态文件拆分

如果函数化后仍太长，再考虑：

```text
backend/static/mobile.css
backend/static/mobile.js
```

但 v1.4 第一阶段不强制做。

---

## 8. 版本拆分建议

不要一次做完整 v1.4。建议分四步：

```text
v1.4.0：设计系统 Tokens 与组件规范落地
v1.4.1：首页与任务页交互重构
v1.4.2：会话页交互重构
v1.4.3：我的页与 mobile.py 代码治理
```

---

# v1.4.0：设计系统 Tokens 与组件规范落地

## 目标

建立统一 UI 组件基础，先不大改业务逻辑。

## 范围

```text
1. 增加 CSS tokens：spacing / radius / font / touch size / z-index。
2. 统一按钮 class：btn-primary / btn-secondary / btn-text / btn-danger / btn-icon。
3. 统一卡片 class：summary-card / list-card / detail-card。
4. 统一 page-header / page-body / page-footer。
5. 统一 empty-state / error-card / recovery-card。
6. 不改后端 API。
7. 不改 Runner / App Server 主链路。
```

## 验收

```text
1. 页面视觉密度更稳定。
2. 大按钮数量减少。
3. 同类组件样式统一。
4. pytest -q 通过。
```

---

# v1.4.1：首页与任务页交互重构

## 目标

首页更像工作台，任务页更像任务收件箱。

## 范围

```text
1. 首页增加“运行中”区域。
2. 首页异常提醒改为 recovery card。
3. 任务筛选从 select 改为 segmented control。
4. 任务卡片弱化技术字段，突出 prompt 摘要和状态。
5. 任务详情 Sheet 结果优先、参数折叠。
6. 任务更多操作按普通/危险分组。
```

## 验收

```text
1. 首页一眼知道系统是否可用。
2. 任务列表不再像数据库记录。
3. 任务卡片按钮减少。
4. 任务详情更清晰。
5. pytest -q 通过。
```

---

# v1.4.2：会话页交互重构

## 目标

会话页真正接近聊天 App。

## 范围

```text
1. 无会话状态增加强引导。
2. 发送模式从“异步/同步”改为“快速发送/等待回复”。
3. 当前运行中 Turn 增加 inline 状态条。
4. 失败气泡增加恢复建议。
5. 会话更多菜单重新分组，减少工程化文案。
6. AppTurn 详情 Sheet 结果优先、技术信息折叠。
```

## 验收

```text
1. 用户无需理解 AppThread/AppTurn 也能使用。
2. 发送模式文案更自然。
3. 失败后知道如何恢复。
4. 调试信息不会干扰主会话。
5. pytest -q 通过。
```

---

# v1.4.3：我的页与 mobile.py 代码治理

## 目标

把“我的”做成诊断中心，并开始拆分 mobile.py。

## 范围

```text
1. 我的页分为：访问、运行诊断、维护操作、关于。
2. Runner/Bridge 状态合并为诊断卡。
3. recover stale / cleanup archived 进入维护折叠区。
4. mobile.py 按 Tab 和 JS 模块进行函数化拆分。
5. tests/test_ui.py 降低脆弱字符串断言。
```

## 验收

```text
1. 我的页不再像杂项页。
2. 维护操作不干扰普通使用。
3. mobile.py 结构明显更清晰。
4. 测试仍覆盖关键能力但不脆弱。
5. pytest -q 通过。
```

---

## 9. 本次不做

v1.4 仍然不做：

```text
1. 不做 Vue / React。
2. 不做 npm / 前端构建。
3. 不做 SSE / WebSocket。
4. 不做审批 UI。
5. 不做 diff UI。
6. 不做多用户系统。
7. 不做公网部署。
8. 不修改 Runner/codex exec 主链路。
9. 不修改 App Server Bridge 架构。
10. 不新增复杂后端 API。
```

---

## 10. Codex 执行建议

建议先执行：

```text
v1.4.0：设计系统 Tokens 与组件规范落地
```

不要一次执行 v1.4.0 ~ v1.4.3。

### v1.4.0 允许修改

```text
backend/mobile.py
tests/test_ui.py
```

### v1.4.0 原则上不要修改

```text
backend/main.py
backend/models.py
backend/schemas.py
backend/services/
runner/
poc/app_server/
scripts/smoke_app_server_flow.py
```

### v1.4.0 完成后必须运行

```powershell
python -m compileall backend runner scripts poc/app_server
pytest -q
```

---

## 11. 最终判断标准

v1.4 完成后，mobile 应该达到：

```text
1. 不是“能用”，而是“顺手”。
2. 不是“按钮少了一点”，而是“操作有层级”。
3. 不是“像 App 的网页”，而是“按 App 心智组织的工具”。
4. 不是“继续堆字符串”，而是“具备可维护前端结构”。
```
