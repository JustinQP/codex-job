import { apiRequest } from "./client";
import type { Project } from "./types";

export function listProjects() {
  return apiRequest<Project[]>("/projects");
}

export type ProjectUpdatePayload = Partial<{
  name: string;
  enabled: boolean;
  test_command: string | null;
  smoke_check_command: string | null;
  default_branch: string | null;
  require_clean_worktree: boolean | null;
  default_model: string | null;
  default_reasoning_effort: string | null;
  default_sandbox: string | null;
  workspace_id: number | null;
}>;

export function updateProject(projectId: number, payload: ProjectUpdatePayload) {
  return apiRequest<Project>(`/projects/${projectId}`, {
    method: "PATCH",
    json: payload
  });
}
