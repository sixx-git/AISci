import { useEffect, type ReactNode } from 'react';
import { X } from 'lucide-react';

interface SideDrawerProps {
  open: boolean;
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}

export function SideDrawer({ open, title, subtitle, onClose, children, footer, wide = false }: SideDrawerProps) {
  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex" role="dialog" aria-modal="true" aria-label={title}>
      <div
        className="fixed inset-0 bg-bp-base/80 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />
      <div className={`relative ml-auto w-full ${wide ? 'max-w-3xl' : 'max-w-2xl'} h-full bg-bp-base border-l border-bp-cyan-dim shadow-bp-glow-strong overflow-hidden flex flex-col animate-slide-in-right`}>
        <div className="shrink-0 flex items-start justify-between gap-3 px-6 py-4 border-b border-bp-cyan-dim bg-bp-panel/50">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-bp-text">{title}</h2>
            {subtitle && (
              <p className="text-xs text-bp-muted mt-1 leading-relaxed">{subtitle}</p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-bp hover:bg-bp-surface text-bp-muted hover:text-bp-text transition-colors shrink-0"
            aria-label="关闭"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-6">
          {children}
        </div>
        {footer && (
          <div className="shrink-0 px-6 py-3 border-t border-bp-border bg-bp-panel/40">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
