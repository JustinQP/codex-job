import { useCallback, useEffect, useMemo, useState } from "react";

import { listDevices } from "../../api/devices";
import { listProjects } from "../../api/projects";
import { cancelRun, listRuns, rerunRun } from "../../api/runs";
import type { Device, Project, Run, RunStatus, Workspace } from "../../api/types";
import { listWorkspaces } from "../../api/workspaces";
import { useLocalStorage } from "../../hooks/useLocalStorage";
import { usePolling } from "../../hooks/usePolling";
import { UI_STATE_KEYS } from "../../state/storage";
import { formatRelativeTime } from "../../utils/date";
import { deviceDisabledReason } from "../../utils/device";
import { errorText, isRunningStatus } from "../../utils/error";
import { statusTone, shortText } from "../../utils/text";
import { Badge } from "../common/Badge";
import { Button } from "../common/Button";
import { EmptyState } from "../common/EmptyState";
import { Sheet } from "../layout/Sheet";
import type { PageProps } from "../types";

const statuses: Array<"" | RunStatus> = ["", "PENDING", "RUNNING", "SUCCESS", "FAILED", "CANCELLED"];

export function RunsPage({ showToast }: PageProps) {
  const [runs, setRuns] = useState<Run[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [showAllHistory, setShowAllHistory] = useState(false);
  const [currentProjectIdText, setCurrentProjectIdText] = useLocalStorage(UI_STATE_KEYS.currentProjectId, "");
  const [currentDeviceIdText] = useLocalStorage(UI_STATE_KEYS.currentDeviceId, "");
  const [currentWorkspaceIdText] = useLocalStorage(UI_STATE_KEYS.currentWorkspaceId, "");
  const [statusFilter, setStatusFilter] = useLocalStorage(UI_STATE_KEYS.taskStatusFilter, "");
  const [selectedRun, setSelectedRun] = useState<Run | null>(null);
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
      const selectedProject = currentProjectId
        ? projectData.find((project) => project.id === currentProjectId)
        : null;
      const fallbackProject = projectData.find((project) => project.enabled) || projectData[0] || null;
      const effectiveProjectId = selectedProject?.id || fallbackProject?.id || null;
      setDevices(deviceData);
      setProjects(projectData);
      setWorkspaces(workspaceData);
      if (!currentProjectIdText && effectiveProjectId) {
        setCurrentProjectIdText(String(effectiveProjectId));
      }
      const workspaceFilter = showAllHistory ? null : effectiveWorkspaceId;
      setRuns(
        effectiveProjectId
          ? await listRuns({ limit: 50, projectId: effectiveProjectId, workspaceId: workspaceFilter })
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

  async function handleCancel(run: Run) {
    if (!window.confirm(`确认取消运行 #${run.id}？`)) return;
    try {
      await cancelRun(run.id);
      showToast("运行已请求取消", "success");
      await loadRuns();
    } catch (err) {
      showToast(errorText(err), "error");
    }
  }

  async function handleRerun(run: Run) {
    if (rerunDisabledReason) {
      showToast(rerunDisabledReason, "warning");
      return;
    }
    try {
      const newRun = await rerunRun(run.id);
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
            <RunCard
              key={run.id}
              onCancel={handleCancel}
              onOpen={setSelectedRun}
              onRerun={handleRerun}
              rerunDisabledReason={rerunDisabledReason}
              run={run}
            />
          ))
        ) : (
          <EmptyState title="没有匹配运行记录" description="可以调整运行状态筛选。" />
        )}
      </div>

      {selectedRun ? (
        <Sheet onClose={() => setSelectedRun(null)} title={`运行 #${selectedRun.id}`}>
          <RunDetail
            onCancel={handleCancel}
            onRerun={handleRerun}
            rerunDisabledReason={rerunDisabledReason}
            run={selectedRun}
          />
        </Sheet>
      ) : null}
    </section>
  );
}

function RunCard({
  onCancel,
  onOpen,
  onRerun,
  rerunDisabledReason,
  run
}: {
  onCancel: (run: Run) => void;
  onOpen: (run: Run) => void;
  onRerun: (run: Run) => void;
  rerunDisabledReason: string;
  run: Run;
}) {
  const running = isRunningStatus(run.status);
  return (
    <div className="task-card">
      <button className="task-main as-button" onClick={() => onOpen(run)} type="button">
        <div className={`wechat-avatar ${statusTone(run.status)}`}>运</div>
        <div className="task-main-text">
          <strong>#{run.id} · {run.run_type}</strong>
          <span>{shortText(run.prompt, 80)}</span>
          <span>{run.workspace_name || run.workspace_path_label || "Workspace"} · {formatRelativeTime(run.updated_at)}</span>
        </div>
        <Badge tone={statusTone(run.status)}>{run.status}</Badge>
      </button>
      <div className="task-actions">
        {running ? <Button onClick={() => onCancel(run)} variant="secondary">取消</Button> : null}
        <Button disabled={Boolean(rerunDisabledReason)} onClick={() => onRerun(run)} variant="secondary">
          重跑
        </Button>
      </div>
    </div>
  );
}

function RunDetail({
  onCancel,
  onRerun,
  rerunDisabledReason,
  run
}: {
  onCancel: (run: Run) => void;
  onRerun: (run: Run) => void;
  rerunDisabledReason: string;
  run: Run;
}) {
  const running = isRunningStatus(run.status);
  return (
    <div className="stack">
      <div className="meta-grid">
        <Meta label="状态" value={run.status} />
        <Meta label="类型" value={run.run_type} />
        <Meta label="设备" value={run.device_display_name || run.device_id || "-"} />
        <Meta label="Workspace" value={run.workspace_name || run.workspace_path_label || "-"} />
        <Meta label="模型" value={run.model || "默认"} />
        <Meta label="sandbox" value={run.sandbox || "workspace-write"} />
        <Meta label="创建" value={formatRelativeTime(run.created_at) || "-"} />
        <Meta label="更新" value={formatRelativeTime(run.updated_at) || "-"} />
      </div>
      <div>
        <h3>Prompt</h3>
        <pre className="code-block">{run.prompt}</pre>
      </div>
      {run.error_message ? <div className="inline-error">{run.error_message}</div> : null}
      <div className="task-actions">
        {running ? <Button onClick={() => onCancel(run)} variant="secondary">取消</Button> : null}
        <Button disabled={Boolean(rerunDisabledReason)} onClick={() => onRerun(run)} variant="primary">
          重跑
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
