import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  APP_THREAD_TITLE_MAX_LENGTH,
  APP_TURN_MESSAGE_MAX_LENGTH,
  APP_TURN_TIMEOUT_DEFAULT_SECONDS,
  APP_TURN_TIMEOUT_MAX_SECONDS,
  APP_TURN_TIMEOUT_MIN_SECONDS,
  cancelAppTurn,
  cleanupAppThreads,
  closeAppThread,
  createAppThread,
  getAppThread,
  getAppThreadEvents,
  getAppThreadFinal,
  listAppTurnEvents,
  getAppTurn,
  listAppThreads,
  listAppTurns,
  recoverStaleAppTurns,
  reopenAppThread,
  sendAppTurn,
  sendAsyncAppTurn,
  streamAppTurn
} from "../../api/appThreads";
import { listDevices } from "../../api/devices";
import { listProjects } from "../../api/projects";
import type { AppThread, AppTurn, AppTurnStreamEvent, Device, Project, TurnEvent, Workspace } from "../../api/types";
import { listWorkspaces } from "../../api/workspaces";
import { useLocalStorage } from "../../hooks/useLocalStorage";
import { usePolling } from "../../hooks/usePolling";
import { UI_STATE_KEYS } from "../../state/storage";
import { deviceDisabledReason } from "../../utils/device";
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
  const [devices, setDevices] = useState<Device[]>([]);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
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
  const [currentDeviceIdText] = useLocalStorage(UI_STATE_KEYS.currentDeviceId, "");
  const [currentWorkspaceIdText, setCurrentWorkspaceIdText] = useLocalStorage(UI_STATE_KEYS.currentWorkspaceId, "");
  const [sendMode, setSendMode] = useLocalStorage(UI_STATE_KEYS.appSendMode, "async");
  const [message, setMessage] = useState("");
  const [turnTimeoutSeconds, setTurnTimeoutSeconds] = useState(APP_TURN_TIMEOUT_DEFAULT_SECONDS);
  const [waitingText, setWaitingText] = useState("");
  const [error, setError] = useState("");
  const [sheet, setSheet] = useState<"switch" | "more" | "final" | "events" | null>(null);
  const [sheetContent, setSheetContent] = useState("");
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const messageListRef = useRef<HTMLElement | null>(null);
  const shouldStickToBottomRef = useRef(true);
  const forceScrollAfterSendRef = useRef(false);
  const streamControllersRef = useRef<Map<number, AbortController>>(new Map());
  const streamSequencesRef = useRef<Map<number, number>>(new Map());
  const streamRetryCountsRef = useRef<Map<number, number>>(new Map());
  const streamRetryTimersRef = useRef<Map<number, number>>(new Map());

  const selectedThreadId = selectedThreadIdText ? Number(selectedThreadIdText) : null;
  const currentProjectId = currentProjectIdText ? Number(currentProjectIdText) : null;
  const currentDevice = useMemo(() => {
    return devices.find((device) => device.device_id === currentDeviceIdText)
      || devices.find((device) => device.status === "ONLINE")
      || devices[0]
      || null;
  }, [currentDeviceIdText, devices]);
  const executionDisabledReason = devices.length ? deviceDisabledReason(currentDevice) : "";
  const includeArchived = appIncludeArchived === "true";
  const selectedThread = useMemo(
    () => threads.find((thread) => thread.id === selectedThreadId) || null,
    [selectedThreadId, threads]
  );
  const currentWorkspace = useMemo(() => {
    const storedWorkspaceId = currentWorkspaceIdText ? Number(currentWorkspaceIdText) : null;
    return workspaces.find((workspace) => workspace.id === storedWorkspaceId)
      || workspaces.find((workspace) => workspace.device_id === currentDevice?.device_id && workspace.enabled)
      || workspaces.find((workspace) => workspace.enabled)
      || workspaces[0]
      || null;
  }, [currentDevice, currentWorkspaceIdText, workspaces]);
  const threadDevice = useMemo(
    () => devices.find((device) => device.device_id === selectedThread?.device_id) || null,
    [devices, selectedThread]
  );
  const threadWorkspace = useMemo(
    () => workspaces.find((workspace) => workspace.id === selectedThread?.workspace_id) || null,
    [selectedThread, workspaces]
  );
  const currentProject = useMemo(
    () => projects.find((project) => project.id === currentProjectId)
      || projects.find((project) => project.enabled)
      || projects[0]
      || null,
    [currentProjectId, projects]
  );
  const runningTurn = turns.find((turn) => isRunningStatus(turn.status)) || null;
  const selectedThreadDeviceDisabledReason = selectedThread?.device_id
    ? deviceDisabledReason(threadDevice)
    : "";
  const disabledReason = !selectedThread
    ? "请先新建或选择会话"
    : selectedThreadDeviceDisabledReason
      ? selectedThreadDeviceDisabledReason
    : selectedThread.status === "CLOSED"
      ? "当前会话已关闭，请重开后继续"
      : selectedThread.status === "RECOVER_REQUIRED"
        ? "当前会话需要重开后继续"
        : selectedThread.status !== "ACTIVE"
          ? "当前会话未就绪，暂时不能发送"
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
    const [deviceData, projectData, workspaceData] = await Promise.all([
      listDevices().catch(() => [] as Device[]),
      listProjects(),
      listWorkspaces().catch(() => [] as Workspace[])
    ]);
    const effectiveProject = currentProjectId
      ? projectData.find((project) => project.id === currentProjectId)
      : null;
    const fallbackProject = projectData.find((project) => project.enabled) || projectData[0] || null;
    const effectiveProjectId = effectiveProject?.id || fallbackProject?.id || null;
    if (!currentProjectIdText && effectiveProjectId) {
      setCurrentProjectIdText(String(effectiveProjectId));
    }
    if (!currentWorkspaceIdText) {
      const preferredWorkspace = workspaceData.find((workspace) => workspace.device_id === currentDeviceIdText && workspace.enabled)
        || workspaceData.find((workspace) => workspace.enabled)
        || workspaceData[0]
        || null;
      if (preferredWorkspace) setCurrentWorkspaceIdText(String(preferredWorkspace.id));
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
    setDevices(deviceData);
    setProjects(projectData);
    setWorkspaces(workspaceData);
  }, [
    appThreadStatusFilter,
    currentProjectId,
    currentProjectIdText,
    currentDeviceIdText,
    currentWorkspaceIdText,
    includeArchived,
    selectedThreadId,
    setCurrentProjectIdText,
    setCurrentWorkspaceIdText,
    setSelectedThreadIdText
  ]);

  const restoreTurnFromPersistedEvents = useCallback(async (turn: AppTurn) => {
    if (!isRunningStatus(turn.status)) return turn;
    try {
      let assistantFinal = turn.assistant_final || "";
      let lastSequence = streamSequencesRef.current.get(turn.id) || 0;
      let cursor = 0;
      while (true) {
        const eventList = await listAppTurnEvents(turn.id, cursor, 500);
        for (const event of eventList.events) {
          if (event.sequence <= lastSequence) continue;
          const streamEvent = streamEventFromTurnEvent(turn.id, event);
          lastSequence = Math.max(lastSequence, event.sequence);
          if (streamEvent.kind === "assistant_delta" && streamEvent.text) {
            assistantFinal += streamEvent.text;
          } else if (streamEvent.kind === "final" && streamEvent.assistant_final) {
            assistantFinal = streamEvent.assistant_final;
          }
        }
        if (!eventList.next_sequence) break;
        cursor = eventList.next_sequence;
      }
      streamSequencesRef.current.set(turn.id, lastSequence);
      return assistantFinal ? { ...turn, assistant_final: assistantFinal } : turn;
    } catch {
      return turn;
    }
  }, []);

  const loadTurns = useCallback(async () => {
    if (!selectedThreadId) {
      setTurns([]);
      return;
    }
    const loadedTurns = await listAppTurns(selectedThreadId);
    const restoredTurns = await Promise.all(loadedTurns.map((turn) => restoreTurnFromPersistedEvents(turn)));
    setTurns((current) =>
      restoredTurns.map((turn) => {
        const currentTurn = current.find((item) => item.id === turn.id);
        if (!currentTurn?.assistant_final) return turn;
        const currentText = currentTurn.assistant_final;
        const restoredText = turn.assistant_final || "";
        if (isRunningStatus(turn.status) && currentText.length > restoredText.length) {
          return { ...turn, assistant_final: currentText };
        }
        return turn;
      })
    );
  }, [restoreTurnFromPersistedEvents, selectedThreadId]);

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
      streamSequencesRef.current.clear();
      streamRetryTimersRef.current.forEach((timerId) => window.clearTimeout(timerId));
      streamRetryTimersRef.current.clear();
      streamRetryCountsRef.current.clear();
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
    streamRetryCountsRef.current.set(event.turn_id, 0);
    const sequence = typeof event.sequence === "number" ? event.sequence : null;
    if (sequence !== null) {
      const previous = streamSequencesRef.current.get(event.turn_id) || 0;
      if (sequence <= previous) return;
      streamSequencesRef.current.set(event.turn_id, sequence);
    }
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
      streamRetryCountsRef.current.delete(event.turn_id);
      const retryTimer = streamRetryTimersRef.current.get(event.turn_id);
      if (retryTimer) window.clearTimeout(retryTimer);
      streamRetryTimersRef.current.delete(event.turn_id);
      if (sequence !== null) streamSequencesRef.current.set(event.turn_id, sequence);
      void loadAll();
      return;
    }
    if (event.kind === "final" && event.assistant_final) {
      setTurns((current) =>
        current.map((turn) =>
          turn.id === event.turn_id
            ? { ...turn, assistant_final: event.assistant_final || turn.assistant_final }
            : turn
        )
      );
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
      streamRetryCountsRef.current.delete(event.turn_id);
      const retryTimer = streamRetryTimersRef.current.get(event.turn_id);
      if (retryTimer) window.clearTimeout(retryTimer);
      streamRetryTimersRef.current.delete(event.turn_id);
      if (sequence !== null) streamSequencesRef.current.set(event.turn_id, sequence);
    }
  }, [loadAll, mergeTurn, scrollMessagesToBottom]);

  function startTurnStream(turnId: number) {
    streamControllersRef.current.get(turnId)?.abort();
    const controller = new AbortController();
    streamControllersRef.current.set(turnId, controller);
    const since = streamSequencesRef.current.get(turnId) || 0;
    void streamAppTurn(turnId, handleStreamEvent, controller.signal, since).catch((err) => {
      if (controller.signal.aborted) return;
      streamControllersRef.current.delete(turnId);
      const retryCount = streamRetryCountsRef.current.get(turnId) || 0;
      if (retryCount < 3) {
        streamRetryCountsRef.current.set(turnId, retryCount + 1);
        setWaitingText("连接中断，正在尝试恢复输出。");
        const timerId = window.setTimeout(() => {
          streamRetryTimersRef.current.delete(turnId);
          if (!streamControllersRef.current.has(turnId)) startTurnStream(turnId);
        }, Math.min(8000, 1200 * 2 ** retryCount));
        streamRetryTimersRef.current.set(turnId, timerId);
        return;
      }
      showToast(`输出流连接失败：${errorText(err)}`, "error");
    });
  }

  useEffect(() => {
    if (!runningTurn) return;
    if (streamControllersRef.current.has(runningTurn.id)) return;
    startTurnStream(runningTurn.id);
  }, [runningTurn?.id]);

  async function handleCreateThread(
    projectId: number,
    title: string,
    options: { sandbox?: string; approvalPolicy?: string; networkAccess?: boolean } = {}
  ) {
    if (executionDisabledReason) {
      showToast(executionDisabledReason, "warning");
      return;
    }
    try {
      const effectiveProjectId = projectId || currentProject?.id;
      if (!effectiveProjectId) {
        showToast("请先选择项目", "warning");
        return;
      }
      const effectiveWorkspaceId = currentWorkspace?.id || null;
      setCurrentProjectIdText(String(effectiveProjectId));
      if (effectiveWorkspaceId) setCurrentWorkspaceIdText(String(effectiveWorkspaceId));
      const thread = await createAppThread(effectiveProjectId, title, {
        workspaceId: effectiveWorkspaceId,
        sandbox: options.sandbox,
        approvalPolicy: options.approvalPolicy,
        networkAccess: options.networkAccess
      });
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
    if (!selectedThreadId || !message.trim() || message.length > APP_TURN_MESSAGE_MAX_LENGTH) return;
    setWaitingText("正在等待 App Server 返回，请不要刷新页面。");
    try {
      const sender = sendMode === "async" ? sendAsyncAppTurn : sendAppTurn;
      const turn = await sender(selectedThreadId, message.trim(), clampTurnTimeout(turnTimeoutSeconds));
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
      showToast(`会话已重开，当前 G${thread.generation}`, "success");
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
          threadDevice={threadDevice}
          threadWorkspace={threadWorkspace}
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
          maxMessageLength={APP_TURN_MESSAGE_MAX_LENGTH}
          message={message}
          onMessageChange={setMessage}
          onSend={handleSend}
          onTimeoutSecondsChange={(value) => setTurnTimeoutSeconds(clampTurnTimeout(value))}
          onToggleMode={() => setSendMode(sendMode === "async" ? "sync" : "async")}
          sendMode={sendMode}
          timeoutSeconds={turnTimeoutSeconds}
          waitingText={waitingText || (runningTurn ? "正在等待回复，可以继续编辑，但暂时不能发送" : "")}
        />
      </div>

      {sheet === "switch" ? (
        <Sheet onClose={() => setSheet(null)} title="切换会话">
          <ThreadSwitcherSheet
            createDisabledReason={executionDisabledReason}
            maxTitleLength={APP_THREAD_TITLE_MAX_LENGTH}
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

function streamEventFromTurnEvent(turnId: number, event: TurnEvent): AppTurnStreamEvent {
  if (event.kind === "final") {
    return {
      kind: "final",
      turn_id: turnId,
      sequence: event.sequence,
      assistant_final: stringFromPayload(event.payload, "assistant_final")
        || stringFromPayload(event.payload, "assistant_final_preview")
    };
  }
  const delta = extractDelta(event.payload);
  if (delta) {
    return {
      kind: "assistant_delta",
      turn_id: turnId,
      sequence: event.sequence,
      text: delta
    };
  }
  if (event.kind === "status") {
    return {
      kind: "status",
      turn_id: turnId,
      sequence: event.sequence,
      status: stringFromPayload(event.payload, "status") || "RUNNING"
    };
  }
  if (event.kind.toLowerCase().includes("error") || event.payload.error) {
    return {
      kind: "error",
      turn_id: turnId,
      sequence: event.sequence,
      message: stringFromPayload(event.payload, "message") || stringFromPayload(event.payload, "error") || event.kind
    };
  }
  return {
    kind: "event",
    turn_id: turnId,
    sequence: event.sequence,
    event_kind: event.kind,
    event: event.payload
  };
}

function extractDelta(payload: Record<string, unknown>): string | null {
  const containers = payloadContainers(payload);
  for (const container of containers) {
    const delta = container.delta;
    if (typeof delta === "string" && delta) return delta;
  }
  return null;
}

function payloadContainers(payload: Record<string, unknown>): Record<string, unknown>[] {
  const containers = [payload];
  const event = payload.event;
  if (isRecord(event)) {
    containers.push(event);
    for (const key of ["params", "result", "item", "message", "delta", "content", "output"]) {
      const nested = event[key];
      if (isRecord(nested)) containers.push(nested);
    }
  }
  return containers;
}

function stringFromPayload(payload: Record<string, unknown>, key: string): string | null {
  const value = payload[key];
  return typeof value === "string" && value ? value : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function clampTurnTimeout(value: number): number {
  if (!Number.isFinite(value)) return APP_TURN_TIMEOUT_DEFAULT_SECONDS;
  return Math.min(
    APP_TURN_TIMEOUT_MAX_SECONDS,
    Math.max(APP_TURN_TIMEOUT_MIN_SECONDS, Math.round(value))
  );
}
