import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  cancelAppTurn,
  cleanupAppThreads,
  closeAppThread,
  createAppThread,
  getAppThread,
  getAppThreadEvents,
  getAppThreadFinal,
  getAppTurn,
  listAppThreads,
  listAppTurns,
  recoverStaleAppTurns,
  reopenAppThread,
  sendAppTurn,
  sendAsyncAppTurn,
  streamAppTurn
} from "../../api/appThreads";
import { listProjects } from "../../api/projects";
import type { AppThread, AppTurn, AppTurnStreamEvent, Project } from "../../api/types";
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
  const [appThreadStatusFilter, setAppThreadStatusFilter] = useLocalStorage(
    UI_STATE_KEYS.appThreadStatusFilter,
    ""
  );
  const [appIncludeArchived, setAppIncludeArchived] = useLocalStorage(
    UI_STATE_KEYS.appIncludeArchived,
    "false"
  );
  const [currentProjectIdText, setCurrentProjectIdText] = useLocalStorage(
    UI_STATE_KEYS.currentProjectId,
    ""
  );
  const [sendMode, setSendMode] = useLocalStorage(UI_STATE_KEYS.appSendMode, "async");
  const [message, setMessage] = useState("");
  const [waitingText, setWaitingText] = useState("");
  const [error, setError] = useState("");
  const [sheet, setSheet] = useState<"switch" | "more" | "final" | "events" | null>(null);
  const [sheetContent, setSheetContent] = useState("");
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const messageListRef = useRef<HTMLElement | null>(null);
  const shouldStickToBottomRef = useRef(true);
  const forceScrollAfterSendRef = useRef(false);
  const streamControllersRef = useRef<Map<number, AbortController>>(new Map());

  const selectedThreadId = selectedThreadIdText ? Number(selectedThreadIdText) : null;
  const currentProjectId = currentProjectIdText ? Number(currentProjectIdText) : null;
  const includeArchived = appIncludeArchived === "true";
  const selectedThread = useMemo(
    () => threads.find((thread) => thread.id === selectedThreadId) || null,
    [selectedThreadId, threads]
  );
  const currentProject = useMemo(
    () => projects.find((project) => project.id === currentProjectId)
      || projects.find((project) => project.enabled)
      || projects[0]
      || null,
    [currentProjectId, projects]
  );
  const runningTurn = turns.find((turn) => isRunningStatus(turn.status)) || null;
  const disabledReason = !selectedThread
    ? "请先新建或选择会话"
    : selectedThread.status === "CLOSED"
      ? "当前会话已关闭，请重开后继续"
      : runningTurn
        ? "正在等待回复，可以继续编辑，但暂时不能发送"
        : "";

  const scrollMessagesToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    const target = messageListRef.current;
    if (!target) return;
    target.scrollTo({ top: target.scrollHeight, behavior });
  }, []);

  const updateStickToBottom = useCallback(() => {
    const target = messageListRef.current;
    if (!target) return;
    const distanceToBottom = target.scrollHeight - target.scrollTop - target.clientHeight;
    shouldStickToBottomRef.current = distanceToBottom < 96;
  }, []);

  const loadThreads = useCallback(async () => {
    const projectData = await listProjects();
    const effectiveProject = currentProjectId
      ? projectData.find((project) => project.id === currentProjectId)
      : null;
    const fallbackProject = projectData.find((project) => project.enabled) || projectData[0] || null;
    const effectiveProjectId = effectiveProject?.id || fallbackProject?.id || null;
    if (!currentProjectIdText && effectiveProjectId) {
      setCurrentProjectIdText(String(effectiveProjectId));
    }

    const threadData = effectiveProjectId
      ? await listAppThreads({
        includeArchived,
        limit: 20,
        projectId: effectiveProjectId,
        status: appThreadStatusFilter || undefined
      })
      : [];
    let nextThreads = threadData;
    if (selectedThreadId && !threadData.some((thread) => thread.id === selectedThreadId)) {
      try {
        const fallbackThread = await getAppThread(selectedThreadId);
        if (fallbackThread.project_id === effectiveProjectId) {
          nextThreads = [fallbackThread, ...threadData];
        } else {
          setSelectedThreadIdText("");
          setTurns([]);
        }
      } catch {
        setSelectedThreadIdText("");
        setTurns([]);
      }
    }
    setThreads(nextThreads);
    setProjects(projectData);
  }, [
    appThreadStatusFilter,
    currentProjectId,
    currentProjectIdText,
    includeArchived,
    selectedThreadId,
    setCurrentProjectIdText,
    setSelectedThreadIdText
  ]);

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

  useEffect(() => {
    return () => {
      streamControllersRef.current.forEach((controller) => controller.abort());
      streamControllersRef.current.clear();
    };
  }, []);

  usePolling(async () => {
    if (!runningTurn) return;
    const updated = await getAppTurn(runningTurn.id);
    setTurns((current) =>
      current.map((turn) =>
        turn.id === updated.id
          ? {
              ...updated,
              assistant_final: isRunningStatus(updated.status)
                ? turn.assistant_final || updated.assistant_final
                : updated.assistant_final
            }
          : turn
      )
    );
    if (!isRunningStatus(updated.status)) {
      setWaitingText("");
      await loadAll();
    }
  }, 2500, Boolean(runningTurn));

  const mergeTurn = useCallback((nextTurn: AppTurn) => {
    setTurns((current) => {
      if (current.some((turn) => turn.id === nextTurn.id)) {
        return current.map((turn) => (turn.id === nextTurn.id ? nextTurn : turn));
      }
      return [...current, nextTurn];
    });
  }, []);

  const handleStreamEvent = useCallback((event: AppTurnStreamEvent) => {
    if (event.kind === "assistant_delta" && event.text) {
      setTurns((current) =>
        current.map((turn) =>
          turn.id === event.turn_id
            ? {
                ...turn,
                assistant_final: `${turn.assistant_final || ""}${event.text}`,
                status: isRunningStatus(turn.status) ? turn.status : "RUNNING"
              }
            : turn
        )
      );
      if (shouldStickToBottomRef.current) {
        window.requestAnimationFrame(() => scrollMessagesToBottom());
      }
      return;
    }
    if (event.kind === "status" && event.status) {
      setTurns((current) =>
        current.map((turn) => (turn.id === event.turn_id ? { ...turn, status: event.status || turn.status } : turn))
      );
      return;
    }
    if (event.kind === "final" && event.turn) {
      mergeTurn(event.turn);
      setWaitingText("");
      streamControllersRef.current.delete(event.turn_id);
      void loadAll();
      return;
    }
    if (event.kind === "error") {
      if (event.turn) {
        mergeTurn(event.turn);
      } else {
        setTurns((current) =>
          current.map((turn) =>
            turn.id === event.turn_id
              ? { ...turn, status: "FAILED", error_message: event.message || turn.error_message }
              : turn
          )
        );
      }
      setWaitingText("");
      streamControllersRef.current.delete(event.turn_id);
    }
  }, [loadAll, mergeTurn, scrollMessagesToBottom]);

  const startTurnStream = useCallback((turnId: number) => {
    streamControllersRef.current.get(turnId)?.abort();
    const controller = new AbortController();
    streamControllersRef.current.set(turnId, controller);
    void streamAppTurn(turnId, handleStreamEvent, controller.signal).catch((err) => {
      if (controller.signal.aborted) return;
      streamControllersRef.current.delete(turnId);
      showToast(errorText(err), "error");
    });
  }, [handleStreamEvent, showToast]);

  async function handleCreateThread(projectId: number, title: string) {
    try {
      const effectiveProjectId = projectId || currentProject?.id;
      if (!effectiveProjectId) {
        showToast("请先选择项目", "warning");
        return;
      }
      setCurrentProjectIdText(String(effectiveProjectId));
      const thread = await createAppThread(effectiveProjectId, title);
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
      forceScrollAfterSendRef.current = true;
      setTurns((current) => [...current, turn]);
      if (sendMode === "async") startTurnStream(turn.id);
      showToast("消息已发送", "success");
      if (!isRunningStatus(turn.status)) setWaitingText("");
      if (sendMode !== "async") await loadAll();
    } catch (err) {
      setWaitingText("");
      showToast(errorText(err), "error");
    }
  }

  useEffect(() => {
    if (forceScrollAfterSendRef.current) {
      forceScrollAfterSendRef.current = false;
      scrollMessagesToBottom();
      return;
    }
    if (shouldStickToBottomRef.current) scrollMessagesToBottom();
  }, [scrollMessagesToBottom, turns.length, turns]);

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
          currentProject={currentProject}
          onMore={() => setSheet("more")}
          onSwitch={() => setSheet("switch")}
          selectedThread={selectedThread}
        />
        {error ? <div className="inline-error">{error}</div> : null}
        <main className="message-list" onScroll={updateStickToBottom} ref={messageListRef}>
          <div className="message-flow">
            <MessageList
              expandedIds={expandedIds}
              onReopenThread={handleReopen}
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
          disabled={Boolean(disabledReason)}
          disabledReason={disabledReason}
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
            onIncludeArchivedChange={(nextIncludeArchived) => {
              setAppIncludeArchived(nextIncludeArchived ? "true" : "false");
            }}
            onSelect={handleSelectThread}
            onStatusFilterChange={setAppThreadStatusFilter}
            includeArchived={includeArchived}
            currentProjectId={currentProject?.id || null}
            projects={projects}
            selectedThreadId={selectedThreadId}
            statusFilter={appThreadStatusFilter}
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
