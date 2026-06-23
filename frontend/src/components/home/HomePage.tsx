import { useCallback, useEffect, useState } from "react";

import { listAppThreads } from "../../api/appThreads";
import { getHealth } from "../../api/health";
import { listRuns } from "../../api/runs";
import type { AppThread, Health, Run } from "../../api/types";
import { useLocalStorage } from "../../hooks/useLocalStorage";
import { UI_STATE_KEYS } from "../../state/storage";
import { formatRelativeTime } from "../../utils/date";
import { errorText } from "../../utils/error";
import { statusTone, shortText } from "../../utils/text";
import { Badge } from "../common/Badge";
import { Button } from "../common/Button";
import { EmptyState } from "../common/EmptyState";
import type { PageProps } from "../types";

export function HomePage({ showToast }: PageProps) {
  const [, setActiveTab] = useLocalStorage(UI_STATE_KEYS.activeTab, "app");
  const [, setSelectedThreadIdText] = useLocalStorage(UI_STATE_KEYS.selectedAppThreadId, "");
  const [health, setHealth] = useState<Health | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [threads, setThreads] = useState<AppThread[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadHome = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [healthData, runData, threadData] = await Promise.all([
        getHealth(),
        listRuns({ limit: 20 }),
        listAppThreads({ limit: 3 })
      ]);
      setHealth(healthData);
      setRuns(runData);
      setThreads(threadData);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadHome();
  }, [loadHome]);

  const runningRuns = runs.filter((run) => ["PENDING", "RUNNING"].includes(run.status));
  const failedRuns = runs.filter((run) => run.status === "FAILED");
  const healthOk = health?.status === "ok";

  function openThread(thread: AppThread) {
    setSelectedThreadIdText(String(thread.id));
    setActiveTab("app");
  }

  return (
    <section className="page active" id="tab-home">
      <div className="home-hero">
        <div>
          <h2>移动工作台</h2>
          <p>Device Agent 主线状态。</p>
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

      {error ? <div className="inline-warning">状态加载失败：{error}</div> : null}

      <section className="wechat-section">
        <div className="wechat-list">
          <StatusRow detail={health?.status || (loading ? "检查中" : "未知")} label="Control Plane" tone={healthOk ? "online" : "warning"} />
          <StatusRow detail={health?.execution_mode || "-"} label="Run Mode" tone="online" />
          <StatusRow detail={health?.session_mode || "-"} label="Session Mode" tone="online" />
        </div>
      </section>

      <section className="wechat-section">
        <div className="section-title-row">
          <h2>正在运行</h2>
          <button className="link-button" onClick={() => setActiveTab("runs")} type="button">
            全部
          </button>
        </div>
        {runningRuns.length ? (
          <div className="wechat-list">
            {runningRuns.slice(0, 3).map((run) => <RunLine key={run.id} run={run} />)}
          </div>
        ) : (
          <EmptyState title="没有运行中的记录" />
        )}
      </section>

      <section className="wechat-section">
        <div className="section-title-row">
          <h2>最近运行</h2>
          <span className="muted">{failedRuns.length ? `${failedRuns.length} 个失败` : "状态正常"}</span>
        </div>
        {runs.length ? (
          <div className="wechat-list">
            {runs.slice(0, 4).map((run) => <RunLine key={run.id} run={run} />)}
          </div>
        ) : (
          <EmptyState title="还没有运行记录" />
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

function RunLine({ run }: { run: Run }) {
  return (
    <div className="wechat-row">
      <div className={`wechat-avatar ${statusTone(run.status)}`}>{run.id}</div>
      <div className="wechat-row-main">
        <strong>{shortText(run.prompt, 42)}</strong>
        <span>{run.run_type} · {formatRelativeTime(run.updated_at)}</span>
      </div>
      <Badge tone={statusTone(run.status)}>{run.status}</Badge>
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
