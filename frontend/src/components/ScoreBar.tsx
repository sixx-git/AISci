import { cn } from '@/lib/utils';

interface ScoreBarProps {
  label: string;
  score?: number;
  max?: number;
  color?: 'blue' | 'green' | 'amber' | 'purple';
  /** compact：HypothesisCard 内联样式（单行 + 细条） */
  compact?: boolean;
  pendingLabel?: string;
}

const colorMap = {
  blue:   { bar: 'bg-bp-cyan',   bg: 'bg-bp-cyan-tint',   text: 'text-bp-cyan' },
  green:  { bar: 'bg-bp-green',  bg: 'bg-bp-green/20',  text: 'text-bp-green' },
  amber:  { bar: 'bg-bp-yellow',  bg: 'bg-bp-yellow/20',  text: 'text-bp-yellow' },
  purple: { bar: 'bg-bp-purple', bg: 'bg-bp-purple/20', text: 'text-bp-purple' },
};

export function ScoreBar({
  label,
  score,
  max = 100,
  color = 'blue',
  compact = false,
  pendingLabel = '—',
}: ScoreBarProps) {
  if (score == null || score <= 0) {
    if (compact) {
      return (
        <div className="flex items-center gap-2">
          <span className="text-xs text-bp-muted w-16 shrink-0">{label}</span>
          <div className="flex-1 h-1.5 bg-bp-surface rounded-full" />
          <span className="text-xs font-mono w-6 text-right text-bp-muted">{pendingLabel}</span>
        </div>
      );
    }
    return (
      <div>
        <div className="flex justify-between text-xs mb-1">
          <span className="text-bp-muted">{label}</span>
          <span className="font-mono text-bp-muted">{pendingLabel}</span>
        </div>
        <div className="h-2 bg-bp-panel rounded-full" />
      </div>
    );
  }

  const pct = Math.min(Math.max(0, (score / max) * 100), 100);
  const c = colorMap[color];

  if (compact) {
    return (
      <div className="flex items-center gap-2">
        <span className="text-xs text-bp-muted w-16 shrink-0">{label}</span>
        <div className="flex-1 h-1.5 bg-bp-surface rounded-full overflow-hidden">
          <div
            className={cn('h-full rounded-full', c.bar)}
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className={cn('text-xs font-mono w-6 text-right', c.text)}>{score}</span>
      </div>
    );
  }

  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-bp-muted">{label}</span>
        <span className={cn('font-mono font-medium', c.text)}>{score}</span>
      </div>
      <div className="h-2 bg-bp-panel rounded-full overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all duration-700', c.bar)}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
