import { apiRequest } from "./client";
import type { Device } from "./types";

export function listDevices() {
  return apiRequest<Device[]>("/devices");
}

export function getDevice(deviceId: string) {
  return apiRequest<Device>(`/devices/${encodeURIComponent(deviceId)}`);
}

export function updateDevice(deviceId: string, payload: { display_name?: string }) {
  return apiRequest<Device>(`/devices/${encodeURIComponent(deviceId)}`, {
    method: "PATCH",
    json: payload
  });
}

export function disableDevice(deviceId: string) {
  return apiRequest<Device>(`/devices/${encodeURIComponent(deviceId)}/disable`, { method: "POST" });
}

export function deleteDevice(deviceId: string) {
  return apiRequest<Device>(`/devices/${encodeURIComponent(deviceId)}`, { method: "DELETE" });
}
