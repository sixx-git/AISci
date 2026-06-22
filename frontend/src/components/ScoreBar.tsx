import { cn } from '@/lib/utils';

interface ScoreBarProps {
  label: string;
  score: number;
  max?: number;
  color?: 'blue' | 'green' | 'amber' | 'purple';
  /** compact：HypothesisCard 内联样式（单行 + 细条） */
  compact?: boolean;
}

const colorMap = {
  blue:   { bar: 'bg-blue-500',   bg: 'bg-blue-500/20',   text: 'text-blue-400' },
  green:  { bar: 'bg-green-500',  bg: 'bg-green-500/20',  text: 'text-green-400' },
  amber:  { bar: 'bg-amber-500',  bg: 'bg-amber-500/20',  text: 'text-amber-400' },
  purple: { bar: 'bg-purple-500', bg: 'bg-purple-500/20', text: 'text-purple-400' },
};

export function ScoreBar({
  label,
  score,
  max = 100,
  color = 'blue',
  compact = false,
}: ScoreBarProps) {
  const pct = Math.min(Math.max(0, (score / max) * 100), 100);
  const c = colorMap[color];

  if (compact) {
    return (
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-500 w-16 shrink-0">{label}</span>
        <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
          <div
            className={cn('h-full rounded-full', c.bar)}
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className="text-xs text-gray-400 font-mono w-6 text-right">{score}</span>
      </div>
    );
  }

  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-gray-400">{label}</span>
        <span className={cn('font-mono font-medium', c.text)}>{score}</span>
      </div>
      <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all duration-700', c.bar)}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
