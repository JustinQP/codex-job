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
  const runnerLabel = task.assigned_runner_id || task.runner_id || "自动分配";

  return (
    <article className="task-card">
      <button className="task-card-main" onClick={() => onOpen(task)} type="button">
        <div className={`wechat-avatar ${statusTone(task.status)}`}>{task.id}</div>
        <div className="task-card-copy">
          <div className="task-card-title-row">
            <h3 className="task-title">{shortText(task.prompt, 58)}</h3>
            <Badge tone={statusTone(task.status)}>{task.status}</Badge>
          </div>
          <span className="muted">
            {task.task_type} · {runnerLabel} · {formatRelativeTime(task.updated_at)}
          </span>
        </div>
      </button>
      {task.error_message ? <div className="inline-error">{task.error_message}</div> : null}
      <div className="task-actions">
        <Button onClick={() => onOpen(task)} variant="secondary">查看</Button>
        <details className="task-more-actions">
          <summary>更多</summary>
          <div>
            <Button onClick={() => onRerun(task)} variant="secondary">重跑</Button>
            <Button
              disabled={!["PENDING", "RUNNING"].includes(task.status)}
              onClick={() => onCancel(task)}
              variant="danger"
            >
              取消
            </Button>
          </div>
        </details>
      </div>
    </article>
  );
}
