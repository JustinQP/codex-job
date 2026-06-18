import { useCallback, useEffect, useMemo, useState } from "react";

import {
  cancelAppTurn,
  cleanupAppThreads,
  closeAppThread,
  createAppThread,
  getAppThreadEvents,
  getAppThreadFinal,
  getAppTurn,
  listAppThreads,
  listAppTurns,
  recoverStaleAppTurns,
  reopenAppThread,
  sendAppTurn,
  sendAsyncAppTurn
} from "../../api/appThreads";
import { listProjects } from "../../api/projects";
import type { AppThread, AppTurn, Project } from "../../api/types";
import { useLocalStorage } from "../../hooks/useLocalStorage";
import { usePolling } from "../../hooks/usePolling";
import { UI_STATE_KEYS } from "../../state/storage";
import { errorText, isRunningStatus } from "../../utils/error";
import { Sheet } from "../layout/Sheet";
import type { PageProps } from "../types";
import { Composer } from "./Composer";
import { MessageList } from "./MessageList";
import { SessionHeader } from "./SessionHeader";
import { SessionMoreSheet } from "./SessionMoreSheet";
import { ThreadSwitcherSheet } from "./ThreadSwitcherSheet";

export function SessionPage({ showToast }: PageProps) {
  const [threads, setThreads] = useState<AppThread[]>([]);
  const [turns, setTurns] = useState<AppTurn[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedThreadIdText, setSelectedThreadIdText] = useLocalStorage(
    UI_STATE_KEYS.selectedAppThreadId,
    ""
  );
  const [sendMode, setSendMode] = useLocalStorage(UI_STATE_KEYS.appSendMode, "async");
  const [message, setMessage] = useState("");
  const [waitingText, setWaitingText] = useState("");
  const [error, setError] = useState("");
  const [sheet, setSheet] = useState<"switch" | "more" | "final" | "events" | null>(null);
  const [sheetContent, setSheetContent] = useState("");
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());

  const selectedThreadId = selectedThreadIdText ? Number(selectedThreadIdText) : null;
  const selectedThread = useMemo(
    () => threads.find((thread) => thread.id === selectedThreadId) || null,
    [selectedThreadId, threads]
  );
  const runningTurn = turns.find((turn) => isRunningStatus(turn.status)) || null;

  const loadThreads = useCallback(async () => {
    const [threadData, projectData] = await Promise.all([
      listAppThreads({ limit: 20 }),
      listProjects()
    ]);
    setThreads(threadData);
    setProjects(projectData);
  }, []);

  const loadTurns = useCallback(async () => {
    if (!selectedThreadId) {
      setTurns([]);
      return;
    }
    setTurns(await listAppTurns(selectedThreadId));
  }, [selectedThreadId]);

  const loadAll = useCallback(async () => {
    setError("");
    try {
      await loadThreads();
      await loadTurns();
    } catch (err) {
      setError(errorText(err));
    }
  }, [loadThreads, loadTurns]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  usePolling(async () => {
    if (!runningTurn) return;
    const updated = await getAppTurn(runningTurn.id);
    setTurns((current) => current.map((turn) => (turn.id === updated.id ? updated : turn)));
    if (!isRunningStatus(updated.status)) {
      setWaitingText("");
      await loadAll();
    }
  }, 2500, Boolean(runningTurn));

  async function handleCreateThread(projectId: number, title: string) {
    try {
      const thread = await createAppThread(projectId, title);
      setSelectedThreadIdText(String(thread.id));
      setSheet(null);
      showToast("会话已创建", "success");
      await loadAll();
    } catch (err) {
      showToast(errorText(err), "error");
    }
  }

  function handleSelectThread(thread: AppThread) {
    setSelectedThreadIdText(String(thread.id));
    setSheet(null);
  }

  async function handleSend() {
    if (!selectedThreadId || !message.trim()) return;
    setWaitingText("正在等待 App Server 返回，请不要刷新页面。");
    try {
      const sender = sendMode === "async" ? sendAsyncAppTurn : sendAppTurn;
      const turn = await sender(selectedThreadId, message.trim());
      setMessage("");
      setTurns((current) => [...current, turn]);
      showToast("消息已发送", "success");
      if (!isRunningStatus(turn.status)) setWaitingText("");
      await loadAll();
    } catch (err) {
      setWaitingText("");
      showToast(errorText(err), "error");
    }
  }

  async function handleCancelTurn() {
    if (!runningTurn) {
      showToast("当前没有运行中的 Turn", "warning");
      return;
    }
    if (!window.confirm(`确认取消 App Turn #${runningTurn.id}？`)) return;
    try {
      await cancelAppTurn(runningTurn.id);
      setWaitingText("");
      showToast("已请求取消当前 Turn", "success");
      await loadAll();
    } catch (err) {
      showToast(errorText(err), "error");
    }
  }

  async function handleReopen() {
    if (!selectedThreadId) return;
    try {
      const thread = await reopenAppThread(selectedThreadId);
      setSelectedThreadIdText(String(thread.id));
      showToast("会话已重开", "success");
      await loadAll();
    } catch (err) {
      showToast(errorText(err), "error");
    }
  }

  async function handleCloseThread() {
    if (!selectedThreadId) return;
    if (!window.confirm("确认关闭当前会话？")) return;
    try {
      await closeAppThread(selectedThreadId);
      showToast("会话已关闭", "success");
      await loadAll();
    } catch (err) {
      showToast(errorText(err), "error");
    }
  }

  async function handleFinal() {
    if (!selectedThreadId) return;
    try {
      const final = await getAppThreadFinal(selectedThreadId);
      setSheetContent(final.assistant_final || "暂无 assistant_final");
      setSheet("final");
    } catch (err) {
      showToast(errorText(err), "error");
    }
  }

  async function handleEvents() {
    if (!selectedThreadId) return;
    try {
      const events = await getAppThreadEvents(selectedThreadId);
      setSheetContent(JSON.stringify(events.event_summary || {}, null, 2));
      setSheet("events");
    } catch (err) {
      showToast(errorText(err), "error");
    }
  }

  async function handleRecoverStale() {
    try {
      const result = await recoverStaleAppTurns();
      showToast(`恢复 ${result.recovered_count} 个 turn`, "success");
      await loadAll();
    } catch (err) {
      showToast(errorText(err), "error");
    }
  }

  async function handleCleanup(status: string) {
    if (!window.confirm(`确认将 ${status} AppThread 标记为 archived？`)) return;
    try {
      const result = await cleanupAppThreads(status);
      showToast(`清理 ${result.archived_count} 个会话`, "success");
      await loadAll();
    } catch (err) {
      showToast(errorText(err), "error");
    }
  }

  return (
    <section className="page active" id="tab-app">
      <div className="session-page">
        <SessionHeader
          onMore={() => setSheet("more")}
          onSwitch={() => setSheet("switch")}
          selectedThread={selectedThread}
        />
        {error ? <div className="inline-error">{error}</div> : null}
        <main className="message-list">
          <div className="message-flow">
            <MessageList
              expandedIds={expandedIds}
              onRetry={(turn) => setMessage(turn.user_message)}
              onShowError={(turn) => {
                setSheetContent(turn.error_message || turn.assistant_final || "无错误详情");
                setSheet("events");
              }}
              onToggle={(turnId) => {
                setExpandedIds((current) => {
                  const next = new Set(current);
                  if (next.has(turnId)) next.delete(turnId);
                  else next.add(turnId);
                  return next;
                });
              }}
              turns={turns}
            />
          </div>
        </main>
        <Composer
          disabled={!selectedThread || selectedThread.status === "CLOSED" || Boolean(runningTurn)}
          message={message}
          onMessageChange={setMessage}
          onSend={handleSend}
          onToggleMode={() => setSendMode(sendMode === "async" ? "sync" : "async")}
          sendMode={sendMode}
          waitingText={waitingText || (runningTurn ? "正在等待回复，可以继续编辑，但暂时不能发送" : "")}
        />
      </div>

      {sheet === "switch" ? (
        <Sheet onClose={() => setSheet(null)} title="切换会话">
          <ThreadSwitcherSheet
            onCreate={handleCreateThread}
            onRefresh={() => void loadAll()}
            onSelect={handleSelectThread}
            projects={projects}
            selectedThreadId={selectedThreadId}
            threads={threads}
          />
        </Sheet>
      ) : null}

      {sheet === "more" ? (
        <Sheet onClose={() => setSheet(null)} title="会话更多">
          <SessionMoreSheet
            onCancelTurn={handleCancelTurn}
            onCleanup={handleCleanup}
            onCloseThread={handleCloseThread}
            onEvents={handleEvents}
            onFinal={handleFinal}
            onRecoverStale={handleRecoverStale}
            onRefreshTurns={() => void loadAll()}
            onReopen={handleReopen}
            selectedThread={selectedThread}
          />
        </Sheet>
      ) : null}

      {sheet === "final" || sheet === "events" ? (
        <Sheet onClose={() => setSheet(null)} title={sheet === "final" ? "最终回复" : "事件摘要"}>
          <pre>{sheetContent}</pre>
        </Sheet>
      ) : null}
    </section>
  );
}
