
import { cn } from '@/lib/utils';

type StatusType = 'pending' | 'running' | 'completed' | 'error' | 'draft' | 'success';

interface StatusBadgeProps {
  status: StatusType;
  label?: string;
}

const statusConfig: Record<StatusType, { bg: string; text: string; label: string }> = {
  pending: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', label: '待处理' },
  running: { bg: 'bg-blue-500/20', text: 'text-blue-400', label: '运行中' },
  completed: { bg: 'bg-green-500/20', text: 'text-green-400', label: '已完成' },
  success: { bg: 'bg-green-500/20', text: 'text-green-400', label: '成功' },
  error: { bg: 'bg-red-500/20', text: 'text-red-400', label: '错误' },
  draft: { bg: 'bg-gray-500/20', text: 'text-gray-400', label: '草稿' },
};

export function StatusBadge({ status, label }: StatusBadgeProps) {
  const config = statusConfig[status] || statusConfig.pending;

  return (
    <span className={cn('px-2.5 py-1 rounded-full text-xs font-medium', config.bg, config.text)}>
      {label || config.label}
    </span>
  );
}
