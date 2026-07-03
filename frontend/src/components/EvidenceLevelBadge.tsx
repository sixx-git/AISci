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
    case 'high': return 'bg-bp-green/15 text-bp-green border-bp-green/30';
    case 'medium': return 'bg-bp-cyan-tint text-bp-cyan border-bp-cyan/30';
    default: return 'bg-bp-panel text-bp-muted border-bp-border';
  }
}

interface EvidenceLevelBadgeProps {
  level: string | undefined;
  className?: string;
}

export function EvidenceLevelBadge({ level, className }: EvidenceLevelBadgeProps) {
  return (
    <span className={cn(
      'text-xs px-1.5 py-0.5 rounded border',
      evidenceLevelBadgeCls(level),
      className,
    )}>
      {evidenceLevelLabel(level)}
    </span>
  );
}
