# 历史文档归档索引

本目录保存已经完成、被替代或不再作为当前实现依据的历史资料索引。

为避免大量过程计划继续占用当前工作树，历史原文通过提交 `224589d6262e27700dc067681493f28e41b0a303` 的不可变链接保留。链接内容不会随 `main` 后续变更而改变。

当前实现和后续开发应优先参考：

- [`docs/README.md`](../README.md)
- [`README.md`](../../README.md)
- [`docs/api-overview.md`](../api-overview.md)
- [`docs/app-server-session.md`](../app-server-session.md)
- [`docs/smoke-checklist.md`](../smoke-checklist.md)

## 1. 早期设计与开发计划

- [01-dev-plan.md](https://github.com/JustinQP/codex-job/blob/224589d6262e27700dc067681493f28e41b0a303/docs/01-dev-plan.md)
- [01-mvp-design.md](https://github.com/JustinQP/codex-job/blob/224589d6262e27700dc067681493f28e41b0a303/docs/01-mvp-design.md)
- [v0.5.0-plan.md](https://github.com/JustinQP/codex-job/blob/224589d6262e27700dc067681493f28e41b0a303/docs/v0.5.0-plan.md)
- [v0.6.0-plan.md](https://github.com/JustinQP/codex-job/blob/224589d6262e27700dc067681493f28e41b0a303/docs/v0.6.0-plan.md)
- [v0.7.x-plan.md](https://github.com/JustinQP/codex-job/blob/224589d6262e27700dc067681493f28e41b0a303/docs/v0.7.x-plan.md)

## 2. App Server 与稳定版计划

- [v0.8.0-plan.md](https://github.com/JustinQP/codex-job/blob/224589d6262e27700dc067681493f28e41b0a303/docs/v0.8.0-plan.md)
- [v0.8.2-plan.md](https://github.com/JustinQP/codex-job/blob/224589d6262e27700dc067681493f28e41b0a303/docs/v0.8.2-plan.md)
- [v0.8.3-plan.md](https://github.com/JustinQP/codex-job/blob/224589d6262e27700dc067681493f28e41b0a303/docs/v0.8.3-plan.md)
- [v0.9.0-plan.md](https://github.com/JustinQP/codex-job/blob/224589d6262e27700dc067681493f28e41b0a303/docs/v0.9.0-plan.md)
- [v0.9.1-plan.md](https://github.com/JustinQP/codex-job/blob/224589d6262e27700dc067681493f28e41b0a303/docs/v0.9.1-plan.md)
- [v0.9.x-plan.md](https://github.com/JustinQP/codex-job/blob/224589d6262e27700dc067681493f28e41b0a303/docs/v0.9.x-plan.md)
- [v1.0.0-plan.md](https://github.com/JustinQP/codex-job/blob/224589d6262e27700dc067681493f28e41b0a303/docs/v1.0.0-plan.md)

## 3. Mobile 版本计划

- [mobile-ui-ux-v1.1-plan.md](https://github.com/JustinQP/codex-job/blob/224589d6262e27700dc067681493f28e41b0a303/docs/mobile-ui-ux-v1.1-plan.md)
- [mobile-ui-ux-v1.2-product-plan.md](https://github.com/JustinQP/codex-job/blob/224589d6262e27700dc067681493f28e41b0a303/docs/mobile-ui-ux-v1.2-product-plan.md)
- [mobile-v1.3-usability-hardening-plan.md](https://github.com/JustinQP/codex-job/blob/224589d6262e27700dc067681493f28e41b0a303/docs/mobile-v1.3-usability-hardening-plan.md)
- [mobile-v1.4-design-system-interaction-redesign-plan.md](https://github.com/JustinQP/codex-job/blob/224589d6262e27700dc067681493f28e41b0a303/docs/mobile-v1.4-design-system-interaction-redesign-plan.md)
- [mobile-v1.5-app-session-core-plan.md](https://github.com/JustinQP/codex-job/blob/224589d6262e27700dc067681493f28e41b0a303/docs/mobile-v1.5-app-session-core-plan.md)
- [mobile-v1.6-chat-viewport-redesign-plan.md](https://github.com/JustinQP/codex-job/blob/224589d6262e27700dc067681493f28e41b0a303/docs/mobile-v1.6-chat-viewport-redesign-plan.md)
- [mobile-v1.7-frontend-split-plan.md](https://github.com/JustinQP/codex-job/blob/224589d6262e27700dc067681493f28e41b0a303/docs/mobile-v1.7-frontend-split-plan.md)

## 4. 文件名异常记录

- [`v1.9.0-plan.md`](https://github.com/JustinQP/codex-job/blob/224589d6262e27700dc067681493f28e41b0a303/docs/v1.9.0-plan.md) 的正文实际是 **v1.8 Conversation-first 产品结构清理计划**。归档保留原文件名以对应历史提交，但不再作为当前版本号依据。

## 5. v2.0 多设备连续会话计划

- [multi-device-continuous-session-roadmap.md](multi-device-continuous-session-roadmap.md)
- [multi-device-continuous-session-codex-task-list.md](multi-device-continuous-session-codex-task-list.md)

归档说明：v2.0 收口时将多设备连续会话路线图和 Codex 执行清单从 `docs/20-plan/` 移入本目录。F05 真实双设备 smoke 按用户指令越过，未作为已通过验收记录；后续需要补验时应以当前 smoke 文档为准。

## 6. 使用规则

- 历史 plan 用于了解演进过程，不用于指导当前实现。
- 历史计划中的路径、版本、限制和测试命令可能已经失效。
- 需要恢复原文时使用以上固定提交链接，不重新复制到 `docs` 根目录。
- 只有从历史计划中提炼出仍长期有效的内容时，才更新当前设计或运行文档。
