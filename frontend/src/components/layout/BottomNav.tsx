export type TabName = "home" | "tasks" | "app" | "settings";

const tabs: Array<{ key: TabName; label: string }> = [
  { key: "home", label: "首页" },
  { key: "tasks", label: "任务" },
  { key: "app", label: "会话" },
  { key: "settings", label: "我的" }
];

type BottomNavProps = {
  activeTab: TabName;
  onChange: (tab: TabName) => void;
};

export function BottomNav({ activeTab, onChange }: BottomNavProps) {
  return (
    <nav className="bottom-nav" aria-label="Mobile sections">
      {tabs.map((tab) => (
        <button
          className={activeTab === tab.key ? "active" : ""}
          data-tab={tab.key}
          key={tab.key}
          onClick={() => onChange(tab.key)}
          type="button"
        >
          {tab.label}
        </button>
      ))}
    </nav>
  );
}
