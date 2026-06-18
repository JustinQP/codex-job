# v1.7 Frontend 完全拆分开发计划

## 1. 背景

当前 mobile 页面已经经历多轮迭代：

```text
v1.0.0：稳定版收口、README/docs、smoke 验收矩阵
v1.1.x：Mobile 第一轮 UI/UX 重构，完成 Tab、卡片、toast、气泡会话
v1.2.x：App 化信息架构，完成 首页 / 任务 / 会话 / 我的、Sheet、更多菜单、发送 toggle
v1.3.x：试用稳定性增强，完成状态持久化、自动刷新、错误分类、空状态优化
v1.4.x：设计系统与交互体系，完成 CSS tokens、组件规范、mobile.py 函数拆分
v1.5.x：会话页核心体验专项，完成失败恢复、长回复折叠、复制重试、会话主路径优化
v1.6.x：会话页聊天视口重构，尝试从卡片控制台布局转向聊天 App 布局
```

现在 mobile 已经不是一个简单的 HTML 页面，而是一个小型前端应用：

```text
1. 多页面：首页 / 任务 / 会话 / 我的
2. 多状态：Task / Runner / AppThread / AppTurn / Bridge
3. 前端状态：localStorage、当前 Tab、当前会话、当前 Turn、发送模式、筛选条件
4. 异步行为：任务自动刷新、AppTurn 轮询、Bridge health 检查
5. 复杂交互：Sheet、Toast、失败恢复、复制重试、长回复折叠、会话切换、紧凑 composer
6. 大量 UI 逻辑：CSS tokens、组件样式、气泡、状态 badge、错误卡、恢复卡
```

继续把 HTML/CSS/JS 放在 `backend/mobile.py` 里，已经明显影响后续迭代：

```text
1. UI 调整效率低。
2. Python 字符串维护 HTML/CSS/JS 容易出错。
3. JS 没有模块边界。
4. CSS 没有独立样式文件。
5. tests/test_ui.py 只能做大量脆弱字符串断言。
6. 会话页继续迭代会越来越难。
```

因此，v1.7 决定进行：

```text
Frontend 完全拆分到 frontend/ 目录
```

---

## 2. v1.7 总目标

版本目标：

```text
v1.7.x：Frontend 完全拆分
```

最终目标：

```text
1. 新增 frontend/ 目录，mobile 前端从 backend/mobile.py 中迁出。
2. backend/mobile.py 不再承载大段 HTML/CSS/JS。
3. 前端具备独立的目录结构、组件结构、样式文件、API client、状态管理模块。
4. FastAPI 继续统一托管前端页面和 API。
5. 不改变现有后端 API 语义。
6. 不破坏 Runner/codex exec 主链路。
7. 不破坏 App Server Bridge sidecar 架构。
8. 为后续持续优化会话页 UI/UX 打基础。
```

一句话：

```text
把 mobile 从 Python 字符串里救出来，变成真正可维护的前端项目。
```

---

## 3. 技术选型建议

## 3.1 推荐方案

推荐使用：

```text
Vite + React + TypeScript
```

理由：

```text
1. Vite 启动快，配置少。
2. React 适合当前这种状态驱动 UI。
3. TypeScript 有利于约束 API 数据结构。
4. 后续会话页组件化更自然。
5. 构建产物可以由 FastAPI 静态托管。
```

## 3.2 可接受替代方案

如果不想引入 React，也可以使用：

```text
Vite + Vanilla TypeScript
```

但从当前页面复杂度看，建议直接 React。

## 3.3 不推荐方案

不推荐：

```text
1. 继续纯 Python 字符串拼接。
2. 只拆 backend/static/mobile.js 和 mobile.css，但仍无组件结构。
3. 一步到位引入大型 UI 组件库。
4. 引入 Next.js / Nuxt 这类 SSR 框架。
```

本项目是本地/局域网工具，不需要 SSR。

---

## 4. 目标目录结构

建议新增：

```text
frontend/
  package.json
  package-lock.json 或 pnpm-lock.yaml
  vite.config.ts
  tsconfig.json
  index.html
  src/
    main.tsx
    App.tsx
    api/
      client.ts
      types.ts
      tasks.ts
      appThreads.ts
      runners.ts
      projects.ts
    state/
      storage.ts
      appState.ts
    components/
      layout/
        BottomNav.tsx
        Sheet.tsx
        Toast.tsx
      common/
        Badge.tsx
        Button.tsx
        EmptyState.tsx
        ErrorSheet.tsx
        RecoveryCard.tsx
      session/
        SessionPage.tsx
        SessionHeader.tsx
        MessageList.tsx
        MessageBubble.tsx
        Composer.tsx
        ThreadSwitcherSheet.tsx
        SessionMoreSheet.tsx
      tasks/
        TasksPage.tsx
        TaskCard.tsx
        TaskDetailSheet.tsx
        CreateTaskSheet.tsx
      home/
        HomePage.tsx
        StatusGrid.tsx
        RunningPanel.tsx
      settings/
        SettingsPage.tsx
        RunnerDiagnostics.tsx
    hooks/
      usePolling.ts
      useLocalStorage.ts
      useToast.ts
    styles/
      tokens.css
      base.css
      components.css
      session.css
      tasks.css
      app.css
    utils/
      date.ts
      error.ts
      text.ts
```

后端保留：

```text
backend/mobile.py
```

但它只负责返回前端入口页面，或重定向到构建后的静态入口。

---

## 5. FastAPI 集成方式

## 5.1 开发模式

开发时：

```text
backend: http://127.0.0.1:8000
frontend dev server: http://127.0.0.1:5173
```

Vite dev server 通过 proxy 调用后端 API：

```ts
// vite.config.ts
server: {
  proxy: {
    '/api': 'http://127.0.0.1:8000',
    '/health': 'http://127.0.0.1:8000',
    '/projects': 'http://127.0.0.1:8000',
    '/tasks': 'http://127.0.0.1:8000',
    '/runners': 'http://127.0.0.1:8000',
    '/app-threads': 'http://127.0.0.1:8000',
    '/app-turns': 'http://127.0.0.1:8000',
    '/app-server-bridge': 'http://127.0.0.1:8000',
    '/task-templates': 'http://127.0.0.1:8000'
  }
}
```

不强制把后端 API 改成 `/api/*`，避免大改后端。

## 5.2 生产/本地使用模式

构建：

```powershell
cd frontend
npm install
npm run build
```

输出：

```text
frontend/dist/
```

FastAPI 托管：

```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app.mount('/assets', StaticFiles(directory='frontend/dist/assets'), name='frontend_assets')

@app.get('/mobile')
def mobile_console():
    return FileResponse('frontend/dist/index.html')
```

如果 `frontend/dist/index.html` 不存在，则保留一个友好错误页：

```text
Frontend build not found. Please run: cd frontend && npm install && npm run build
```

---

## 6. 迁移原则

## 6.1 先迁移，不重写业务逻辑

v1.7 第一目标是拆分，不是重新设计 UI。

迁移时要尽量保留现有行为：

```text
1. API endpoint 不变。
2. Token localStorage key 不变：apiToken。
3. UI state localStorage key 尽量兼容：mobile.activeTab 等。
4. AppTurn polling 逻辑不变。
5. Task auto refresh 逻辑不变。
6. Sheet/Toast/ErrorSheet 行为等价。
```

## 6.2 UI 视觉只做必要调整

v1.7 不要继续大规模美化。

只允许为拆分后的组件做最小必要样式整理。

真正的 UI 继续优化放到 v1.8。

## 6.3 逐步替换 backend/mobile.py

不建议一次删除旧代码。

建议迁移策略：

```text
v1.7.0：建立 frontend 工程骨架，FastAPI 能托管 dist。
v1.7.1：迁移静态 UI 壳和通用组件。
v1.7.2：迁移 API client 与状态管理。
v1.7.3：迁移四个页面：首页 / 任务 / 会话 / 我的。
v1.7.4：移除 backend/mobile.py 中旧的大段 HTML/CSS/JS。
v1.7.5：测试与文档收口。
```

---

# 7. v1.7 分阶段开发计划

---

## v1.7.0：Frontend 工程骨架与 FastAPI 托管

### 目标

新增 `frontend/` 项目，打通：

```text
npm install
npm run build
python -m uvicorn backend.main:app
http://127.0.0.1:8000/mobile
```

### 任务

1. 新增 `frontend/` 目录。
2. 使用 Vite + React + TypeScript 初始化。
3. 新增基础页面：显示 `Codex Mobile Console`。
4. 配置 `npm run build` 输出到 `frontend/dist`。
5. 修改后端 `/mobile`：
   - 优先返回 `frontend/dist/index.html`。
   - 如果 dist 不存在，返回清晰提示。
6. 配置 FastAPI 托管 `/assets`。
7. 保留旧 `backend/mobile.py` 中的旧页面代码作为 fallback，或者临时保留函数但不作为主入口。

### 验收标准

```text
1. cd frontend && npm install && npm run build 成功。
2. python -m compileall backend runner scripts poc/app_server 成功。
3. pytest -q 成功。
4. /mobile 可以打开 frontend 构建页面。
5. dist 不存在时有清晰提示，不是 500。
```

### 允许修改

```text
frontend/**
backend/main.py
backend/mobile.py
tests/test_ui.py
README.md 或 docs
```

### 不要修改

```text
backend/models.py
backend/schemas.py
backend/services/
runner/
poc/app_server/
scripts/smoke_app_server_flow.py
```

---

## v1.7.1：迁移设计系统与通用组件

### 目标

把现有 CSS tokens、基础组件迁移到前端项目。

### 任务

1. 新增样式文件：

```text
frontend/src/styles/tokens.css
frontend/src/styles/base.css
frontend/src/styles/components.css
frontend/src/styles/session.css
frontend/src/styles/tasks.css
frontend/src/styles/app.css
```

2. 迁移现有 CSS tokens：

```text
--space-1
--space-2
--radius-sm
--radius-md
--touch-min
--bottom-nav-height
--composer-height
```

3. 新增通用组件：

```text
Badge
Button
BottomNav
Sheet
Toast
EmptyState
RecoveryCard
ErrorSheet
```

4. 实现基础四 Tab 壳：

```text
首页 / 任务 / 会话 / 我的
```

### 验收标准

```text
1. 前端页面有四 Tab。
2. 样式不依赖 backend/mobile.py 内联 style。
3. 通用组件可被页面使用。
4. npm run build 成功。
5. pytest -q 成功。
```

---

## v1.7.2：迁移 API client 与前端状态

### 目标

从全局 JS 函数迁移为模块化 API client 和状态 hooks。

### 任务

1. 新增 API 类型：

```text
frontend/src/api/types.ts
```

至少定义：

```text
Project
Runner
Task
TaskTemplate
AppThread
AppTurn
BridgeHealth
```

2. 新增 API client：

```text
frontend/src/api/client.ts
frontend/src/api/tasks.ts
frontend/src/api/appThreads.ts
frontend/src/api/runners.ts
frontend/src/api/projects.ts
```

3. 保持 Header：

```text
X-API-Token
Content-Type: application/json
```

4. 迁移 localStorage：

```text
apiToken
mobile.activeTab
mobile.taskStatusFilter
mobile.appThreadStatusFilter
mobile.appIncludeArchived
mobile.selectedAppThreadId
mobile.appSendMode
```

5. 新增 hooks：

```text
useLocalStorage
useToast
usePolling
```

### 验收标准

```text
1. API client 不改变 endpoint。
2. Token 行为兼容旧页面。
3. activeTab 等状态 key 兼容旧页面。
4. npm run build 成功。
5. pytest -q 成功。
```

---

## v1.7.3：迁移四个页面

### 目标

把现有四个 Tab 从 `backend/mobile.py` 迁移到 React 组件。

### 页面

```text
HomePage
TasksPage
SessionPage
SettingsPage
```

### HomePage

迁移：

```text
系统状态
运行中
最近任务
最近会话
异常提醒
```

调用：

```text
GET /health
GET /runners
GET /tasks?limit=20
GET /app-server-bridge/health
GET /app-threads?limit=3
```

### TasksPage

迁移：

```text
任务筛选
任务列表
新建任务 Sheet
任务详情 Sheet
任务取消/重跑
任务自动刷新
```

调用：

```text
GET /projects
GET /runners
GET /task-templates
GET /tasks?limit=20
POST /tasks
GET /tasks/{id}
POST /tasks/{id}/cancel
POST /tasks/{id}/rerun
```

### SessionPage

迁移：

```text
session-header
message-list
session-composer
Thread switcher
Session more
AppTurn polling
长回复折叠
失败恢复
复制重试
重开会话
取消当前 Turn
```

调用：

```text
GET /app-threads
POST /app-threads
GET /app-threads/{id}
DELETE /app-threads/{id}
POST /app-threads/{id}/reopen
GET /app-threads/{id}/turns
POST /app-threads/{id}/turns
POST /app-threads/{id}/turns/async
GET /app-turns/{id}
POST /app-turns/{id}/cancel
GET /app-threads/{id}/final
GET /app-threads/{id}/events
POST /app-turns/recover-stale
POST /app-threads/cleanup
GET /app-server-bridge/health
```

### SettingsPage

迁移：

```text
Token 保存
Runner 诊断
维护操作
Smoke 命令
当前限制
版本文案
```

### 验收标准

```text
1. 四个页面功能与旧 mobile 页面等价。
2. 会话页仍是 v1.6 的聊天 viewport 布局。
3. AppThread/AppTurn 逻辑不倒退。
4. npm run build 成功。
5. pytest -q 成功。
```

---

## v1.7.4：移除旧 mobile.py 大段 HTML/CSS/JS

### 目标

后端不再维护旧的大段前端字符串。

### 任务

1. 将 `backend/mobile.py` 简化为：

```text
read built index.html
or return frontend build missing page
```

2. 删除旧的：

```text
mobile_styles
mobile_home_tab
mobile_tasks_tab
mobile_app_tab
mobile_settings_tab
mobile_script_*
```

3. 保留必要的测试辅助函数，如有。

4. 更新测试，不再对旧 HTML 字符串做大量断言。

### 验收标准

```text
1. backend/mobile.py 明显变短。
2. 不再包含大量 HTML/CSS/JS 字符串。
3. /mobile 仍可打开构建前端。
4. pytest -q 成功。
```

---

## v1.7.5：测试与文档收口

### 目标

完成拆分后的测试体系和文档。

### 测试调整

后端测试：

```text
tests/test_ui.py
```

改为覆盖：

```text
1. /mobile 返回 frontend/dist/index.html 或构建缺失提示。
2. /assets 可托管静态资源。
3. dist 不存在时不是 500。
4. 后端 API 不受影响。
```

前端测试可选：

```text
frontend npm run build
frontend npm run typecheck
```

如果暂不引入前端测试框架，至少保留：

```text
npm run build
npm run typecheck
```

### 文档更新

更新：

```text
README.md
docs/mobile-v1.7-frontend-split-plan.md
```

新增说明：

```text
前端开发启动
前端构建
后端托管 dist
常见问题
```

### 验收标准

```text
1. README 有 frontend 开发说明。
2. v1.7 文档说明 frontend 架构。
3. python -m compileall backend runner scripts poc/app_server 成功。
4. pytest -q 成功。
5. cd frontend && npm install && npm run build 成功。
```

---

## 8. 建议 package.json scripts

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "typecheck": "tsc -b",
    "preview": "vite preview"
  }
}
```

不要一开始引入复杂 lint/prettier，除非项目已经准备好维护前端工具链。

---

## 9. 后端 fallback 策略

`/mobile` 逻辑建议：

```text
1. 如果 frontend/dist/index.html 存在：返回它。
2. 如果不存在：返回构建缺失说明页面。
3. 不再返回旧 mobile.py 内联页面，避免两套 UI 长期并存。
```

构建缺失说明页面包含：

```text
Frontend build not found.
Run:
  cd frontend
  npm install
  npm run build
```

---

## 10. 风险与控制

## 10.1 风险：引入 npm 后环境复杂度增加

控制：

```text
1. 文档写清 npm install / npm run build。
2. 后端 dist 不存在时提示清楚。
3. 不要求所有后端测试自动运行 npm build。
```

## 10.2 风险：前端重写导致行为倒退

控制：

```text
1. v1.7.0~v1.7.2 先打基础，不迁移全部页面。
2. v1.7.3 再迁移四页。
3. 保持 endpoint 不变。
4. 对 AppThread/AppTurn 关键路径手工 smoke。
```

## 10.3 风险：两套 UI 长期并存

控制：

```text
1. v1.7.4 明确删除旧 mobile.py 大段代码。
2. 只保留 frontend dist 托管。
3. 旧代码最多作为短期迁移参考，不保留为运行入口。
```

---

## 11. 本次不做

v1.7 不做：

```text
1. 不做 SSE。
2. 不做 WebSocket。
3. 不做真正流式输出。
4. 不做审批 UI。
5. 不做 diff UI。
6. 不做多用户权限。
7. 不做复杂后端队列。
8. 不做真正强杀 App Server turn。
9. 不改 Runner/codex exec 主链路。
10. 不改 App Server Bridge 架构。
11. 不把 Bridge 合并进 backend。
```

---

## 12. Codex 执行建议

建议先执行：

```text
v1.7.0：Frontend 工程骨架与 FastAPI 托管
```

不要一次性执行 v1.7.0 ~ v1.7.5。

### v1.7.0 指令摘要

```text
请阅读 docs/mobile-v1.7-frontend-split-plan.md，先执行 v1.7.0：Frontend 工程骨架与 FastAPI 托管。

目标：
1. 新增 frontend/，使用 Vite + React + TypeScript。
2. 实现最小前端页面：Codex Mobile Console。
3. npm run build 输出 frontend/dist。
4. 修改 /mobile：优先返回 frontend/dist/index.html。
5. 如果 dist 不存在，返回清晰的构建缺失提示。
6. FastAPI 托管 frontend/dist/assets。
7. 不迁移完整业务页面，只打通前端构建与后端托管链路。

约束：
- 不改后端 API 语义。
- 不改 Runner 主链路。
- 不改 App Server Bridge 架构。
- 不迁移完整会话页。
- 不自动 commit。
- 不 push。

完成后运行：
python -m compileall backend runner scripts poc/app_server
pytest -q
cd frontend
npm install
npm run build
```

---

## 13. 最终目标

v1.7 完成后，项目应从：

```text
后端 Python 字符串承载复杂 mobile 前端
```

升级为：

```text
backend/ 提供 API 和托管入口
frontend/ 负责完整移动端 UI 应用
```

后续 v1.8 才继续专注：

```text
会话页视觉与交互精修
前端组件治理
更好的测试体系
```

---

## 14. 执行状态

截至 v1.7.5，已完成：

```text
v1.7.0：新增 frontend/ Vite + React + TypeScript 工程骨架，FastAPI 托管 frontend/dist。
v1.7.1：迁移设计 tokens、基础样式、通用组件和四 Tab 壳。
v1.7.2：新增 API client、类型、localStorage 兼容 key 和 hooks。
v1.7.3：迁移首页、任务页、会话页、设置页主路径。
v1.7.4：清理 backend/mobile.py 旧大段 HTML/CSS/JS。
v1.7.5：测试和文档收口。
```

当前验证命令：

```powershell
python -m compileall backend runner scripts poc/app_server
pytest -q
cd frontend
npm install
npm run build
```
