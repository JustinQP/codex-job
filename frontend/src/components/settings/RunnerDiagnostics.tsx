import type { Runner } from "../../api/types";
import { formatRelativeTime } from "../../utils/date";
import { statusTone } from "../../utils/text";
import { Badge } from "../common/Badge";

type RunnerDiagnosticsProps = {
  runners: Runner[];
};

export function RunnerDiagnostics({ runners }: RunnerDiagnosticsProps) {
  if (!runners.length) {
    return <div className="empty-state"><strong>没有在线 Runner</strong></div>;
  }
  return (
    <div className="stack">
      {runners.map((runner) => (
        <div className="list-card" key={runner.runner_id}>
          <div className="row">
            <strong>{runner.runner_id}</strong>
            <Badge tone={statusTone(runner.status)}>{runner.status}</Badge>
          </div>
          <span className="muted">
            {runner.hostname} · pid={runner.pid} · heartbeat {formatRelativeTime(runner.last_heartbeat_at)}
          </span>
        </div>
      ))}
    </div>
  );
}
