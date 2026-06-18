import { EmptyState } from "../common/EmptyState";

export function SessionPage() {
  return (
    <section className="page active" id="tab-app">
      <div className="session-page">
        <header className="session-header">
          <div className="session-header-main">
            <div className="session-title-area">
              <h2 className="session-title">开始一次 Codex 会话</h2>
              <span className="session-subtitle">选择或新建会话后即可发送消息</span>
            </div>
          </div>
        </header>
        <main className="message-list">
          <div className="message-flow">
            <EmptyState title="Session shell ready" description="AppThread and AppTurn flows will be wired in v1.7.3." />
          </div>
        </main>
        <footer className="session-composer">
          <div className="composer-status-row">
            <span>请选择会话后发送消息</span>
          </div>
          <div className="composer-input-row">
            <textarea placeholder="输入消息" />
            <button className="btn-primary send-button" type="button">
              发送
            </button>
          </div>
        </footer>
      </div>
    </section>
  );
}
