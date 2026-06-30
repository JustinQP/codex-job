import { useEffect, useRef } from "react";

import { Button } from "../common/Button";

type ComposerProps = {
  message: string;
  sendMode: string;
  disabled: boolean;
  disabledReason: string;
  waitingText: string;
  maxMessageLength: number;
  timeoutSeconds: number;
  onMessageChange: (message: string) => void;
  onSend: () => void;
  onTimeoutSecondsChange: (timeoutSeconds: number) => void;
  onToggleMode: () => void;
};

export function Composer({
  disabled,
  disabledReason,
  maxMessageLength,
  message,
  onMessageChange,
  onSend,
  onTimeoutSecondsChange,
  onToggleMode,
  sendMode,
  timeoutSeconds,
  waitingText
}: ComposerProps) {
  const textAreaRef = useRef<HTMLTextAreaElement | null>(null);
  const trimmed = message.trim();
  const overLimit = message.length > maxMessageLength;

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
          {sendMode === "async" ? "快速发送" : "等待回复"}
        </Button>
      </div>
      <div className="composer-input-row">
        <textarea
          maxLength={maxMessageLength + 1}
          onChange={(event) => onMessageChange(event.target.value)}
          placeholder="输入消息"
          ref={textAreaRef}
          value={message}
        />
        <Button
          className="send-button"
          disabled={disabled || !trimmed || overLimit}
          onClick={onSend}
          variant="primary"
        >
          发送
        </Button>
      </div>
      <div className="composer-meta">
        <span>{sendMode === "async" ? "后台等待回复" : "等待完成后返回"}</span>
        <label className="inline">
          timeout
          <input
            max={21600}
            min={30}
            onChange={(event) => onTimeoutSecondsChange(Number(event.target.value) || 180)}
            step={30}
            type="number"
            value={timeoutSeconds}
          />
        </label>
        <span className={`message-count ${message.length ? "" : "empty"} ${overLimit ? "danger" : ""}`}>
          {message.length ? `${message.length}/${maxMessageLength} 字` : ""}
        </span>
      </div>
    </footer>
  );
}
