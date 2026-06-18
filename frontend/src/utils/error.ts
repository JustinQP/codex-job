import { ApiError } from "../api/client";

export function errorText(error: unknown): string {
  if (error instanceof ApiError) return `HTTP ${error.status}: ${error.message}`;
  if (error instanceof Error) return error.message;
  return String(error || "Unknown error");
}

export function isRunningStatus(status?: string | null): boolean {
  return ["PENDING", "RUNNING"].includes(String(status || "").toUpperCase());
}
