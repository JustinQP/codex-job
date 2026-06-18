import { EmptyState } from "../common/EmptyState";

export function SettingsPage() {
  return (
    <section className="page active" id="tab-settings">
      <div className="page-header summary-card">
        <h2>我的</h2>
        <p className="muted">v1.7 frontend split POC</p>
      </div>
      <div className="page-body stack">
        <EmptyState title="Settings shell ready" description="Token and diagnostics will be wired in v1.7.3." />
      </div>
    </section>
  );
}
