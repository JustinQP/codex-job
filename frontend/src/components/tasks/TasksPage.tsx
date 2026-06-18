import { useCallback, useEffect, useMemo, useState } from "react";

import {
  cancelTask,
  createTask,
  listTaskTemplates,
  listTasks,
  rerunTask,
  type CreateTaskPayload
} from "../../api/tasks";
import type { Project, Runner, Task, TaskStatus, TaskTemplate } from "../../api/types";
import { listProjects } from "../../api/projects";
import { listRunners } from "../../api/runners";
import { useLocalStorage } from "../../hooks/useLocalStorage";
import { usePolling } from "../../hooks/usePolling";
import { UI_STATE_KEYS } from "../../state/storage";
import { errorText, isRunningStatus } from "../../utils/error";
import { Button } from "../common/Button";
import { EmptyState } from "../common/EmptyState";
import { Sheet } from "../layout/Sheet";
import type { PageProps } from "../types";
import { CreateTaskSheet } from "./CreateTaskSheet";
import { TaskCard } from "./TaskCard";
import { TaskDetailSheet } from "./TaskDetailSheet";

const statuses: Array<"" | TaskStatus> = ["", "PENDING", "RUNNING", "SUCCESS", "FAILED", "CANCELLED"];

export function TasksPage({ showToast }: PageProps) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [runners, setRunners] = useState<Runner[]>([]);
  const [templates, setTemplates] = useState<TaskTemplate[]>([]);
  const [statusFilter, setStatusFilter] = useLocalStorage(UI_STATE_KEYS.taskStatusFilter, "");
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const loadTasks = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [taskData, projectData, runnerData, templateData] = await Promise.all([
        listTasks(20),
        listProjects(),
        listRunners(),
        listTaskTemplates()
      ]);
      setTasks(taskData);
      setProjects(projectData);
      setRunners(runnerData);
      setTemplates(templateData);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadTasks();
  }, [loadTasks]);

  usePolling(loadTasks, 5000, tasks.some((task) => isRunningStatus(task.status)));

  const filteredTasks = useMemo(() => {
    if (!statusFilter) return tasks;
    return tasks.filter((task) => task.status === statusFilter);
  }, [statusFilter, tasks]);

  async function handleCreate(payload: CreateTaskPayload) {
    try {
      await createTask(payload);
      setCreating(false);
      showToast("任务已创建", "success");
      await loadTasks();
    } catch (err) {
      showToast(errorText(err), "error");
    }
  }

  async function handleCancel(task: Task) {
    if (!window.confirm(`确认取消任务 #${task.id}？`)) return;
    try {
      await cancelTask(task.id);
      showToast("任务已请求取消", "success");
      await loadTasks();
    } catch (err) {
      showToast(errorText(err), "error");
    }
  }

  async function handleRerun(task: Task) {
    try {
      const newTask = await rerunTask(task.id);
      showToast(`已创建重跑任务 #${newTask.id}`, "success");
      await loadTasks();
    } catch (err) {
      showToast(errorText(err), "error");
    }
  }

  return (
    <section className="page active" id="tab-tasks">
      <div className="page-header summary-card">
        <div className="row">
          <h2>任务</h2>
          <Button onClick={() => setCreating(true)} variant="primary">
            新建任务
          </Button>
        </div>
        <div className="segmented-control" aria-label="任务状态筛选">
          {statuses.map((status) => (
            <button
              className={statusFilter === status ? "active" : ""}
              key={status || "all"}
              onClick={() => setStatusFilter(status)}
              type="button"
            >
              {status || "全部"}
            </button>
          ))}
        </div>
        <div className="muted">
          {loading ? "刷新中" : `显示 ${filteredTasks.length}/${tasks.length} 个任务`}
        </div>
      </div>

      {error ? <div className="inline-error">{error}</div> : null}

      <div className="page-body stack">
        {filteredTasks.length ? (
          filteredTasks.map((task) => (
            <TaskCard
              key={task.id}
              onCancel={handleCancel}
              onOpen={setSelectedTask}
              onRerun={handleRerun}
              task={task}
            />
          ))
        ) : (
          <EmptyState title="没有匹配任务" description="可以调整筛选或创建新任务。" />
        )}
      </div>

      {creating ? (
        <Sheet onClose={() => setCreating(false)} title="新建任务">
          <CreateTaskSheet
            onSubmit={handleCreate}
            projects={projects}
            runners={runners}
            templates={templates}
          />
        </Sheet>
      ) : null}

      {selectedTask ? (
        <Sheet onClose={() => setSelectedTask(null)} title={`任务 #${selectedTask.id}`}>
          <TaskDetailSheet onCancel={handleCancel} onRerun={handleRerun} task={selectedTask} />
        </Sheet>
      ) : null}
    </section>
  );
}
