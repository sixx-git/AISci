import { ClipboardList } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { EmptyState } from '@/components/EmptyState';

export function Reports() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <PageHeader
        title="报告中心"
        subtitle="查看和管理 AI Scientist 生成的研究报告"
      />
      <EmptyState
        icon={<ClipboardList className="w-8 h-8" />}
        title="报告中心"
        description="报告管理功能即将上线"
      />
    </div>
  );
}