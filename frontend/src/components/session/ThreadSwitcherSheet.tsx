import { useEffect, useState } from "react";

import type { AppThread, Project } from "../../api/types";
import { formatRelativeTime } from "../../utils/date";
import { statusTone } from "../../utils/text";
import { Badge } from "../common/Badge";
import { Button } from "../common/Button";

type ThreadSwitcherSheetProps = {
  projects: Project[];
  threads: AppThread[];
  selectedThreadId: number | null;
  currentProjectId: number | null;
  statusFilter: string;
  includeArchived: boolean;
  createDisabledReason?: string;
  onCreate: (projectId: number, title: string) => void;
  onIncludeArchivedChange: (includeArchived: boolean) => void;
  onSelect: (thread: AppThread) => void;
  onRefresh: () => void;
  onStatusFilterChange: (status: string) => void;
};

export function ThreadSwitcherSheet({
  includeArchived,
  onCreate,
  onIncludeArchivedChange,
  onRefresh,
  onSelect,
  onStatusFilterChange,
  projects,
  createDisabledReason = "",
  currentProjectId,
  selectedThreadId,
  statusFilter,
  threads
}: ThreadSwitcherSheetProps) {
  const [projectId, setProjectId] = useState(currentProjectId || projects[0]?.id || 0);
  const [title, setTitle] = useState("");

  useEffect(() => {
    const fallbackProjectId = currentProjectId || projects[0]?.id || 0;
    if (fallbackProjectId) setProjectId(fallbackProjectId);
  }, [currentProjectId, projects]);

  return (
    <div className="session-switch-sheet stack">
      <div className="wechat-form stack">
        <h3>快速新建</h3>
        <label>
          项目
          <select value={projectId} onChange={(event) => setProjectId(Number(event.target.value))}>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>{project.name}</option>
            ))}
          </select>
        </label>
        <label>
          会话标题
          <input value={title} onChange={(event) => setTitle(event.target.value)} />
        </label>
        {createDisabledReason ? <div className="inline-error">{createDisabledReason}</div> : null}
        <Button
          disabled={!projectId || Boolean(createDisabledReason)}
          onClick={() => onCreate(projectId, title)}
          title={createDisabledReason}
          variant="primary"
        >
          新建会话
        </Button>
      </div>
      <div className="wechat-section stack">
        <div className="section-title-row">
          <h3>最近会话</h3>
          <Button onClick={onRefresh} variant="secondary">刷新</Button>
        </div>
        <div className="segmented-control" aria-label="AppThread 状态筛选">
          {["", "ACTIVE", "ERROR", "CLOSED"].map((status) => (
            <button
              className={statusFilter === status ? "active" : ""}
              key={status || "all"}
              onClick={() => onStatusFilterChange(status)}
              type="button"
            >
              {status || "全部"}
            </button>
          ))}
        </div>
        <label className="inline">
          <input
            checked={includeArchived}
            onChange={(event) => onIncludeArchivedChange(event.target.checked)}
            type="checkbox"
          />{" "}
          显示 archived
        </label>
        {threads.map((thread) => (
          <button
            className={`wechat-row thread-card ${selectedThreadId === thread.id ? "selected" : ""}`}
            key={thread.id}
            onClick={() => onSelect(thread)}
            type="button"
          >
            <div className={`wechat-avatar ${statusTone(thread.status)}`}>会</div>
            <div className="wechat-row-main">
              <strong className="thread-title">{thread.title}</strong>
              <span>
                #{String(thread.id).slice(0, 8)} · {thread.turn_count} 轮 · {formatRelativeTime(thread.updated_at)}
              </span>
            </div>
            <Badge tone={statusTone(thread.status)}>{thread.status}</Badge>
          </button>
        ))}
      </div>
    </div>
  );
}
