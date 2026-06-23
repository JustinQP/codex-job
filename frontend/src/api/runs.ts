import { apiRequest } from "./client";
import type { Run, RunTemplate, RunType } from "./types";

export type RunCreatePayload = {
  project_id: number;
  prompt: string;
  run_type?: RunType;
  timeout_seconds?: number;
  workspace_id: number;
  device_id?: string | null;
  model?: string | null;
  reasoning_effort?: string | null;
  sandbox?: string | null;
};

export type ListRunsOptions = {
  limit?: number;
  projectId?: number | null;
  workspaceId?: number | null;
};

export function listRuns(options: ListRunsOptions = {}) {
  const params = new URLSearchParams({ limit: String(options.limit ?? 20) });
  if (options.projectId) params.set("project_id", String(options.projectId));
  if (options.workspaceId) params.set("workspace_id", String(options.workspaceId));
  return apiRequest<Run[]>(`/runs?${params.toString()}`);
}

export function getRun(runId: number) {
  return apiRequest<Run>(`/runs/${runId}`);
}

export function createRun(payload: RunCreatePayload) {
  return apiRequest<Run>("/runs", { method: "POST", json: payload });
}

export function cancelRun(runId: number) {
  return apiRequest<Run>(`/runs/${runId}/cancel`, { method: "POST" });
}

export function rerunRun(runId: number) {
  return apiRequest<Run>(`/runs/${runId}/rerun`, { method: "POST" });
}

export function listRunTemplates() {
  return apiRequest<RunTemplate[]>("/run-templates");
}
