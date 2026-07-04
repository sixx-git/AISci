import { useEffect, useId, useRef } from 'react';
import { AlertTriangle, X } from 'lucide-react';
import { Button } from '@/components/Button';

export const DELETE_CONFIRM_PHRASE = '确认删除';

interface ConfirmDeleteDialogProps {
  open: boolean;
  title?: string;
  itemName: string;
  description?: string;
  confirmPhrase?: string;
  confirmValue: string;
  onConfirmValueChange: (value: string) => void;
  onConfirm: () => void;
  onCancel: () => void;
  isLoading?: boolean;
  error?: string | null;
}

export function ConfirmDeleteDialog({
  open,
  title = '删除项目',
  itemName,
  description = '此操作不可撤销，将永久删除该项目及其相关数据。',
  confirmPhrase = DELETE_CONFIRM_PHRASE,
  confirmValue,
  onConfirmValueChange,
  onConfirm,
  onCancel,
  isLoading = false,
  error = null,
}: ConfirmDeleteDialogProps) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const canConfirm = confirmValue === confirmPhrase && !isLoading;

  useEffect(() => {
    if (!open) return undefined;
    const timer = setTimeout(() => inputRef.current?.focus(), 50);
    return () => clearTimeout(timer);
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isLoading) onCancel();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, isLoading, onCancel]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-bp-base/80 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby={`${inputId}-title`}
      onClick={() => {
        if (!isLoading) onCancel();
      }}
    >
      <div
        className="w-full max-w-md rounded-xl border border-bp-border bg-[#161b22] shadow-bp-glow"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 px-5 pt-5 pb-3">
          <div className="flex items-start gap-3 min-w-0">
            <div className="shrink-0 w-10 h-10 rounded-bp bg-red-500/10 border border-red-500/20 flex items-center justify-center">
              <AlertTriangle className="w-5 h-5 text-red-400" />
            </div>
            <div className="min-w-0">
              <h3 id={`${inputId}-title`} className="text-base font-semibold text-bp-text">
                {title}
              </h3>
              <p className="text-sm text-bp-muted mt-1">
                {description}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onCancel}
            disabled={isLoading}
            className="shrink-0 p-1 rounded-bp text-bp-muted hover:text-bp-text hover:bg-bp-cyan-tint/30 transition-colors disabled:opacity-50"
            aria-label="关闭"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="px-5 pb-5 space-y-4">
          <div className="rounded-bp border border-bp-border bg-bp-base/50 px-3 py-2.5">
            <p className="text-xs text-bp-muted mb-1">即将删除</p>
            <p className="text-sm font-medium text-bp-text truncate" title={itemName}>
              {itemName}
            </p>
          </div>

          <div>
            <label htmlFor={inputId} className="block text-sm text-bp-muted mb-2">
              请输入
              <span className="mx-1 font-mono text-bp-text">{confirmPhrase}</span>
              以确认删除
            </label>
            <input
              ref={inputRef}
              id={inputId}
              type="text"
              value={confirmValue}
              onChange={(e) => onConfirmValueChange(e.target.value)}
              disabled={isLoading}
              placeholder={confirmPhrase}
              className="input-field w-full"
              autoComplete="off"
              spellCheck={false}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && canConfirm) onConfirm();
              }}
            />
          </div>

          {error && (
            <div className="rounded-bp border border-danger-500/30 bg-danger-500/10 px-3 py-2 text-sm text-danger-400">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <Button
              type="button"
              variant="secondary"
              onClick={onCancel}
              disabled={isLoading}
            >
              取消
            </Button>
            <Button
              type="button"
              variant="danger"
              onClick={onConfirm}
              disabled={!canConfirm}
              isLoading={isLoading}
            >
              删除
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
