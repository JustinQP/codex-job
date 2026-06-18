import { useState } from "react";

import { HomePage } from "./components/home/HomePage";
import { BottomNav, type TabName } from "./components/layout/BottomNav";
import { Toast, type ToastState } from "./components/layout/Toast";
import { SessionPage } from "./components/session/SessionPage";
import { SettingsPage } from "./components/settings/SettingsPage";
import { TasksPage } from "./components/tasks/TasksPage";

function App() {
  const [activeTab, setActiveTab] = useState<TabName>("home");
  const [toast] = useState<ToastState>(null);

  return (
    <div className="app-shell">
      <header className="top-bar">
        <h1>Codex Mobile Console</h1>
        <div className="top-subtitle">Codex Remote Runner + App Server Sidecar</div>
      </header>

      <main>
        {activeTab === "home" ? <HomePage /> : null}
        {activeTab === "tasks" ? <TasksPage /> : null}
        {activeTab === "app" ? <SessionPage /> : null}
        {activeTab === "settings" ? <SettingsPage /> : null}
      </main>

      <BottomNav activeTab={activeTab} onChange={setActiveTab} />
      <Toast toast={toast} />
    </div>
  );
}

export default App;
