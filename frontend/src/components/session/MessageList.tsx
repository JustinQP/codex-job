import type { AppTurn } from "../../api/types";
import { EmptyState } from "../common/EmptyState";
import { MessageBubble } from "./MessageBubble";

type MessageListProps = {
  turns: AppTurn[];
  expandedIds: Set<number>;
  onToggle: (turnId: number) => void;
  onRetry: (turn: AppTurn) => void;
  onReopenThread: () => void;
  onShowError: (turn: AppTurn) => void;
};

export function MessageList({
  expandedIds,
  onReopenThread,
  onRetry,
  onShowError,
  onToggle,
  turns
}: MessageListProps) {
  if (!turns.length) {
    return <EmptyState title="还没有消息" description="选择或新建会话后即可发送消息。" />;
  }

  return (
    <>
      {turns.map((turn) => (
        <MessageBubble
          expanded={expandedIds.has(turn.id)}
          key={turn.id}
          onReopenThread={onReopenThread}
          onRetry={() => onRetry(turn)}
          onShowError={() => onShowError(turn)}
          onToggle={() => onToggle(turn.id)}
          turn={turn}
        />
      ))}
    </>
  );
}
