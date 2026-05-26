
import { Settings2 } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { EmptyState } from '@/components/EmptyState';

export function Settings() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <PageHeader
        title="设置"
        subtitle="配置 AI Scientist 选项"
      />
      <EmptyState
        icon={<Settings2 className="w-8 h-8" />}
        title="设置页面"
        description="配置选项即将上线"
      />
    </div>
  );
}
