function App() {
  return (
    <main className="mobile-shell">
      <section className="hero">
        <div>
          <p className="eyebrow">v1.7 frontend split POC</p>
          <h1>Codex Mobile Console</h1>
          <p className="summary">
            Frontend build is being served by FastAPI. Full task and App Server
            session pages will be migrated in later v1.7 steps.
          </p>
        </div>
        <div className="status-card" aria-label="Frontend hosting status">
          <span className="status-dot" />
          <span>React + TypeScript + Vite</span>
        </div>
      </section>

      <section className="panel">
        <h2>Current Scope</h2>
        <ul>
          <li>Frontend project skeleton is available under frontend/.</li>
          <li>npm run build outputs static files to frontend/dist.</li>
          <li>FastAPI serves this built page from /mobile.</li>
        </ul>
      </section>
    </main>
  );
}

export default App;
