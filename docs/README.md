# 项目文档索引

本目录只保留对当前开发、运行和维护仍然有效的文档。已经完成或被替代的版本计划不继续堆放在 `docs` 根目录，而是通过 `90-archive/` 中的固定 Git 提交链接保留历史。

## 1. 当前有效文档

### 使用与验收

- [功能与用法说明](feature-usage.md)
- [API 概览](api-overview.md)
- [App Server 会话说明](app-server-session.md)
- [状态机](state-machines.md)
- [Smoke 验收清单](smoke-checklist.md)

### 当前开发计划

当前没有活跃开发计划。v2.0 多设备连续会话计划已完成并归档到 `docs/90-archive/`。

新一轮跨提交开发开始前，再在 `20-plan/` 中放置一份路线图和一份执行清单。

### 工程规则

- [AI 开发流程](30-rules/ai-workflow.md)
- [文档治理规则](30-rules/docs-governance.md)
- [工程基线](30-rules/engineering-baseline.md)
- [测试与验收规则](30-rules/testing-acceptance.md)

### 历史资料

- [历史版本计划索引](90-archive/README.md)
- [v2.0 多设备连续会话路线图](90-archive/multi-device-continuous-session-roadmap.md)
- [v2.0 多设备连续会话执行清单](90-archive/multi-device-continuous-session-codex-task-list.md)

历史资料通过不可变 commit 链接保存，避免在当前工作树中保留大量已完成的过程计划。

## 2. 目录职责

```text
docs/
  README.md            # 文档总入口
  *.md                 # 少量高频、长期有效的使用和设计文档
  20-plan/             # 当前活跃路线图和执行清单
  30-rules/            # AI、工程、测试、文档规则
  90-archive/          # 历史资料索引
```

当前项目是个人工具，不为目录结构本身引入额外层级。只有同类长期文档明显增多时，才新增 `00-overview/`、`10-design/` 或 `40-review/` 等目录。

## 3. 文档生命周期

### 新建

只有满足以下条件之一才新增正式文档：

- 跨多个提交或开发阶段，需要持续引用。
- 记录长期有效的架构、接口、部署或验收信息。
- 是当前唯一的正式路线图或 Codex 执行清单。
- 重要决策需要通过 Git 留痕。

### 更新

同一主题已有文档时优先更新，不创建 `新版`、`最终版`、`plan-2` 等重复文件。

### 完成

版本计划完成后：

1. 将仍然有效的结论更新到 README、设计、API 或运行文档。
2. 将复盘结论写入专门复盘文档（确有长期价值时）。
3. 从活跃计划目录移除完成的过程计划。
4. 在 `90-archive/README.md` 中保留固定 commit 链接。

### 删除

临时草稿、重复内容和无长期价值的过程记录可以删除；重要历史内容必须能够通过 Git 历史或归档索引找回。

## 4. 当前约束

- `docs` 根目录只保留本索引和少量长期有效文档。
- `20-plan/` 同一产品方向最多保留一份路线图和一份执行清单。
- 历史 plan 不作为当前实现依据。
- 测试不得依赖已完成版本计划中的文案；测试应验证当前代码、当前接口或当前有效文档。
- 文档移动或归档时同步更新 README、测试和交叉引用。
