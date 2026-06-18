import { useCallback, useEffect, useState } from "react";

import type { ToastState } from "../components/layout/Toast";

export function useToast(timeoutMs = 3200) {
  const [toast, setToast] = useState<ToastState>(null);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), timeoutMs);
    return () => window.clearTimeout(timer);
  }, [timeoutMs, toast]);

  const showToast = useCallback(
    (message: string, type: NonNullable<ToastState>["type"] = "info") => {
      setToast({ message, type });
    },
    []
  );

  return { toast, showToast, clearToast: () => setToast(null) };
}
