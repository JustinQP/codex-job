import { API_TOKEN_KEY, readStorage } from "../state/storage";

export type ApiOptions = RequestInit & {
  json?: unknown;
  token?: string;
};

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export function apiHeaders(json = false, token = readStorage(API_TOKEN_KEY)): HeadersInit {
  const headers: Record<string, string> = {};
  if (token) headers["X-API-Token"] = token;
  if (json) headers["Content-Type"] = "application/json";
  return headers;
}

export async function apiRequest<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const hasJson = options.json !== undefined;
  const response = await fetch(path, {
    ...options,
    body: hasJson ? JSON.stringify(options.json) : options.body,
    headers: {
      ...apiHeaders(hasJson, options.token),
      ...(options.headers || {})
    }
  });

  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json")
    ? await response.json().catch(() => null)
    : await response.text();

  if (!response.ok) {
    const message =
      typeof body === "object" && body && "detail" in body
        ? JSON.stringify((body as { detail: unknown }).detail)
        : String(body || response.statusText);
    throw new ApiError(message, response.status, body);
  }

  return body as T;
}

export async function safeApi<T>(path: string, options: ApiOptions = {}) {
  try {
    return { ok: true as const, data: await apiRequest<T>(path, options) };
  } catch (error) {
    return { ok: false as const, error };
  }
}
