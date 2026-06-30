import { apiRequest } from "./client";
import type { Workspace } from "./types";

export function listWorkspaces(deviceId?: string) {
  const query = deviceId ? `?device_id=${encodeURIComponent(deviceId)}` : "";
  return apiRequest<Workspace[]>(`/workspaces${query}`);
}

export function getWorkspace(workspaceId: number) {
  return apiRequest<Workspace>(`/workspaces/${workspaceId}`);
}

export type WorkspaceUpdatePayload = Partial<{
  name: string;
  enabled: boolean;
  default_model: string | null;
  default_reasoning_effort: string | null;
  default_sandbox: string | null;
  default_approval_policy: string | null;
  require_clean_worktree: boolean | null;
}>;

export function updateWorkspace(workspaceId: number, payload: WorkspaceUpdatePayload) {
  return apiRequest<Workspace>(`/workspaces/${workspaceId}`, {
    method: "PATCH",
    json: payload
  });
}
