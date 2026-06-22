export const API_TOKEN_KEY = "apiToken";

export const UI_STATE_KEYS = {
  activeTab: "mobile.activeTab",
  taskStatusFilter: "mobile.taskStatusFilter",
  appThreadStatusFilter: "mobile.appThreadStatusFilter",
  appIncludeArchived: "mobile.appIncludeArchived",
  currentProjectId: "mobile.currentProjectId",
  selectedAppThreadId: "mobile.selectedAppThreadId",
  appSendMode: "mobile.appSendMode"
} as const;

export function readStorage(key: string, fallback = ""): string {
  try {
    return window.localStorage.getItem(key) ?? fallback;
  } catch {
    return fallback;
  }
}

export function writeStorage(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // localStorage can be unavailable in privacy modes.
  }
}

export function removeStorage(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    // localStorage can be unavailable in privacy modes.
  }
}
