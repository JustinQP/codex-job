import { EmptyState } from "../common/EmptyState";

export function TasksPage() {
  return (
    <section className="page active" id="tab-tasks">
      <div className="page-header summary-card">
        <div className="row">
          <h2>任务</h2>
        </div>
      </div>
      <div className="page-body stack">
        <EmptyState title="Tasks shell ready" description="Task list and forms will be wired in v1.7.3." />
      </div>
    </section>
  );
}
