# State Machines

本文档说明 v1.0.0 当前 App Server 会话状态机。

## AppThread 状态

```text
CREATED
ACTIVE
ERROR
CLOSED
```

含义：

- `CREATED`：线程记录已创建但尚未进入可用状态。当前主线创建成功后通常直接进入 `ACTIVE`。
- `ACTIVE`：线程可继续发送 AppTurn。
- `ERROR`：最近一次 Bridge 或 turn 操作失败，需要排查或 reopen。
- `CLOSED`：线程已关闭，不允许继续发送 turn，除非 reopen。

典型流转：

```text
CREATED -> ACTIVE
ACTIVE -> ERROR
ACTIVE -> CLOSED
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
- `CANCELLED`：用户请求本地取消。

典型流转：

```text
PENDING -> RUNNING -> SUCCESS
PENDING -> RUNNING -> FAILED
PENDING -> CANCELLED
RUNNING -> CANCELLED
PENDING/RUNNING -> FAILED by recover-stale
```

注意：

- `CANCELLED` 是本地状态取消，不保证中断 Codex App Server。
- `recover-stale` 是失败恢复，不会重放用户消息。
- 服务重启后不会继续执行 `PENDING` / `RUNNING` AppTurn。
