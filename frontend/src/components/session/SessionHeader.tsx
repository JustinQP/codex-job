import type { AppThread, Device, Project, Workspace } from "../../api/types";
import { formatRelativeTime } from "../../utils/date";
import { statusTone } from "../../utils/text";
import { Badge } from "../common/Badge";
import { Button } from "../common/Button";

type SessionHeaderProps = {
  selectedThread: AppThread | null;
  currentProject: Project | null;
  threadDevice: Device | null;
  threadWorkspace: Workspace | null;
  onSwitch: () => void;
  onMore: () => void;
};

export function SessionHeader({
  currentProject,
  onMore,
  onSwitch,
  selectedThread,
  threadDevice,
  threadWorkspace
}: SessionHeaderProps) {
  if (!selectedThread) {
    return (
      <header className="session-header">
        <div className="session-header-main">
          <Button onClick={onSwitch} variant="text">≡</Button>
          <div className="session-title-area">
            <h2 className="session-title">Codex 会话</h2>
            <span className="session-subtitle">
              {currentProject ? `${currentProject.name} · ${currentProject.path_label}` : "选择工作空间后即可发送消息"}
            </span>
          </div>
          <div className="session-actions">
            <Button onClick={onSwitch} variant="text">选择</Button>
          </div>
        </div>
      </header>
    );
  }

  const updated = formatRelativeTime(selectedThread.updated_at);
  const deviceLabel = threadDevice?.display_name || selectedThread.device_id || "本机 Bridge";
  const workspaceLabel = threadWorkspace
    ? `${threadWorkspace.name} · ${threadWorkspace.path_label}`
    : selectedThread.workspace_id
      ? `Workspace #${selectedThread.workspace_id}`
      : currentProject?.path_label || "";
  const modeLabel = selectedThread.sandbox || "read-only";
  const deviceStatus = threadDevice?.status || selectedThread.status;
  return (
    <header className="session-header">
      <div className="session-header-main selected">
        <div className="session-title-area">
          <h2 className="session-title">{selectedThread.title}</h2>
          <span className="session-subtitle">
            {deviceLabel} · {workspaceLabel} · {modeLabel}
          </span>
          <span className="session-subtitle">
            {selectedThread.status} · G{selectedThread.generation} · {selectedThread.turn_count} 轮
            {updated ? ` · 更新 ${updated}` : ""}
          </span>
        </div>
        <div className="session-actions">
          <Badge tone={statusTone(deviceStatus)}>{deviceStatus}</Badge>
          <Badge tone={statusTone(selectedThread.status)}>{selectedThread.status}</Badge>
          <Button onClick={onSwitch} variant="text">切换</Button>
          <Button onClick={onMore} variant="text">···</Button>
        </div>
      </div>
    </header>
  );
}
