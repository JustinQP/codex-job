export function shortText(value: unknown, maxLength = 180): string {
  const text = String(value || "");
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength)}...`;
}

export function statusTone(status?: string | null): string {
  const normalized = String(status || "").toLowerCase();
  if (["success", "active", "online"].includes(normalized)) return normalized;
  if (["pending", "running"].includes(normalized)) return normalized;
  if (["failed", "error", "offline"].includes(normalized)) return normalized;
  if (["cancelled", "closed"].includes(normalized)) return normalized;
  return "closed";
}
