import { useCallback, useEffect, useState } from "react";

import { getBridgeHealth, listAppThreads } from "../../api/appThreads";
import { safeApi } from "../../api/client";
import { listRunners } from "../../api/runners";
import { listTasks } from "../../api/tasks";
import type { AppThread, BridgeHealth, Runner, Task } from "../../api/types";
import { Badge } from "../common/Badge";
import { Button } from "../common/Button";
import { EmptyState } from "../common/EmptyState";
import type { PageProps } from "../types";
import { formatRelativeTime } from "../../utils/date";
import { statusTone, shortText } from "../../utils/text";

type Health = { status?: string };

export function HomePage({ showToast }: PageProps) {
  const [health, setHealth] = useState<Health | null>(null);
  const [bridge, setBridge] = useState<BridgeHealth | null>(null);
  const [runners, setRunners] = useState<Runner[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [threads, setThreads] = useState<AppThread[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadHome = useCallback(async () => {
    setLoading(true);
    setError("");
    const [healthResult, runnerResult, taskResult, bridgeResult, threadResult] =
      await Promise.all([
        safeApi<Health>("/health"),
        safeApi<Runner[]>("/runners"),
        safeApi<Task[]>("/tasks?limit=20"),
        safeApi<BridgeHealth>("/app-server-bridge/health"),
        safeApi<AppThread[]>("/app-threads?limit=3")
      ]);

    if (healthResult.ok) setHealth(healthResult.data);
    if (runnerResult.ok) setRunners(runnerResult.data);
    if (taskResult.ok) setTasks(taskResult.data);
    if (bridgeResult.ok) setBridge(bridgeResult.data);
    if (threadResult.ok) setThreads(threadResult.data);

    const failures = [healthResult, runnerResult, taskResult, bridgeResult, threadResult]
      .filter((result) => !result.ok)
      .map((result) => String(result.error));
    if (failures.length) setError(failures[0]);
    setLoading(false);
  }, []);

  useEffect(() => {
    void loadHome();
  }, [loadHome]);

  const runningTasks = tasks.filter((task) => ["PENDING", "RUNNING"].includes(task.status));
  const onlineRunners = runners.filter((runner) => runner.status === "ONLINE");

  return (
    <section className="page active" id="tab-home">
      <div className="page-header summary-card home-hero">
        <div className="row">
          <div>
            <h2>Codex 工作台</h2>
            <p className="muted">今日工作台：先看状态，再进入任务或会话。</p>
          </div>
          <Button
            onClick={() => {
              void loadHome();
              showToast("首页已刷新", "success");
            }}
            variant="secondary"
          >
            刷新
          </Button>
        </div>
      </div>

      {error ? <div className="inline-warning">部分状态加载失败：{error}</div> : null}

      <div className="summary-card">
        <h2>系统状态</h2>
        <div className="status-grid">
          <StatusTile label="Backend" value={health?.status || (loading ? "检查中" : "未知")} />
          <StatusTile label="Runners" value={`${onlineRunners.length}/${runners.length} 在线`} />
          <StatusTile label="Bridge" value={bridge?.status || "未知"} />
          <StatusTile label="AppThreads" value={`${threads.length} 最近会话`} />
        </div>
      </div>

      <div className="summary-card stack">
        <h2>运行中</h2>
        {runningTasks.length ? (
          runningTasks.slice(0, 3).map((task) => <TaskLine key={task.id} task={task} />)
        ) : (
          <EmptyState title="没有运行中的任务" />
        )}
      </div>

      <div className="summary-card stack">
        <h2>最近任务</h2>
        {tasks.length ? (
          tasks.slice(0, 3).map((task) => <TaskLine key={task.id} task={task} />)
        ) : (
          <EmptyState title="还没有任务" />
        )}
      </div>

      <div className="summary-card stack">
        <h2>最近会话</h2>
        {threads.length ? (
          threads.slice(0, 3).map((thread) => <ThreadLine key={thread.id} thread={thread} />)
        ) : (
          <EmptyState title="还没有 App 会话" />
        )}
      </div>
    </section>
  );
}

function StatusTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="status-tile">
      <strong>{label}</strong>
      <span>{value}</span>
    </div>
  );
}

function TaskLine({ task }: { task: Task }) {
  return (
    <div className="list-card">
      <div className="row">
        <strong>#{task.id} {shortText(task.prompt, 48)}</strong>
        <Badge tone={statusTone(task.status)}>{task.status}</Badge>
      </div>
      <span className="muted">updated {formatRelativeTime(task.updated_at)}</span>
    </div>
  );
}

function ThreadLine({ thread }: { thread: AppThread }) {
  return (
    <div className="list-card">
      <div className="row">
        <strong>{thread.title}</strong>
        <Badge tone={statusTone(thread.status)}>{thread.status}</Badge>
      </div>
      <span className="muted">
        {thread.turn_count} 轮 · updated {formatRelativeTime(thread.updated_at)}
      </span>
    </div>
  );
}
