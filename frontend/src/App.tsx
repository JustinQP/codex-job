import { useEffect } from "react";

import { BottomNav, type TabName } from "./components/layout/BottomNav";
import { Toast } from "./components/layout/Toast";
import { ProjectsPage } from "./components/projects/ProjectsPage";
import { RunsPage } from "./components/runs/RunsPage";
import { SessionPage } from "./components/session/SessionPage";
import { SettingsPage } from "./components/settings/SettingsPage";
import { useLocalStorage } from "./hooks/useLocalStorage";
import { useToast } from "./hooks/useToast";
import { UI_STATE_KEYS } from "./state/storage";

function App() {
  const [activeTab, setActiveTab] = useLocalStorage(UI_STATE_KEYS.activeTab, "app");
  const { toast, showToast } = useToast();
  const tabAlias: Record<string, TabName> = {
    home: "app",
    tasks: "runs",
    app: "app",
    projects: "projects",
    runs: "runs",
    settings: "settings"
  };
  const currentTab = tabAlias[activeTab] || "app";
  const pageTitle: Record<TabName, string> = {
    app: "会话",
    projects: "项目",
    runs: "运行",
    settings: "我的"
  };
  const pageSubtitle: Record<TabName, string> = {
    app: "连续对话控制",
    projects: "当前工作目录与项目配置",
    runs: "后台运行记录",
    settings: "连接、诊断与维护"
  };

  useEffect(() => {
    if (activeTab !== currentTab) setActiveTab(currentTab);
  }, [activeTab, currentTab, setActiveTab]);

  function handleTabChange(tab: TabName) {
    setActiveTab(tab);
  }

  return (
    <div className={`app-shell app-shell-${currentTab}`}>
      <header className="top-bar">
        <h1>{pageTitle[currentTab]}</h1>
        <div className="top-subtitle">{pageSubtitle[currentTab]}</div>
      </header>

      <main>
        {currentTab === "app" ? <SessionPage showToast={showToast} /> : null}
        {currentTab === "projects" ? <ProjectsPage showToast={showToast} /> : null}
        {currentTab === "runs" ? <RunsPage showToast={showToast} /> : null}
        {currentTab === "settings" ? <SettingsPage showToast={showToast} /> : null}
      </main>

      <BottomNav activeTab={currentTab} onChange={handleTabChange} />
      <Toast toast={toast} />
    </div>
  );
}

export default App;
