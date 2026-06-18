import { Button } from "./Button";

type ErrorSheetProps = {
  error: unknown;
  onClose: () => void;
};

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return String(error || "Unknown error");
}

export function ErrorSheet({ error, onClose }: ErrorSheetProps) {
  return (
    <div className="stack">
      <div className="inline-error">{errorMessage(error)}</div>
      <Button onClick={onClose} variant="secondary">
        Close
      </Button>
    </div>
  );
}
