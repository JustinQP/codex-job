import type { Task } from "../../api/types";
import { formatRelativeTime } from "../../utils/date";
import { shortText, statusTone } from "../../utils/text";
import { Badge } from "../common/Badge";
import { Button } from "../common/Button";

type TaskCardProps = {
  task: Task;
  onCancel: (task: Task) => void;
  onRerun: (task: Task) => void;
  onOpen: (task: Task) => void;
};

export function TaskCard({ task, onCancel, onRerun, onOpen }: TaskCardProps) {
  return (
    <article className="list-card task-card">
      <div className="task-card-header">
        <div>
          <h3 className="task-title">#{task.id} {shortText(task.prompt, 64)}</h3>
          <span className="muted">
            {task.task_type} · updated {formatRelativeTime(task.updated_at)}
          </span>
        </div>
        <Badge tone={statusTone(task.status)}>{task.status}</Badge>
      </div>
      <div className="meta-grid">
        <div className="meta-cell">
          <span className="meta-label">runner</span>
          <span className="meta-value">{task.assigned_runner_id || task.runner_id || "-"}</span>
        </div>
        <div className="meta-cell">
          <span className="meta-label">sandbox</span>
          <span className="meta-value">{task.sandbox || "-"}</span>
        </div>
      </div>
      {task.error_message ? <div className="inline-error">{task.error_message}</div> : null}
      <div className="task-actions">
        <Button onClick={() => onOpen(task)} variant="secondary">详情</Button>
        <Button onClick={() => onRerun(task)} variant="secondary">重跑</Button>
        <Button
          disabled={!["PENDING", "RUNNING"].includes(task.status)}
          onClick={() => onCancel(task)}
          variant="danger"
        >
          取消
        </Button>
      </div>
    </article>
  );
}
