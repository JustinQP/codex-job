# State Machines

## Run

```text
PENDING -> RUNNING -> SUCCESS
PENDING -> RUNNING -> FAILED
PENDING -> CANCELLED
RUNNING -> CANCELLED
```

说明：

- `PENDING`：Run 已创建，等待 Device Agent claim。
- `RUNNING`：Agent 已 ack 并开始执行。
- `SUCCESS`：AgentCommand 成功完成。
- `FAILED`：AgentCommand 失败或过期。
- `CANCELLED`：用户取消或 AgentCommand 被取消。

## AppThread

```text
OPENING -> ACTIVE
OPENING -> ERROR
ACTIVE -> RECOVER_REQUIRED
ACTIVE -> CLOSED
RECOVER_REQUIRED -> OPENING by reopen
ERROR -> OPENING by reopen
CLOSED -> OPENING by reopen
```

## AppTurn

```text
PENDING -> RUNNING -> SUCCESS
PENDING -> RUNNING -> FAILED
PENDING -> CANCELLED
RUNNING -> CANCELLED
PENDING/RUNNING -> FAILED by recover-stale
```
