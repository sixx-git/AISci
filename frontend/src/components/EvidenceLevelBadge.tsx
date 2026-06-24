import { cn } from '@/lib/utils';

export function evidenceLevelLabel(level: string | undefined): string {
  switch (level) {
    case 'high': return '高证据';
    case 'medium': return '中证据';
    default: return '低证据';
  }
}

export function evidenceLevelBadgeCls(level: string | undefined): string {
  switch (level) {
    case 'high': return 'bg-green-500/15 text-green-400 border-green-500/30';
    case 'medium': return 'bg-blue-500/15 text-blue-400 border-blue-500/30';
    default: return 'bg-gray-500/15 text-bp-muted border-gray-500/30';
  }
}

interface EvidenceLevelBadgeProps {
  level: string | undefined;
  className?: string;
}

export function EvidenceLevelBadge({ level, className }: EvidenceLevelBadgeProps) {
  return (
    <span className={cn(
      'text-[11px] px-1.5 py-0.5 rounded border',
      evidenceLevelBadgeCls(level),
      className,
    )}>
      {evidenceLevelLabel(level)}
    </span>
  );
}
