import { cn } from '@/lib/utils';

/**
 * 统一状态标签 —— 5 种标准状态：
 *   pending     → 灰色（未开始）
 *   running     → 蓝色（运行中）
 *   completed   → 绿色（已完成）
 *   failed      → 红色（失败）
 *   human_review → 紫色（需人工确认）
 */
export type StatusType =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'human_review'
  // 向后兼容旧类型
  | 'error'
  | 'draft'
  | 'success';

interface StatusBadgeProps {
  status: StatusType;
  label?: string;
  className?: string;
}

const statusConfig: Record<StatusType, { className: string; label: string }> = {
  pending:      { className: 'badge-pending',   label: '未开始' },
  running:      { className: 'badge-running',   label: '运行中' },
  completed:    { className: 'badge-completed', label: '已完成' },
  failed:       { className: 'badge-failed',    label: '失败' },
  human_review: { className: 'badge-review',    label: '需人工确认' },
  // 别名
  error:   { className: 'badge-failed',         label: '失败' },
  draft:   { className: 'badge-pending',        label: '草稿' },
  success: { className: 'badge-completed',      label: '成功' },
};

export function StatusBadge({ status, label, className }: StatusBadgeProps) {
  const config = statusConfig[status] || statusConfig.pending;

  return (
    <span className={cn(config.className, className)}>
      {label || config.label}
    </span>
  );
}