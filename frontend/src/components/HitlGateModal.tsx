import { useEffect, useId } from 'react';
import { AlertTriangle, ArrowRight, Lightbulb, X } from 'lucide-react';
import { Button } from '@/components/Button';
import { getHitlGateReviewTarget } from '@/config/hitlGateReview';
import type { HitlGateInfo } from '@/types';

interface HitlGateModalProps {
  open: boolean;
  gate?: HitlGateInfo | null;
  onDismiss: () => void;
  onGoReview: (tab: string) => void;
}

export function HitlGateModal({
  open,
  gate,
  onDismiss,
  onGoReview,
}: HitlGateModalProps) {
  const titleId = useId();
  const target = getHitlGateReviewTarget(gate?.stage);
  const isHypothesisGate = gate?.stage === 'hypothesis_generation' || gate?.stage === 'hypothesis_review';

  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onDismiss();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, onDismiss]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-bp-base/80 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
    >
      <div
        className="w-full max-w-md rounded-xl border border-bp-yellow/30 bg-[#161b22] shadow-bp-glow"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 px-5 pt-5 pb-3">
          <div className="flex items-start gap-3 min-w-0">
            <div className="shrink-0 w-10 h-10 rounded-bp bg-bp-yellow/15 border border-bp-yellow/30 flex items-center justify-center">
              {isHypothesisGate ? (
                <Lightbulb className="w-5 h-5 text-bp-yellow" />
              ) : (
                <AlertTriangle className="w-5 h-5 text-bp-yellow" />
              )}
            </div>
            <div className="min-w-0">
              <h3 id={titleId} className="text-base font-semibold text-bp-yellow">
                {target.title}
              </h3>
              <p className="text-sm text-bp-muted mt-1">{target.description}</p>
              {gate?.paused_at && (
                <p className="text-xs text-bp-muted mt-1">暂停于 {gate.paused_at}</p>
              )}
            </div>
          </div>
          <button
            type="button"
            onClick={onDismiss}
            className="shrink-0 p-1 rounded-bp text-bp-muted hover:text-bp-text hover:bg-bp-cyan-tint/30 transition-colors"
            aria-label="稍后处理"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="px-5 pb-5 space-y-4">
          <div className="rounded-bp border border-bp-border bg-bp-base/50 px-3 py-2.5">
            <p className="text-xs text-bp-muted">{target.continueHint}</p>
          </div>

          <div className="flex flex-wrap gap-2 justify-end">
            <Button size="sm" variant="secondary" onClick={onDismiss}>
              稍后处理
            </Button>
            <Button
              size="sm"
              variant="primary"
              onClick={() => onGoReview(target.tab)}
              className="gap-1.5"
            >
              {target.ctaLabel}
              <ArrowRight className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
