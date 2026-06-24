import { PROJECT_TABS } from '@/config/projectTabs';
import { cn } from '@/lib/utils';

interface ProjectTabNavProps {
  activeTab: string;
  onTabChange: (tabId: string) => void;
}

export function ProjectTabNav({ activeTab, onTabChange }: ProjectTabNavProps) {
  return (
    <div className="bp-tab-nav">
      <nav className="flex gap-1 overflow-x-auto -mb-px">
        {PROJECT_TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => onTabChange(tab.id)}
              className={cn('bp-tab', isActive && 'bp-tab-active')}
            >
              <Icon className="w-4 h-4 shrink-0" />
              {tab.label}
            </button>
          );
        })}
      </nav>
    </div>
  );
}
