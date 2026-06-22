export type TabName = "app" | "projects" | "runs" | "settings";

const tabs: Array<{ key: TabName; label: string; icon: string }> = [
  { key: "app", label: "会话", icon: "○" },
  { key: "projects", label: "项目", icon: "⌂" },
  { key: "runs", label: "运行", icon: "□" },
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
