import { useCallback, useEffect, useMemo, useState } from "react";

import { listProjects } from "../../api/projects";
import { cancelTask, listTasks, rerunTask } from "../../api/tasks";
import type { Project, Task, TaskStatus } from "../../api/types";
import { useLocalStorage } from "../../hooks/useLocalStorage";
import { usePolling } from "../../hooks/usePolling";
import { UI_STATE_KEYS } from "../../state/storage";
import { errorText, isRunningStatus } from "../../utils/error";
import { EmptyState } from "../common/EmptyState";
import { Sheet } from "../layout/Sheet";
import { TaskCard } from "../tasks/TaskCard";
import { TaskDetailSheet } from "../tasks/TaskDetailSheet";
import type { PageProps } from "../types";

const statuses: Array<"" | TaskStatus> = ["", "PENDING", "RUNNING", "SUCCESS", "FAILED", "CANCELLED"];

export function RunsPage({ showToast }: PageProps) {
  const [runs, setRuns] = useState<Task[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [currentProjectIdText, setCurrentProjectIdText] = useLocalStorage(
    UI_STATE_KEYS.currentProjectId,
    ""
  );
  const [statusFilter, setStatusFilter] = useLocalStorage(UI_STATE_KEYS.taskStatusFilter, "");
  const [selectedRun, setSelectedRun] = useState<Task | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const currentProjectId = currentProjectIdText ? Number(currentProjectIdText) : null;
  const currentProject = useMemo(() => {
    return projects.find((project) => project.id === currentProjectId)
      || projects.find((project) => project.enabled)
      || projects[0]
      || null;
  }, [currentProjectId, projects]);

  const loadRuns = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const projectData = await listProjects();
      const effectiveProject = currentProjectId
        ? projectData.find((project) => project.id === currentProjectId)
        : null;
      const fallbackProject = projectData.find((project) => project.enabled) || projectData[0] || null;
      const effectiveProjectId = effectiveProject?.id || fallbackProject?.id || null;
      setProjects(projectData);
      if (!currentProjectIdText && effectiveProjectId) {
        setCurrentProjectIdText(String(effectiveProjectId));
      }
      setRuns(effectiveProjectId ? await listTasks({ limit: 20, projectId: effectiveProjectId }) : []);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setLoading(false);
    }
  }, [currentProjectId, currentProjectIdText, setCurrentProjectIdText]);

  useEffect(() => {
    void loadRuns();
  }, [loadRuns]);

  usePolling(loadRuns, 5000, runs.some((run) => isRunningStatus(run.status)));

  const filteredRuns = useMemo(() => {
    if (!statusFilter) return runs;
    return runs.filter((run) => run.status === statusFilter);
  }, [statusFilter, runs]);
  const runningCount = runs.filter((run) => ["PENDING", "RUNNING"].includes(run.status)).length;
  const failedCount = runs.filter((run) => run.status === "FAILED").length;

  async function handleCancel(run: Task) {
    if (!window.confirm(`确认取消运行 #${run.id}？`)) return;
    try {
      await cancelTask(run.id);
      showToast("运行已请求取消", "success");
      await loadRuns();
    } catch (err) {
      showToast(errorText(err), "error");
    }
  }

  async function handleRerun(run: Task) {
    try {
      const newRun = await rerunTask(run.id);
      showToast(`已创建重跑运行 #${newRun.id}`, "success");
      await loadRuns();
    } catch (err) {
      showToast(errorText(err), "error");
    }
  }

  return (
    <section className="page active" id="tab-runs">
      <div className="tasks-toolbar">
        <div>
          <h2>运行记录</h2>
          <span>
            {loading
              ? "刷新中"
              : `${currentProject?.name || "未选择工作空间"} · 运行中 ${runningCount} · 失败 ${failedCount} · 共 ${runs.length} 条`}
          </span>
        </div>
      </div>

      <div className="wechat-section">
        <div className="segmented-control" aria-label="运行状态筛选">
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
      </div>

      {error ? <div className="inline-error">{error}</div> : null}

      <div className="task-list">
        {filteredRuns.length ? (
          filteredRuns.map((run) => (
            <TaskCard
              key={run.id}
              onCancel={handleCancel}
              onOpen={setSelectedRun}
              onRerun={handleRerun}
              task={run}
            />
          ))
        ) : (
          <EmptyState title="没有匹配运行记录" description="可以调整运行状态筛选。" />
        )}
      </div>

      {selectedRun ? (
        <Sheet onClose={() => setSelectedRun(null)} title={`运行 #${selectedRun.id}`}>
          <TaskDetailSheet onCancel={handleCancel} onRerun={handleRerun} task={selectedRun} />
        </Sheet>
      ) : null}
    </section>
  );
}
