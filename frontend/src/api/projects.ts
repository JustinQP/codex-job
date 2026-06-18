import { apiRequest } from "./client";
import type { Project } from "./types";

export function listProjects() {
  return apiRequest<Project[]>("/projects");
}
