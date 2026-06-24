import React from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/Button';

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  className?: string;
}

/**
 * 统一空状态组件 —— 用于无数据时的占位展示
 */
export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn(
      'flex flex-col items-center justify-center py-16 px-4 text-center',
      className,
    )}>
      {icon && (
        <div className="w-16 h-16 rounded-bp bg-bp-panel flex items-center justify-center mb-4 text-bp-muted">
          {icon}
        </div>
      )}
      <h3 className="text-lg font-medium text-bp-text mb-2">{title}</h3>
      {description && (
        <p className="text-sm text-bp-muted max-w-md mb-6">{description}</p>
      )}
      {action && (
        <Button variant="primary" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </div>
  );
}