import type { RunLogStatus } from '@/types';

export const RUN_LOG_STATUS_BADGE: Record<
  RunLogStatus,
  { label: string; className: string; dotClass: string }
> = {
  success: {
    label: '成功',
    className: 'text-bp-green bg-bp-green/10 border-bp-green/20',
    dotClass: 'bg-bp-green',
  },
  running: {
    label: '运行中',
    className: 'text-bp-cyan bg-bp-cyan-tint border-bp-cyan/20 animate-pulse',
    dotClass: 'bg-bp-cyan',
  },
  failed: {
    label: '失败',
    className: 'text-danger-400 bg-danger-500/10 border-danger-500/20',
    dotClass: 'bg-danger-400',
  },
  pending: {
    label: '等待中',
    className: 'text-bp-muted bg-bp-panel border-bp-border',
    dotClass: 'bg-bp-muted',
  },
};
