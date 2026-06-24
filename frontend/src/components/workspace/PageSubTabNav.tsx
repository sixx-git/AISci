import { cn } from '@/lib/utils';

export interface PageSubTab {
  id: string;
  label: string;
}

interface PageSubTabNavProps {
  tabs: PageSubTab[];
  activeTab: string;
  onTabChange: (tabId: string) => void;
  className?: string;
}

/** 页内二级 Tab（数据集、文献库等），样式与项目 Tab 一致 */
export function PageSubTabNav({ tabs, activeTab, onTabChange, className }: PageSubTabNavProps) {
  return (
    <div className={cn('bp-tab-nav', className)}>
      <nav className="flex gap-1 overflow-x-auto -mb-px">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => onTabChange(tab.id)}
              className={cn('bp-tab', isActive && 'bp-tab-active')}
            >
              {tab.label}
            </button>
          );
        })}
      </nav>
    </div>
  );
}
