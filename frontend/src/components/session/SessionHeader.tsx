import type { AppThread } from "../../api/types";
import { formatRelativeTime } from "../../utils/date";
import { statusTone } from "../../utils/text";
import { Badge } from "../common/Badge";
import { Button } from "../common/Button";

type SessionHeaderProps = {
  selectedThread: AppThread | null;
  onSwitch: () => void;
  onMore: () => void;
};

export function SessionHeader({ onMore, onSwitch, selectedThread }: SessionHeaderProps) {
  if (!selectedThread) {
    return (
      <header className="session-header">
        <div className="session-header-main">
          <div className="session-title-area">
            <h2 className="session-title">开始一次 Codex 会话</h2>
            <span className="session-subtitle">选择或新建会话后即可发送消息</span>
          </div>
          <div className="session-actions">
            <Button onClick={onSwitch} variant="text">新建</Button>
            <Button onClick={onSwitch} variant="text">选择</Button>
          </div>
        </div>
      </header>
    );
  }

  const updated = formatRelativeTime(selectedThread.updated_at);
  return (
    <header className="session-header">
      <div className="session-header-main">
        <div className="session-title-area">
          <h2 className="session-title">{selectedThread.title}</h2>
          <span className="session-subtitle">
            状态 {selectedThread.status} · {selectedThread.turn_count} 轮
            {updated ? ` · 更新 ${updated}` : ""}
          </span>
        </div>
        <Badge tone={statusTone(selectedThread.status)}>{selectedThread.status}</Badge>
        <div className="session-actions">
          <Button onClick={onSwitch} variant="text">切换</Button>
          <Button onClick={onMore} variant="text">更多</Button>
        </div>
      </div>
    </header>
  );
}
