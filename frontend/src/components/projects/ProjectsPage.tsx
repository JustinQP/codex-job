import { useCallback, useEffect, useMemo, useState } from "react";

import { listAppThreads } from "../../api/appThreads";
import { listProjects } from "../../api/projects";
import { listTasks } from "../../api/tasks";
import type { AppThread, Project, Task } from "../../api/types";
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
  const [, setSelectedThreadIdText] = useLocalStorage(UI_STATE_KEYS.selectedAppThreadId, "");
  const [projects, setProjects] = useState<Project[]>([]);
  const [threads, setThreads] = useState<AppThread[]>([]);
  const [runs, setRuns] = useState<Task[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const currentProjectId = currentProjectIdText ? Number(currentProjectIdText) : null;
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
      const projectData = await listProjects();
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
          listTasks({ limit: 5, projectId: effectiveProject.id })
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
  }, [currentProjectId, currentProjectIdText, setCurrentProjectIdText]);

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
            <Meta label="Runner" value={currentProject.default_runner_id || "项目默认"} />
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
          <Meta label="Bridge cwd" value={currentProject ? "跟随工作空间" : "-"} />
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
                  <strong>#{run.id} · {run.task_type}</strong>
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
