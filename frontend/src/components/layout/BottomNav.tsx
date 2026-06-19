export type TabName = "home" | "tasks" | "app" | "settings";

const tabs: Array<{ key: TabName; label: string; icon: string }> = [
  { key: "home", label: "工作台", icon: "⌂" },
  { key: "tasks", label: "任务", icon: "□" },
  { key: "app", label: "会话", icon: "○" },
  { key: "settings", label: "我的", icon: "◇" }
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
          <span aria-hidden="true" className="bottom-nav-icon">{tab.icon}</span>
          <span>{tab.label}</span>
        </button>
      ))}
    </nav>
  );
}
