import { useEffect, useRef } from "react";

import { Button } from "../common/Button";

type ComposerProps = {
  message: string;
  sendMode: string;
  disabled: boolean;
  disabledReason: string;
  waitingText: string;
  onMessageChange: (message: string) => void;
  onSend: () => void;
  onToggleMode: () => void;
};

export function Composer({
  disabled,
  disabledReason,
  message,
  onMessageChange,
  onSend,
  onToggleMode,
  sendMode,
  waitingText
}: ComposerProps) {
  const textAreaRef = useRef<HTMLTextAreaElement | null>(null);
  const trimmed = message.trim();

  useEffect(() => {
    const target = textAreaRef.current;
    if (!target) return;
    target.style.height = "auto";
    target.style.height = `${Math.min(target.scrollHeight, 120)}px`;
  }, [message]);

  return (
    <footer className="session-composer">
      <div className="composer-status-row">
        <span>{disabledReason || waitingText || "输入消息"}</span>
        <Button onClick={onToggleMode} variant="text">
          {sendMode === "async" ? "后台" : "同步"}
        </Button>
      </div>
      <div className="composer-input-row">
        <textarea
          onChange={(event) => onMessageChange(event.target.value)}
          placeholder="输入消息"
          ref={textAreaRef}
          value={message}
        />
        <Button
          className="send-button"
          disabled={disabled || !trimmed}
          onClick={onSend}
          variant="primary"
        >
          发
        </Button>
      </div>
      <div className="composer-meta">
        <span>{sendMode === "async" ? "后台等待回复" : "等待完成后返回"}</span>
        <span className={`message-count ${message.length ? "" : "empty"}`}>
          {message.length ? `${message.length} 字` : ""}
        </span>
      </div>
    </footer>
  );
}
