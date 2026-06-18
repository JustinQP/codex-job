import { useState } from "react";

import type { AppThread, Project } from "../../api/types";
import { formatRelativeTime } from "../../utils/date";
import { statusTone } from "../../utils/text";
import { Badge } from "../common/Badge";
import { Button } from "../common/Button";

type ThreadSwitcherSheetProps = {
  projects: Project[];
  threads: AppThread[];
  selectedThreadId: number | null;
  onCreate: (projectId: number, title: string) => void;
  onSelect: (thread: AppThread) => void;
  onRefresh: () => void;
};

export function ThreadSwitcherSheet({
  onCreate,
  onRefresh,
  onSelect,
  projects,
  selectedThreadId,
  threads
}: ThreadSwitcherSheetProps) {
  const [projectId, setProjectId] = useState(projects[0]?.id ?? 0);
  const [title, setTitle] = useState("");

  return (
    <div className="session-switch-sheet stack">
      <div className="detail-card stack">
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
        <Button disabled={!projectId} onClick={() => onCreate(projectId, title)} variant="primary">
          新建会话
        </Button>
      </div>
      <div className="detail-card stack">
        <div className="row">
          <h3>最近会话</h3>
          <Button onClick={onRefresh} variant="secondary">刷新</Button>
        </div>
        {threads.map((thread) => (
          <button
            className={`list-card thread-card ${selectedThreadId === thread.id ? "selected" : ""}`}
            key={thread.id}
            onClick={() => onSelect(thread)}
            type="button"
          >
            <div className="thread-card-header">
              <strong className="thread-title">{thread.title}</strong>
              <Badge tone={statusTone(thread.status)}>{thread.status}</Badge>
            </div>
            <span className="muted">
              #{String(thread.id).slice(0, 8)} · {thread.turn_count} 轮 · {formatRelativeTime(thread.updated_at)}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
