import { apiRequest } from "./client";
import type { Workspace } from "./types";

export function listWorkspaces(deviceId?: string) {
  const query = deviceId ? `?device_id=${encodeURIComponent(deviceId)}` : "";
  return apiRequest<Workspace[]>(`/workspaces${query}`);
}

export function getWorkspace(workspaceId: number) {
  return apiRequest<Workspace>(`/workspaces/${workspaceId}`);
}
