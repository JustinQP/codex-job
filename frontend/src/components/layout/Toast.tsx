export type ToastState = {
  message: string;
  type?: "info" | "success" | "error" | "warning";
} | null;

type ToastProps = {
  toast: ToastState;
};

export function Toast({ toast }: ToastProps) {
  if (!toast) return null;
  return (
    <div className={`toast ${toast.type || "info"}`} role="status">
      {toast.message}
    </div>
  );
}
