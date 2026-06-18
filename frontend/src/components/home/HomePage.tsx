import { EmptyState } from "../common/EmptyState";

export function HomePage() {
  return (
    <section className="page active" id="tab-home">
      <div className="page-header summary-card home-hero">
        <h2>Codex 工作台</h2>
        <p className="muted">先看状态，再进入任务或会话。</p>
      </div>
      <div className="page-body stack">
        <EmptyState title="Frontend shell ready" description="Home data will be wired in v1.7.3." />
      </div>
    </section>
  );
}
