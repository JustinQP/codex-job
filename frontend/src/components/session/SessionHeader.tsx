import type { AppThread, Project } from "../../api/types";
import { formatRelativeTime } from "../../utils/date";
import { statusTone } from "../../utils/text";
import { Badge } from "../common/Badge";
import { Button } from "../common/Button";

type SessionHeaderProps = {
  selectedThread: AppThread | null;
  currentProject: Project | null;
  onSwitch: () => void;
  onMore: () => void;
};

export function SessionHeader({ currentProject, onMore, onSwitch, selectedThread }: SessionHeaderProps) {
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
  return (
    <header className="session-header">
      <div className="session-header-main selected">
        <div className="session-title-area">
          <h2 className="session-title">{selectedThread.title}</h2>
          <span className="session-subtitle">
            {currentProject ? `${currentProject.name} · ` : ""}
            {selectedThread.status} · {selectedThread.turn_count} 轮
            {updated ? ` · 更新 ${updated}` : ""}
          </span>
        </div>
        <div className="session-actions">
          <Badge tone={statusTone(selectedThread.status)}>{selectedThread.status}</Badge>
          <Button onClick={onSwitch} variant="text">切换</Button>
          <Button onClick={onMore} variant="text">···</Button>
        </div>
      </div>
    </header>
  );
}
