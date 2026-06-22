import type { Device } from "../api/types";

export function isDeviceRunnable(device: Device | null): boolean {
  return device?.status === "ONLINE";
}

export function deviceDisabledReason(device: Device | null): string {
  if (!device) return "请先在项目页选择设备";
  if (device.status === "ONLINE") return "";
  if (device.status === "OFFLINE") return "当前设备离线，只能查看历史，不能新建执行";
  if (device.status === "DISABLED") return "当前设备已停用，不能新建执行";
  return `当前设备状态为 ${device.status}，不能新建执行`;
}
