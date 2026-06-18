import { apiRequest } from "./client";
import type { Runner } from "./types";

export function listRunners() {
  return apiRequest<Runner[]>("/runners");
}
