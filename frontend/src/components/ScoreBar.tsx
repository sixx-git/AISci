import { cn } from '@/lib/utils';

interface ScoreBarProps {
  label: string;
  score: number;
  max?: number;
  color?: 'blue' | 'green' | 'amber' | 'purple';
}

const colorMap = {
  blue:   { bar: 'bg-blue-500',   bg: 'bg-blue-500/20',   text: 'text-blue-400' },
  green:  { bar: 'bg-green-500',  bg: 'bg-green-500/20',  text: 'text-green-400' },
  amber:  { bar: 'bg-amber-500',  bg: 'bg-amber-500/20',  text: 'text-amber-400' },
  purple: { bar: 'bg-purple-500', bg: 'bg-purple-500/20', text: 'text-purple-400' },
};

export function ScoreBar({ label, score, max = 100, color = 'blue' }: ScoreBarProps) {
  const pct = Math.min((score / max) * 100, 100);
  const c = colorMap[color];

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