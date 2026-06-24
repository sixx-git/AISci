import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

interface CollapsiblePanelProps {
  title: string;
  subtitle?: string;
  defaultOpen?: boolean;
  badge?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}

/** 工作流 / 详情页可折叠区块 */
export function CollapsiblePanel({
  title,
  subtitle,
  defaultOpen = false,
  badge,
  children,
  className,
}: CollapsiblePanelProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className={cn('rounded-bp border border-bp-border bg-bp-panel/40 overflow-hidden', className)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-4 py-3 text-left hover:bg-bp-panel/60 transition-colors"
      >
        {open ? (
          <ChevronDown className="w-4 h-4 text-bp-muted shrink-0" />
        ) : (
          <ChevronRight className="w-4 h-4 text-bp-muted shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-bp-text">{title}</div>
          {subtitle && <div className="text-xs text-bp-muted mt-0.5">{subtitle}</div>}
        </div>
        {badge}
      </button>
      {open && <div className="px-4 pb-4 border-t border-bp-cyan-dim">{children}</div>}
    </div>
  );
}
