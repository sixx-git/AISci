import { AlertCircle } from 'lucide-react';
import { Button } from '@/components/Button';
import { cn } from '@/lib/utils';

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
  compact?: boolean;
}

/** Blueprint Error 态 — 对齐设计稿 Frame 18-UI States */
export function ErrorState({
  title = '加载失败',
  message,
  onRetry,
  className,
  compact = false,
}: ErrorStateProps) {
  return (
    <div className={cn(
      'flex flex-col items-center justify-center text-center',
      compact ? 'py-10' : 'py-16',
      className,
    )}>
      <AlertCircle className={cn('text-danger-400 mb-3', compact ? 'w-8 h-8' : 'w-10 h-10')} />
      <p className={cn('text-danger-300 mb-1', compact ? 'text-sm' : 'text-base')}>{title}</p>
      {message && (
        <p className="text-xs text-bp-muted max-w-md mb-4">{message}</p>
      )}
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          重试
        </Button>
      )}
    </div>
  );
}
