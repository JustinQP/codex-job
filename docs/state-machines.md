# State Machines

本文档说明 v1.0.0 当前 App Server 会话状态机。

## AppThread 状态

```text
CREATED
ACTIVE
RECOVER_REQUIRED
ERROR
CLOSED
```

含义：

- `CREATED`：线程记录已创建但尚未进入可用状态。当前主线创建成功后通常直接进入 `ACTIVE`。
- `ACTIVE`：线程可继续发送 AppTurn。
- `RECOVER_REQUIRED`：取消、超时或后端恢复时底层 App Server 状态不再可信；必须 reopen 后才能继续发送 turn。
- `ERROR`：最近一次 Bridge 或 turn 操作失败，需要排查或 reopen。
- `CLOSED`：线程已关闭，不允许继续发送 turn，除非 reopen。

典型流转：

```text
CREATED -> ACTIVE
ACTIVE -> RECOVER_REQUIRED
ACTIVE -> ERROR
ACTIVE -> CLOSED
RECOVER_REQUIRED -> ACTIVE by reopen
ERROR -> ACTIVE by reopen
CLOSED -> ACTIVE by reopen
```

## AppTurn 状态

```text
PENDING
RUNNING
SUCCESS
FAILED
CANCELLED
```

含义：

- `PENDING`：异步 turn 已入库，等待后台线程执行。
- `RUNNING`：后台线程正在调用 Bridge。
- `SUCCESS`：Bridge 已完成 turn，后端已保存 final 和 event summary。
- `FAILED`：turn 失败，`error_message` 记录原因。
- `CANCELLED`：用户请求取消，关联 Session 进入 `RECOVER_REQUIRED`。

典型流转：

```text
PENDING -> RUNNING -> SUCCESS
PENDING -> RUNNING -> FAILED
PENDING -> CANCELLED
RUNNING -> CANCELLED
PENDING/RUNNING -> FAILED by recover-stale, Session -> RECOVER_REQUIRED
```

注意：

- 当前 Codex App Server 尚未验证可靠协议级取消；Agent 模式取消或超时会关闭对应 App Server process，并要求 reopen。
- `recover-stale` 是失败恢复，不会重放用户消息。
- 服务重启后不会继续执行 `PENDING` / `RUNNING` AppTurn。
