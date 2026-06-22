import type { Task } from "../../api/types";
import { Button } from "../common/Button";

type TaskDetailSheetProps = {
  task: Task;
  rerunDisabledReason?: string;
  onCancel: (task: Task) => void;
  onRerun: (task: Task) => void;
};

export function TaskDetailSheet({
  task,
  rerunDisabledReason = "",
  onCancel,
  onRerun
}: TaskDetailSheetProps) {
  const cancelLabel = task.cancel_requested && task.status !== "CANCELLED" ? "取消中" : "取消";

  return (
    <div className="task-detail-grid">
      <div className="detail-card">
        <h3>运行输入</h3>
        <pre>{task.prompt}</pre>
      </div>
      <div className="meta-grid">
        <Meta label="status" value={task.status} />
        <Meta label="task_type" value={task.task_type} />
        <Meta label="model" value={task.model || ""} />
        <Meta label="reasoning" value={task.reasoning_effort || ""} />
        <Meta label="sandbox" value={task.sandbox || ""} />
        <Meta label="timeout" value={String(task.timeout_seconds)} />
        <Meta label="device" value={task.device_display_name || task.device_id || ""} />
        <Meta label="workspace" value={task.workspace_name || task.workspace_path_label || ""} />
        <Meta label="device_status" value={task.device_status || ""} />
        <Meta label="cancel" value={task.cancel_requested ? "requested" : ""} />
      </div>
      {task.error_message ? <div className="inline-error">{task.error_message}</div> : null}
      <div className="task-actions">
        <Button onClick={() => window.open(task.log_url, "_blank")} variant="secondary">
          log
        </Button>
        <Button onClick={() => window.open(task.result_url, "_blank")} variant="secondary">
          result
        </Button>
        <Button onClick={() => window.open(task.diff_url, "_blank")} variant="secondary">
          diff
        </Button>
        <Button
          disabled={Boolean(rerunDisabledReason)}
          onClick={() => onRerun(task)}
          title={rerunDisabledReason}
          variant="secondary"
        >
          重跑
        </Button>
        <Button
          disabled={!["PENDING", "RUNNING"].includes(task.status)}
          onClick={() => onCancel(task)}
          variant="danger"
        >
          {cancelLabel}
        </Button>
      </div>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="meta-cell">
      <span className="meta-label">{label}</span>
      <span className="meta-value">{value || "-"}</span>
    </div>
  );
}
