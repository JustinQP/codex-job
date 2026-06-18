export type ShowToast = (message: string, type?: "info" | "success" | "error" | "warning") => void;

export type PageProps = {
  showToast: ShowToast;
};
