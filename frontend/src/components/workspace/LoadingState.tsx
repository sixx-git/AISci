import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface LoadingStateProps {
  message?: string;
  className?: string;
  compact?: boolean;
}

/** Blueprint Loading 态 — 对齐设计稿 Frame 18-UI States */
export function LoadingState({
  message = '加载中...',
  className,
  compact = false,
}: LoadingStateProps) {
  return (
    <div className={cn(
      'flex flex-col items-center justify-center text-bp-muted',
      compact ? 'py-10' : 'py-16',
      className,
    )}>
      <Loader2 className={cn('animate-spin text-bp-cyan mb-3', compact ? 'w-6 h-6' : 'w-8 h-8')} />
      <p className="text-sm">{message}</p>
    </div>
  );
}
