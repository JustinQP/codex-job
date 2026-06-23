import { useCallback, useEffect, useMemo, useState } from "react";

import { listAppThreads } from "../../api/appThreads";
import { listDevices } from "../../api/devices";
import { listProjects } from "../../api/projects";
import { listRuns } from "../../api/runs";
import type { AppThread, Device, Project, Run, Workspace } from "../../api/types";
import { listWorkspaces } from "../../api/workspaces";
import { useLocalStorage } from "../../hooks/useLocalStorage";
import { UI_STATE_KEYS } from "../../state/storage";
import { formatRelativeTime } from "../../utils/date";
import { errorText, isRunningStatus } from "../../utils/error";
import { statusTone } from "../../utils/text";
import { Badge } from "../common/Badge";
import { EmptyState } from "../common/EmptyState";
import type { PageProps } from "../types";

export function ProjectsPage({ showToast }: PageProps) {
  const [, setActiveTab] = useLocalStorage(UI_STATE_KEYS.activeTab, "app");
  const [currentProjectIdText, setCurrentProjectIdText] = useLocalStorage(
    UI_STATE_KEYS.currentProjectId,
    ""
  );
  const [currentDeviceIdText, setCurrentDeviceIdText] = useLocalStorage(
    UI_STATE_KEYS.currentDeviceId,
    ""
  );
  const [currentWorkspaceIdText, setCurrentWorkspaceIdText] = useLocalStorage(
    UI_STATE_KEYS.currentWorkspaceId,
    ""
  );
  const [, setSelectedThreadIdText] = useLocalStorage(UI_STATE_KEYS.selectedAppThreadId, "");
  const [devices, setDevices] = useState<Device[]>([]);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [threads, setThreads] = useState<AppThread[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const currentProjectId = currentProjectIdText ? Number(currentProjectIdText) : null;
  const currentWorkspaceId = currentWorkspaceIdText ? Number(currentWorkspaceIdText) : null;
  const currentDevice = useMemo(() => {
    return devices.find((device) => device.device_id === currentDeviceIdText)
      || devices.find((device) => device.status === "ONLINE")
      || devices[0]
      || null;
  }, [currentDeviceIdText, devices]);
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

  const loadWorkspace = useCallback(async () => {
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
      setDevices(deviceData);
      setWorkspaces(workspaceData);
      if (!currentDeviceIdText && effectiveDevice) {
        setCurrentDeviceIdText(effectiveDevice.device_id);
      }
      if (!selectedWorkspace && currentWorkspaceIdText) {
        setCurrentWorkspaceIdText("");
      } else if (!currentWorkspaceIdText && fallbackWorkspace) {
        setCurrentWorkspaceIdText(String(fallbackWorkspace.id));
      }
      const selectedProject = currentProjectId
        ? projectData.find((project) => project.id === currentProjectId)
        : null;
      const fallbackProject = projectData.find((project) => project.enabled) || projectData[0] || null;
      const effectiveProject = selectedProject || fallbackProject;
      setProjects(projectData);
      if (!currentProjectIdText && effectiveProject) {
        setCurrentProjectIdText(String(effectiveProject.id));
      }
      if (effectiveProject) {
        const [threadData, runData] = await Promise.all([
          listAppThreads({ limit: 5, projectId: effectiveProject.id }),
          listRuns({ limit: 5, projectId: effectiveProject.id })
        ]);
        setThreads(threadData);
        setRuns(runData);
      } else {
        setThreads([]);
        setRuns([]);
      }
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
    currentWorkspaceIdText,
    setCurrentDeviceIdText,
    setCurrentProjectIdText,
    setCurrentWorkspaceIdText
  ]);

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  const runningCount = runs.filter((run) => isRunningStatus(run.status)).length;
  const failedCount = runs.filter((run) => run.status === "FAILED").length;
  const activeThreads = threads.filter((thread) => thread.status === "ACTIVE").length;

  function handleSelectProject(project: Project) {
    setCurrentProjectIdText(String(project.id));
    setSelectedThreadIdText("");
    showToast(`当前工作空间已切换为 ${project.name}`, "success");
  }

  function handleSelectDevice(device: Device) {
    setCurrentDeviceIdText(device.device_id);
    setCurrentWorkspaceIdText("");
    setSelectedThreadIdText("");
    showToast(`当前设备已切换为 ${device.display_name}`, "success");
  }

  function handleSelectWorkspace(workspace: Workspace) {
    setCurrentWorkspaceIdText(String(workspace.id));
    setSelectedThreadIdText("");
    showToast(`当前 Workspace 已切换为 ${workspace.name}`, "success");
  }

  function handleOpenThread(thread: AppThread) {
    setSelectedThreadIdText(String(thread.id));
    setActiveTab("app");
  }

  return (
    <section className="page active" id="tab-projects">
      <div className="profile-hero">
        <div className={`profile-avatar ${currentProject?.enabled ? "online" : "closed"}`}>项</div>
        <div>
          <h2>{currentProject?.name || "未选择工作空间"}</h2>
          <p>{currentProject?.path_label || (loading ? "加载工作空间中" : "暂无项目")}</p>
        </div>
      </div>

      {error ? <div className="inline-error">{error}</div> : null}

      <section className="wechat-section">
        <div className="section-title-row">
          <h2>设备</h2>
          <span className="muted">{loading ? "刷新中" : `${devices.length} 台设备`}</span>
        </div>
        {devices.length ? (
          <div className="wechat-list">
            {devices.map((device) => (
              <button
                className={`wechat-row as-button ${currentDevice?.device_id === device.device_id ? "selected" : ""}`}
                key={device.device_id}
                onClick={() => handleSelectDevice(device)}
                type="button"
              >
                <div className={`wechat-avatar ${device.status === "ONLINE" ? "online" : "closed"}`}>设</div>
                <div className="wechat-row-main">
                  <strong>{device.display_name}</strong>
                  <span>{device.hostname} · {device.os_name}</span>
                </div>
                <Badge tone={device.status === "ONLINE" ? "online" : "closed"}>{device.status}</Badge>
              </button>
            ))}
          </div>
        ) : (
          <EmptyState title="暂无设备" />
        )}
      </section>

      <section className="wechat-section">
        <div className="section-title-row">
          <h2>Workspace</h2>
          <span className="muted">{currentDevice ? currentDevice.display_name : "未选择设备"}</span>
        </div>
        {workspaces.length ? (
          <div className="wechat-list">
            {workspaces.map((workspace) => (
              <button
                className={`wechat-row as-button ${currentWorkspace?.id === workspace.id ? "selected" : ""}`}
                key={workspace.id}
                onClick={() => handleSelectWorkspace(workspace)}
                type="button"
              >
                <div className={`wechat-avatar ${workspace.enabled ? "online" : "closed"}`}>目</div>
                <div className="wechat-row-main">
                  <strong>{workspace.name}</strong>
                  <span>{workspace.path_label}</span>
                </div>
                <Badge tone={workspace.enabled ? "online" : "closed"}>{workspace.enabled ? "启用" : "停用"}</Badge>
              </button>
            ))}
          </div>
        ) : (
          <EmptyState title={currentDevice ? "当前设备暂无 Workspace" : "请选择设备"} />
        )}
      </section>

      {currentProject ? (
        <section className="wechat-form stack">
          <div className="section-title-row">
            <h3>当前工作空间</h3>
            <Badge tone={currentProject.enabled ? "online" : "closed"}>
              {currentProject.enabled ? "可用" : "停用"}
            </Badge>
          </div>
          <div className="meta-grid">
            <Meta label="路径" value={currentProject.path_label} />
            <Meta label="设备" value={currentDevice?.display_name || "未选择"} />
            <Meta label="Workspace" value={currentWorkspace?.name || "未选择"} />
            <Meta label="模型" value={currentProject.default_model || "未指定"} />
            <Meta label="sandbox" value={currentProject.default_sandbox || "workspace-write"} />
          </div>
          <div className="meta-grid">
            <Meta label="活跃会话" value={`${activeThreads}`} />
            <Meta label="运行中" value={`${runningCount}`} />
            <Meta label="失败运行" value={`${failedCount}`} />
            <Meta label="更新时间" value={formatRelativeTime(currentProject.updated_at) || "-"} />
          </div>
        </section>
      ) : null}

      <section className="wechat-section">
        <div className="section-title-row">
          <h2>工作空间状态</h2>
          <span className="muted">{loading ? "刷新中" : "按当前项目筛选"}</span>
        </div>
        <div className="meta-grid">
          <Meta label="项目启用" value={currentProject?.enabled ? "是" : "否"} />
          <Meta label="会话范围" value={currentProject ? "当前工作空间" : "-"} />
          <Meta label="运行范围" value={currentProject ? "当前工作空间" : "-"} />
          <Meta label="会话模式" value={currentProject ? "Device Agent" : "-"} />
        </div>
      </section>

      <section className="wechat-section">
        <div className="section-title-row">
          <h2>项目列表</h2>
          <span className="muted">{loading ? "刷新中" : `${projects.length} 个项目`}</span>
        </div>
        {projects.length ? (
          <div className="wechat-list">
            {projects.map((project) => (
              <button
                className={`wechat-row as-button ${currentProject?.id === project.id ? "selected" : ""}`}
                key={project.id}
                onClick={() => handleSelectProject(project)}
                type="button"
              >
                <div className={`wechat-avatar ${project.enabled ? "online" : "closed"}`}>项</div>
                <div className="wechat-row-main">
                  <strong>{project.name}</strong>
                  <span>{project.path_label}</span>
                </div>
                <Badge tone={project.enabled ? "online" : "closed"}>
                  {project.enabled ? "启用" : "停用"}
                </Badge>
              </button>
            ))}
          </div>
        ) : (
          <EmptyState title="暂无项目" />
        )}
      </section>

      <section className="wechat-section">
        <div className="section-title-row">
          <h2>当前工作空间最近会话</h2>
          <span className="muted">{threads.length ? "点击进入" : ""}</span>
        </div>
        {threads.length ? (
          <div className="wechat-list">
            {threads.map((thread) => (
              <button
                className="wechat-row as-button"
                key={thread.id}
                onClick={() => handleOpenThread(thread)}
                type="button"
              >
                <div className={`wechat-avatar ${statusTone(thread.status)}`}>会</div>
                <div className="wechat-row-main">
                  <strong>{thread.title}</strong>
                  <span>{thread.turn_count} 轮 · {formatRelativeTime(thread.updated_at)}</span>
                </div>
                <Badge tone={statusTone(thread.status)}>{thread.status}</Badge>
              </button>
            ))}
          </div>
        ) : (
          <EmptyState title="暂无当前工作空间会话" />
        )}
      </section>

      <section className="wechat-section">
        <div className="section-title-row">
          <h2>当前工作空间最近运行</h2>
          <span className="muted">{runs.length ? "按时间排序" : ""}</span>
        </div>
        {runs.length ? (
          <div className="wechat-list">
            {runs.map((run) => (
              <div className="wechat-row" key={run.id}>
                <div className={`wechat-avatar ${statusTone(run.status)}`}>运</div>
                <div className="wechat-row-main">
                  <strong>#{run.id} · {run.run_type}</strong>
                  <span>{formatRelativeTime(run.updated_at)} · {run.prompt}</span>
                </div>
                <Badge tone={statusTone(run.status)}>{run.status}</Badge>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState title="暂无当前工作空间运行记录" />
        )}
      </section>
    </section>
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
