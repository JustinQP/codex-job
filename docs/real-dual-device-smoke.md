# Real Dual Device Smoke

This checklist records the manual smoke that cannot be replaced by
`scripts/smoke_local_e2e.py`. It is not automated and must be run with two real
devices or two real agent hosts before marking the dual-device scenario as
passed.

## Scope

- two real devices registered to the same Control Plane
- the same `workspace_key` reported by both devices remains device-scoped
- read-only session open, turn execution, stream recovery, and reopen
- workspace-write run creation, artifact upload, cancel, and lock release
- evidence for PASS/FAIL decisions, without treating missing devices as passed

## Prerequisites

1. Start the Control Plane with the intended `API_TOKEN` and `AGENT_TOKEN`.
2. Start Agent A and Agent B from separate real hosts or separate real device
   environments.
3. Confirm both agents use distinct `CODEX_AGENT_DEVICE_ID` values and separate
   `CODEX_AGENT_DATA_DIR` paths.
4. Configure both agents with at least one workspace using the same
   `workspace_key` and different local paths.
5. Open `/mobile` from the operator device and confirm both devices are online.

## Evidence Record

| Field | Value |
| --- | --- |
| Date/time | |
| Control Plane version/commit | |
| Operator | |
| Device A id/name | |
| Device B id/name | |
| Shared `workspace_key` | |
| Device A workspace path | |
| Device B workspace path | |
| API token source | |
| Network boundary | |
| Result | PASS/FAIL |
| Notes | |

## Checks

| Step | Expected result | Evidence | PASS/FAIL |
| --- | --- | --- | --- |
| Register two real devices | Both devices appear online in `/mobile` with separate ids and capabilities. | Device ids and screenshot or API response. | |
| Sync same `workspace_key` from both devices | Workspaces remain separate rows scoped to each device; selecting one does not overwrite the other. | Workspace ids and device ids. | |
| Start read-only session on Device A | `SESSION_OPEN` completes, AppThread becomes `ACTIVE`, and the thread records `agent_session_id` plus `codex_thread_id`. | AppThread id and command id. | |
| Send read-only session turn | `TURN_START` completes and stream/event replay shows assistant output without holding a stale DB session. | AppTurn id and final assistant text. | |
| Reopen read-only session | Reopen reuses or restores the expected Codex thread context and does not create a duplicate active session for the same thread. | Reopen command id and resulting thread state. | |
| Start workspace-write run on Device B | Run is routed to Device B's workspace and acquires the workspace lock for that device/path only. | Run id, command id, workspace id. | |
| Cancel an in-flight run | Cancel moves the run to a terminal canceled state and releases the workspace lock. | Cancel response and follow-up lock/run evidence. | |
| Recover after agent restart | Restarting the selected agent reconciles pending commands/events and does not duplicate uploaded events. | Reconcile response and event sequence. | |
| Cross-device isolation check | Device A and Device B can use the same `workspace_key` without command or artifact leakage. | Run/thread artifacts and device ids. | |

## Completion Rule

The real dual-device smoke is complete only when every required row above is
marked PASS with evidence. If the current environment does not provide two real
devices, record the result as FAIL or not run; do not mark it as passed based on
the fake local smoke.
