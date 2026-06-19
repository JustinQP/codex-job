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
  const { toast, showToast } = useToast();
  const currentTab = ["home", "tasks", "app", "settings"].includes(activeTab)
    ? (activeTab as TabName)
    : "home";
  const pageTitle: Record<TabName, string> = {
    home: "工作台",
    tasks: "任务",
    app: "会话",
    settings: "我的"
  };
  const pageSubtitle: Record<TabName, string> = {
    home: "Codex Mobile Console",
    tasks: "查看、筛选和处理远程任务",
    app: "Codex Remote Runner + App Server Sidecar",
    settings: "连接、诊断与维护"
  };

  return (
    <div className={`app-shell app-shell-${currentTab}`}>
      <header className="top-bar">
        <h1>{pageTitle[currentTab]}</h1>
        <div className="top-subtitle">{pageSubtitle[currentTab]}</div>
      </header>

      <main>
        {currentTab === "home" ? <HomePage showToast={showToast} /> : null}
        {currentTab === "tasks" ? <TasksPage showToast={showToast} /> : null}
        {currentTab === "app" ? <SessionPage showToast={showToast} /> : null}
        {currentTab === "settings" ? <SettingsPage showToast={showToast} /> : null}
      </main>

      <BottomNav activeTab={currentTab} onChange={setActiveTab} />
      <Toast toast={toast} />
    </div>
  );
}

export default App;
