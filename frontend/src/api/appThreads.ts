import { apiHeaders, apiRequest } from "./client";
import type {
  AppThread,
  AppThreadCleanup,
  AppThreadEvents,
  AppThreadFinal,
  AppTurn,
  TurnEventList,
  AppTurnStreamEvent,
  AppTurnRecovery,
  BridgeHealth
} from "./types";

export type ListAppThreadsOptions = {
  limit?: number;
  projectId?: number | null;
  status?: string;
  includeArchived?: boolean;
};

export function getBridgeHealth() {
  return apiRequest<BridgeHealth>("/app-server-bridge/health");
}

export function listAppThreads(options: ListAppThreadsOptions = {}) {
  const params = new URLSearchParams({ limit: String(options.limit ?? 20) });
  if (options.projectId) params.set("project_id", String(options.projectId));
  if (options.status) params.set("status", options.status);
  if (options.includeArchived) params.set("include_archived", "true");
  return apiRequest<AppThread[]>(`/app-threads?${params.toString()}`);
}

export function createAppThread(projectId: number, title?: string) {
  return apiRequest<AppThread>("/app-threads", {
    method: "POST",
    json: { project_id: projectId, title: title || undefined }
  });
}

export function getAppThread(threadId: number) {
  return apiRequest<AppThread>(`/app-threads/${threadId}`);
}

export function updateAppThreadTitle(threadId: number, title: string) {
  return apiRequest<AppThread>(`/app-threads/${threadId}`, {
    method: "PATCH",
    json: { title }
  });
}

export function closeAppThread(threadId: number) {
  return apiRequest<AppThread>(`/app-threads/${threadId}`, { method: "DELETE" });
}

export function reopenAppThread(threadId: number) {
  return apiRequest<AppThread>(`/app-threads/${threadId}/reopen`, { method: "POST" });
}

export function listAppTurns(threadId: number) {
  return apiRequest<AppTurn[]>(`/app-threads/${threadId}/turns`);
}

export function sendAppTurn(threadId: number, message: string) {
  return apiRequest<AppTurn>(`/app-threads/${threadId}/turns`, {
    method: "POST",
    json: { message }
  });
}

export function sendAsyncAppTurn(threadId: number, message: string) {
  return apiRequest<AppTurn>(`/app-threads/${threadId}/turns/async`, {
    method: "POST",
    json: { message }
  });
}

export function getAppTurn(turnId: number) {
  return apiRequest<AppTurn>(`/app-turns/${turnId}`);
}

export function listAppTurnEvents(turnId: number, since = 0, limit = 100) {
  const params = new URLSearchParams({
    since: String(since),
    limit: String(limit)
  });
  return apiRequest<TurnEventList>(`/app-turns/${turnId}/events?${params.toString()}`);
}

export async function streamAppTurn(
  turnId: number,
  onEvent: (event: AppTurnStreamEvent) => void,
  signal?: AbortSignal
) {
  const response = await fetch(`/app-turns/${turnId}/stream`, {
    headers: apiHeaders(false),
    signal
  });
  if (!response.ok) {
    throw new Error(await response.text() || response.statusText);
  }
  if (!response.body) {
    throw new Error("stream response has no body");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";
    for (const chunk of chunks) {
      const event = parseSseEvent(chunk);
      if (event) onEvent(event);
    }
  }
  buffer += decoder.decode();
  const event = parseSseEvent(buffer);
  if (event) onEvent(event);
}

export function cancelAppTurn(turnId: number) {
  return apiRequest<AppTurn>(`/app-turns/${turnId}/cancel`, { method: "POST" });
}

export function getAppThreadFinal(threadId: number) {
  return apiRequest<AppThreadFinal>(`/app-threads/${threadId}/final`);
}

export function getAppThreadEvents(threadId: number) {
  return apiRequest<AppThreadEvents>(`/app-threads/${threadId}/events`);
}

export function recoverStaleAppTurns() {
  return apiRequest<AppTurnRecovery>("/app-turns/recover-stale", { method: "POST" });
}

export function cleanupAppThreads(status: string, limit = 50) {
  return apiRequest<AppThreadCleanup>("/app-threads/cleanup", {
    method: "POST",
    json: { status, limit }
  });
}

function parseSseEvent(chunk: string): AppTurnStreamEvent | null {
  const dataLines = chunk
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart());
  if (!dataLines.length) return null;
  return JSON.parse(dataLines.join("\n")) as AppTurnStreamEvent;
}
