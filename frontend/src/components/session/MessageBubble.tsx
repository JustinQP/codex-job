import type { AppTurn } from "../../api/types";
import { shortText, statusTone } from "../../utils/text";
import { Badge } from "../common/Badge";
import { Button } from "../common/Button";

type MessageBubbleProps = {
  turn: AppTurn;
  expanded: boolean;
  onToggle: () => void;
  onRetry: () => void;
  onReopenThread: () => void;
  onShowError: () => void;
};

export function MessageBubble({
  turn,
  expanded,
  onReopenThread,
  onRetry,
  onShowError,
  onToggle
}: MessageBubbleProps) {
  const assistantText = turn.assistant_final || turn.error_message || "正在等待 App Server 返回";
  const longText = assistantText.length > 520;
  const failed = ["FAILED", "ERROR", "CANCELLED"].includes(turn.status);
  const canRecoverByReopen = /unknown bridge thread id/i.test(turn.error_message || "");

  return (
    <article className="chat-turn">
      <div className="bubble-row user">
        <div className="bubble user">{turn.user_message}</div>
      </div>
      <div className="bubble-row assistant">
        <div className={`bubble assistant ${statusTone(turn.status)}`} onClick={onToggle}>
          <div className="bubble-meta-row">
            <Badge tone={statusTone(turn.status)}>{turn.status}</Badge>
          </div>
          <div className={longText && !expanded ? "assistant-message collapsed" : "assistant-message"}>
            {expanded || !longText ? assistantText : shortText(assistantText, 520)}
          </div>
          {longText ? (
            <div className="bubble-detail-hint">
              {expanded ? "收起" : "展开全文"}
            </div>
          ) : null}
          {failed ? (
            <div className="task-actions">
              {canRecoverByReopen ? (
                <Button onClick={(event) => { event.stopPropagation(); onReopenThread(); }} variant="primary">
                  重开会话
                </Button>
              ) : (
                <Button onClick={(event) => { event.stopPropagation(); onRetry(); }} variant="secondary">
                  复制重试
                </Button>
              )}
              <Button onClick={(event) => { event.stopPropagation(); onShowError(); }} variant="danger">
                查看错误
              </Button>
            </div>
          ) : null}
        </div>
      </div>
    </article>
  );
}
