import { apiRequest } from "./client";
import type { Task, TaskTemplate, TaskType } from "./types";

export type CreateTaskPayload = {
  project_id: number;
  prompt: string;
  timeout_seconds?: number;
  task_type?: TaskType;
  assigned_runner_id?: string | null;
  model?: string | null;
  reasoning_effort?: string | null;
  sandbox?: string | null;
};

export type ListTasksOptions = {
  limit?: number;
  projectId?: number | null;
};

export function listTasks(options: number | ListTasksOptions = 20) {
  const normalized = typeof options === "number" ? { limit: options } : options;
  const params = new URLSearchParams({ limit: String(normalized.limit ?? 20) });
  if (normalized.projectId) params.set("project_id", String(normalized.projectId));
  return apiRequest<Task[]>(`/tasks?${params.toString()}`);
}

export function getTask(taskId: number) {
  return apiRequest<Task>(`/tasks/${taskId}`);
}

export function createTask(payload: CreateTaskPayload) {
  return apiRequest<Task>("/tasks", { method: "POST", json: payload });
}

export function cancelTask(taskId: number) {
  return apiRequest<Task>(`/tasks/${taskId}/cancel`, { method: "POST" });
}

export function rerunTask(taskId: number) {
  return apiRequest<Task>(`/tasks/${taskId}/rerun`, { method: "POST" });
}

export function listTaskTemplates() {
  return apiRequest<TaskTemplate[]>("/task-templates");
}
