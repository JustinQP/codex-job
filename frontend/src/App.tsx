import { HomePage } from "./components/home/HomePage";
import { BottomNav, type TabName } from "./components/layout/BottomNav";
import { Toast } from "./components/layout/Toast";
import { SessionPage } from "./components/session/SessionPage";
import { SettingsPage } from "./components/settings/SettingsPage";
import { TasksPage } from "./components/tasks/TasksPage";
import { useLocalStorage } from "./hooks/useLocalStorage";
import { useToast } from "./hooks/useToast";
import { UI_STATE_KEYS } from "./state/storage";

function App() {
  const [activeTab, setActiveTab] = useLocalStorage(UI_STATE_KEYS.activeTab, "home");
  const { toast } = useToast();
  const currentTab = ["home", "tasks", "app", "settings"].includes(activeTab)
    ? (activeTab as TabName)
    : "home";

  return (
    <div className="app-shell">
      <header className="top-bar">
        <h1>Codex Mobile Console</h1>
        <div className="top-subtitle">Codex Remote Runner + App Server Sidecar</div>
      </header>

      <main>
        {currentTab === "home" ? <HomePage /> : null}
        {currentTab === "tasks" ? <TasksPage /> : null}
        {currentTab === "app" ? <SessionPage /> : null}
        {currentTab === "settings" ? <SettingsPage /> : null}
      </main>

      <BottomNav activeTab={currentTab} onChange={setActiveTab} />
      <Toast toast={toast} />
    </div>
  );
}

export default App;
