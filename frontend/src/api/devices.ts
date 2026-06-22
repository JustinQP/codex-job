import { apiRequest } from "./client";
import type { Device } from "./types";

export function listDevices() {
  return apiRequest<Device[]>("/devices");
}

export function getDevice(deviceId: string) {
  return apiRequest<Device>(`/devices/${encodeURIComponent(deviceId)}`);
}
