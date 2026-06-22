import { useCallback, useEffect, useMemo, useState } from "react";

import { listDevices } from "../../api/devices";
import { listProjects } from "../../api/projects";
import { cancelTask, listTasks, rerunTask } from "../../api/tasks";
import type { Device, Project, Task, TaskStatus, Workspace } from "../../api/types";
import { listWorkspaces } from "../../api/workspaces";
import { useLocalStorage } from "../../hooks/useLocalStorage";
import { usePolling } from "../../hooks/usePolling";
import { UI_STATE_KEYS } from "../../state/storage";
import { deviceDisabledReason } from "../../utils/device";
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
  const [devices, setDevices] = useState<Device[]>([]);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [showAllHistory, setShowAllHistory] = useState(false);
  const [currentProjectIdText, setCurrentProjectIdText] = useLocalStorage(
    UI_STATE_KEYS.currentProjectId,
    ""
  );
  const [currentDeviceIdText] = useLocalStorage(UI_STATE_KEYS.currentDeviceId, "");
  const [currentWorkspaceIdText] = useLocalStorage(UI_STATE_KEYS.currentWorkspaceId, "");
  const [statusFilter, setStatusFilter] = useLocalStorage(UI_STATE_KEYS.taskStatusFilter, "");
  const [selectedRun, setSelectedRun] = useState<Task | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const currentProjectId = currentProjectIdText ? Number(currentProjectIdText) : null;
  const currentWorkspaceId = currentWorkspaceIdText ? Number(currentWorkspaceIdText) : null;
  const currentDevice = useMemo(() => {
    return devices.find((device) => device.device_id === currentDeviceIdText)
      || devices.find((device) => device.status === "ONLINE")
      || devices[0]
      || null;
  }, [currentDeviceIdText, devices]);
  const rerunDisabledReason = devices.length ? deviceDisabledReason(currentDevice) : "";
  const currentWorkspace = useMemo(() => {
    return workspaces.find((workspace) => workspace.id === currentWorkspaceId)
      || workspaces.find((workspace) => workspace.enabled)
      || workspaces[0]
      || null;
  }, [currentWorkspaceId, workspaces]);
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
      const [deviceData, projectData] = await Promise.all([
        listDevices().catch(() => [] as Device[]),
        listProjects()
      ]);
      const selectedDevice = currentDeviceIdText
        ? deviceData.find((device) => device.device_id === currentDeviceIdText)
        : null;
      const fallbackDevice = deviceData.find((device) => device.status === "ONLINE") || deviceData[0] || null;
      const effectiveDevice = selectedDevice || fallbackDevice;
      const workspaceData = effectiveDevice ? await listWorkspaces(effectiveDevice.device_id) : [];
      const selectedWorkspace = currentWorkspaceId
        ? workspaceData.find((workspace) => workspace.id === currentWorkspaceId)
        : null;
      const fallbackWorkspace = workspaceData.find((workspace) => workspace.enabled) || workspaceData[0] || null;
      const effectiveWorkspaceId = selectedWorkspace?.id || fallbackWorkspace?.id || null;
      const effectiveProject = currentProjectId
        ? projectData.find((project) => project.id === currentProjectId)
        : null;
      const fallbackProject = projectData.find((project) => project.enabled) || projectData[0] || null;
      const effectiveProjectId = effectiveProject?.id || fallbackProject?.id || null;
      setDevices(deviceData);
      setProjects(projectData);
      setWorkspaces(workspaceData);
      if (!currentProjectIdText && effectiveProjectId) {
        setCurrentProjectIdText(String(effectiveProjectId));
      }
      const workspaceFilter = showAllHistory ? null : effectiveWorkspaceId;
      setRuns(
        effectiveProjectId
          ? await listTasks({ limit: 50, projectId: effectiveProjectId, workspaceId: workspaceFilter })
          : []
      );
    } catch (err) {
      setError(errorText(err));
    } finally {
      setLoading(false);
    }
  }, [
    currentDeviceIdText,
    currentProjectId,
    currentProjectIdText,
    currentWorkspaceId,
    setCurrentProjectIdText,
    showAllHistory,
  ]);

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
    if (rerunDisabledReason) {
      showToast(rerunDisabledReason, "warning");
      return;
    }
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
              : `${currentWorkspace?.name || currentProject?.name || "未选择 Workspace"} · 运行中 ${runningCount} · 失败 ${failedCount} · 共 ${runs.length} 条`}
          </span>
        </div>
      </div>

      <div className="wechat-section">
        <div className="context-strip">
          <span>{currentDevice?.display_name || "未选择设备"}</span>
          <span>{currentWorkspace?.path_label || "未选择目录"}</span>
          <span>{showAllHistory ? "全部历史" : "当前 Workspace"}</span>
        </div>
        {rerunDisabledReason ? <div className="inline-error">{rerunDisabledReason}</div> : null}
        <div className="segmented-control" aria-label="运行历史范围">
          <button className={!showAllHistory ? "active" : ""} onClick={() => setShowAllHistory(false)} type="button">
            当前 Workspace
          </button>
          <button className={showAllHistory ? "active" : ""} onClick={() => setShowAllHistory(true)} type="button">
            全部设备历史
          </button>
        </div>
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
              rerunDisabledReason={rerunDisabledReason}
              task={run}
            />
          ))
        ) : (
          <EmptyState title="没有匹配运行记录" description="可以调整运行状态筛选。" />
        )}
      </div>

      {selectedRun ? (
        <Sheet onClose={() => setSelectedRun(null)} title={`运行 #${selectedRun.id}`}>
          <TaskDetailSheet
            onCancel={handleCancel}
            onRerun={handleRerun}
            rerunDisabledReason={rerunDisabledReason}
            task={selectedRun}
          />
        </Sheet>
      ) : null}
    </section>
  );
}
