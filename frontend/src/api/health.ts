import { apiRequest } from "./client";
import type { Health } from "./types";

export function getHealth() {
  return apiRequest<Health>("/health");
}
