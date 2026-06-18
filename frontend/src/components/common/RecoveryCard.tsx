import { Button } from "./Button";

type RecoveryCardProps = {
  title: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
};

export function RecoveryCard({
  title,
  message,
  actionLabel,
  onAction
}: RecoveryCardProps) {
  return (
    <div className="detail-card recovery-card">
      <strong>{title}</strong>
      <p className="muted">{message}</p>
      {actionLabel && onAction ? (
        <Button onClick={onAction} variant="secondary">
          {actionLabel}
        </Button>
      ) : null}
    </div>
  );
}
