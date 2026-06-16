下一阶段开发计划:
```text
v0.1.2：任务体验与安全边界补丁
v0.2.0：简单 HTML 管理页面
v0.2.1：任务取消与运行中控制
v0.3.0：工程化工作流
v0.4.0：远程 Runner
```

---

# v0.1.2：任务体验与安全边界补丁

## 目标

让这个 MVP 更适合你自己日常连续使用。

## 建议功能

```text
1. TaskRead 不再直接暴露本机文件路径
2. 增加 timeout_seconds 上限
3. 增加 stale runner.lock 检测
4. 增加任务按项目筛选
5. 增加任务状态筛选
6. 增加最近 N 条任务查询
7. 增加简单任务重跑接口：基于旧任务复制 prompt
8. FastAPI version 改成 0.1.2
```

## API 建议

```text
GET  /tasks?project_id=1&status=FAILED&limit=20
POST /tasks/{task_id}/rerun
GET  /tasks/{task_id}/artifacts
```

`/tasks/{task_id}/artifacts` 可以返回：

```json
{
  "log_url": "/tasks/1/log",
  "result_url": "/tasks/1/result",
  "diff_url": "/tasks/1/diff",
  "git_status_url": "/tasks/1/artifacts/git-status"
}
```

这一版依然不要做 Vue。

---

# v0.2.0：简单 HTML 管理页面

## 目标

让你不用每次开 Swagger 或 curl。

## 页面范围

只做一个简单页面：

```text
/
  项目列表
  创建任务
  任务列表
  任务详情
  查看 log/result/diff
```

不要上 Vue，先用 FastAPI + Jinja2 或简单 HTML/HTMX 都可以。你的重点是工具闭环，不是前端工程。

## 验收标准

```text
1. 页面能创建任务
2. 页面能刷新任务状态
3. 页面能查看日志
4. 页面能查看 result
5. 页面能查看 diff
6. 页面能复制旧任务 prompt 重新创建
```

---

# v0.2.1：任务取消

## 目标

让你能终止正在运行的 Codex。

现在 `CANCELLED` 只是预留状态，README 也明确说暂不支持取消正在运行的 Codex 子进程。

## 建议实现

```text
1. Task 增加 cancel_requested 字段
2. Runner 执行时保存当前 process pid
3. POST /tasks/{task_id}/cancel 标记 cancel_requested
4. Runner 定期检查取消标记
5. Windows 下 taskkill /PID <pid> /T /F
6. 任务状态变为 CANCELLED
```

这一步比较关键，因为 Codex 任务可能一跑很久。

---

# v0.3.0：工程化工作流

## 目标

开始贴合你真正的 Codex 使用方式：

```text
生成计划
→ 执行开发
→ 自检
→ 测试
→ 总结
→ 提交
```

## 功能建议

```text
1. 任务类型：
   - PLAN
   - IMPLEMENT
   - REVIEW
   - TEST_FIX
   - DOCS
   - COMMIT

2. 任务模板：
   - 每种任务类型内置 prompt 模板
   - 用户只填核心目标

3. 项目配置：
   - test_command
   - smoke_check_command
   - default_branch
   - require_clean_worktree

4. 执行报告：
   - result.md
   - git-status.txt
   - test-output.txt
   - task-report.md
```

这一版做完，它才真正成为你的“AI 编程任务工作台”。

---

# v0.4.0：远程 Runner

## 目标

让你可以从其他电脑/手机远程提交任务给本机 Runner。

## 前置条件

在做 v0.4 之前，必须先加：

```text
1. API Token
2. 本机路径白名单
3. 不返回本机绝对路径
4. Runner 心跳
5. Runner 注册
```

当前文档也明确“用户身份认证、项目级权限隔离、Prompt 内容安全审核”未实现。

所以 v0.4 之前不要把服务暴露到公网。

---

