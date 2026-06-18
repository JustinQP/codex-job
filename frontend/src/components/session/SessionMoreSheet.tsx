import type { AppThread } from "../../api/types";
import { Badge } from "../common/Badge";
import { Button } from "../common/Button";

type SessionMoreSheetProps = {
  selectedThread: AppThread | null;
  onCancelTurn: () => void;
  onCloseThread: () => void;
  onEvents: () => void;
  onFinal: () => void;
  onRefreshTurns: () => void;
  onReopen: () => void;
  onRecoverStale: () => void;
  onCleanup: (status: string) => void;
};

export function SessionMoreSheet({
  onCancelTurn,
  onCleanup,
  onCloseThread,
  onEvents,
  onFinal,
  onRecoverStale,
  onRefreshTurns,
  onReopen,
  selectedThread
}: SessionMoreSheetProps) {
  return (
    <div className="session-more-sheet stack">
      <div className="detail-card">
        <h3>{selectedThread?.title || "当前会话"}</h3>
        {selectedThread ? <Badge tone={selectedThread.status}>{selectedThread.status}</Badge> : null}
      </div>
      <div className="detail-card stack">
        <h3>常用</h3>
        <div className="task-actions">
          <Button onClick={onRefreshTurns} variant="secondary">刷新会话</Button>
          <Button onClick={onFinal} variant="secondary">查看最终回复</Button>
          <Button onClick={onEvents} variant="secondary">查看事件摘要</Button>
        </div>
      </div>
      <div className="detail-card stack">
        <h3>会话管理</h3>
        <div className="task-actions">
          <Button onClick={onReopen} variant="secondary">重开</Button>
          <Button onClick={onCancelTurn} variant="danger">取消当前 Turn</Button>
          <Button onClick={onCloseThread} variant="danger">关闭会话</Button>
        </div>
      </div>
      <details className="detail-card">
        <summary>调试与维护</summary>
        <div className="task-actions">
          <Button onClick={onRecoverStale} variant="secondary">恢复卡住 turn</Button>
          <Button onClick={() => onCleanup("CLOSED")} variant="secondary">清理 CLOSED</Button>
          <Button onClick={() => onCleanup("ERROR")} variant="secondary">清理 ERROR</Button>
        </div>
      </details>
    </div>
  );
}
