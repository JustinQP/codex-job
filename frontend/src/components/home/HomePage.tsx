import { useCallback, useEffect, useState } from "react";

import { getBridgeHealth, listAppThreads } from "../../api/appThreads";
import { safeApi } from "../../api/client";
import { listRunners } from "../../api/runners";
import { listTasks } from "../../api/tasks";
import type { AppThread, BridgeHealth, Runner, Task } from "../../api/types";
import { useLocalStorage } from "../../hooks/useLocalStorage";
import { UI_STATE_KEYS } from "../../state/storage";
import { formatRelativeTime } from "../../utils/date";
import { statusTone, shortText } from "../../utils/text";
import { Badge } from "../common/Badge";
import { Button } from "../common/Button";
import { EmptyState } from "../common/EmptyState";
import type { PageProps } from "../types";

type Health = { status?: string };

export function HomePage({ showToast }: PageProps) {
  const [, setActiveTab] = useLocalStorage(UI_STATE_KEYS.activeTab, "home");
  const [, setSelectedThreadIdText] = useLocalStorage(UI_STATE_KEYS.selectedAppThreadId, "");
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
  const failedTasks = tasks.filter((task) => task.status === "FAILED");
  const healthOk = health?.status === "ok" || health?.status === "healthy";
  const bridgeOk = bridge?.status === "ok" || bridge?.status === "healthy" || bridge?.status === "ready";

  function openThread(thread: AppThread) {
    setSelectedThreadIdText(String(thread.id));
    setActiveTab("app");
  }

  return (
    <section className="page active" id="tab-home">
      <div className="home-hero">
        <div>
          <h2>移动工作台</h2>
          <p>先看状态，再进会话或任务。</p>
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

      {error ? <div className="inline-warning">部分状态加载失败：{error}</div> : null}

      <section className="wechat-section">
        <div className="wechat-list">
          <StatusRow
            detail={health?.status || (loading ? "检查中" : "未知")}
            label="Backend"
            tone={healthOk ? "online" : "warning"}
          />
          <StatusRow
            detail={`${onlineRunners.length}/${runners.length} 在线`}
            label="Runners"
            tone={onlineRunners.length ? "online" : "warning"}
          />
          <StatusRow
            detail={bridge?.status || "未知"}
            label="App Bridge"
            tone={bridgeOk ? "online" : "warning"}
          />
        </div>
      </section>

      <section className="wechat-section">
        <div className="section-title-row">
          <h2>正在处理</h2>
          <button className="link-button" onClick={() => setActiveTab("tasks")} type="button">
            全部
          </button>
        </div>
        {runningTasks.length ? (
          <div className="wechat-list">
            {runningTasks.slice(0, 3).map((task) => <TaskLine key={task.id} task={task} />)}
          </div>
        ) : (
          <EmptyState title="没有运行中的任务" />
        )}
      </section>

      <section className="wechat-section">
        <div className="section-title-row">
          <h2>最近任务</h2>
          <span className="muted">{failedTasks.length ? `${failedTasks.length} 个失败` : "状态正常"}</span>
        </div>
        {tasks.length ? (
          <div className="wechat-list">
            {tasks.slice(0, 4).map((task) => <TaskLine key={task.id} task={task} />)}
          </div>
        ) : (
          <EmptyState title="还没有任务" />
        )}
      </section>

      <section className="wechat-section">
        <div className="section-title-row">
          <h2>最近会话</h2>
          <button className="link-button" onClick={() => setActiveTab("app")} type="button">
            进入会话
          </button>
        </div>
        {threads.length ? (
          <div className="wechat-list">
            {threads.slice(0, 4).map((thread) => (
              <ThreadLine key={thread.id} onOpen={openThread} thread={thread} />
            ))}
          </div>
        ) : (
          <EmptyState title="还没有 App 会话" />
        )}
      </section>
    </section>
  );
}

function StatusRow({
  detail,
  label,
  tone
}: {
  detail: string;
  label: string;
  tone: "online" | "warning";
}) {
  return (
    <div className="wechat-row">
      <div className={`wechat-avatar ${tone}`}>{label.slice(0, 1)}</div>
      <div className="wechat-row-main">
        <strong>{label}</strong>
        <span>{detail}</span>
      </div>
      <Badge tone={tone}>{tone === "online" ? "可用" : "检查"}</Badge>
    </div>
  );
}

function TaskLine({ task }: { task: Task }) {
  return (
    <div className="wechat-row">
      <div className={`wechat-avatar ${statusTone(task.status)}`}>{task.id}</div>
      <div className="wechat-row-main">
        <strong>{shortText(task.prompt, 42)}</strong>
        <span>{task.task_type} · {formatRelativeTime(task.updated_at)}</span>
      </div>
      <Badge tone={statusTone(task.status)}>{task.status}</Badge>
    </div>
  );
}

function ThreadLine({
  onOpen,
  thread
}: {
  onOpen: (thread: AppThread) => void;
  thread: AppThread;
}) {
  return (
    <button className="wechat-row as-button" onClick={() => onOpen(thread)} type="button">
      <div className={`wechat-avatar ${statusTone(thread.status)}`}>会</div>
      <div className="wechat-row-main">
        <strong>{thread.title}</strong>
        <span>{thread.turn_count} 轮 · {formatRelativeTime(thread.updated_at)}</span>
      </div>
      <Badge tone={statusTone(thread.status)}>{thread.status}</Badge>
    </button>
  );
}
