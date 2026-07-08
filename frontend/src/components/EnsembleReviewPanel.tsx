import { ShieldCheck, AlertTriangle, RefreshCw } from 'lucide-react';
import { Button } from '@/components/Button';
import type { EnsembleReviewData } from '@/types';

interface EnsembleReviewPanelProps {
  review: EnsembleReviewData;
  onRerunFromReview?: () => void;
}

export function EnsembleReviewPanel({ review, onRerunFromReview }: EnsembleReviewPanelProps) {
  const overall = review.overall ?? review.aggregated?.overall_score;
  const decision = review.decision ?? review.aggregated?.decision;
  const needsHuman = review.aggregated?.needs_human_review;
  const flags = review.aggregated?.disagreement_flags ?? [];
  const members = review.ensemble_reviews ?? [];

  return (
    <div className="p-4 rounded-lg border border-bp-border bg-bp-panel/30">
      <h3 className="text-sm font-semibold text-bp-text mb-3 flex items-center gap-2">
        <ShieldCheck className="w-4 h-4 text-bp-cyan" />
        集成评审（含红蓝反方权重）
      </h3>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        <StatBox label="综合分" value={overall != null ? Number(overall).toFixed(1) : '—'} accent="text-bp-yellow" />
        <StatBox
          label="决策"
          value={decision || '—'}
          accent={decision === 'Accept' ? 'text-bp-green' : decision === 'Reject' ? 'text-danger-400' : 'text-bp-muted'}
        />
        <StatBox label="评审者" value={String(members.length || 4)} accent="text-bp-cyan" />
        <StatBox label="需人工复核" value={needsHuman ? '是' : '否'} accent={needsHuman ? 'text-bp-yellow' : 'text-bp-muted'} />
      </div>

      {members.length > 0 && (
        <div className="mb-4">
          <p className="text-xs text-bp-muted mb-2">各评审者得分</p>
          <div className="space-y-1.5">
            {members.map((m) => (
              <div key={String(m.reviewer_id)} className="flex items-center justify-between text-xs">
                <span className="text-bp-muted">
                  {m.reviewer_id === 'con_challenger' ? '反方质疑' : String(m.reviewer_id)}
                  {m.weight != null ? ` (${(Number(m.weight) * 100).toFixed(0)}%)` : ''}
                </span>
                <span className="font-mono text-bp-text">{Number(m.overall_score ?? 0).toFixed(1)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {flags.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-1.5">
          {flags.map((f) => (
            <span key={f} className="text-xs px-2 py-0.5 rounded bg-bp-yellow/10 text-bp-yellow border border-bp-yellow/20">
              {f}
            </span>
          ))}
        </div>
      )}

      {(review.weaknesses?.length ?? 0) > 0 && (
        <div className="mb-3">
          <p className="text-xs text-bp-muted mb-1">主要不足</p>
          <ul className="space-y-1">
            {review.weaknesses!.slice(0, 5).map((w, i) => (
              <li key={i} className="text-xs text-bp-muted flex gap-1.5">
                <AlertTriangle className="w-3 h-3 text-danger-400/70 shrink-0 mt-0.5" />
                {w}
              </li>
            ))}
          </ul>
        </div>
      )}

      {(review.revision_suggestions?.length ?? 0) > 0 && (
        <div className="mb-3">
          <p className="text-xs text-bp-muted mb-1">修订建议</p>
          <ul className="space-y-1">
            {review.revision_suggestions!.slice(0, 4).map((s, i) => (
              <li key={i} className="text-xs text-bp-muted">• {s}</li>
            ))}
          </ul>
        </div>
      )}

      {decision === 'Reject' && onRerunFromReview && (
        <Button
          size="sm"
          variant="secondary"
          icon={<RefreshCw className="w-3.5 h-3.5" />}
          onClick={onRerunFromReview}
        >
          从假设评审起继续后续流程
        </Button>
      )}
    </div>
  );
}

function StatBox({ label, value, accent }: { label: string; value: string; accent: string }) {
  return (
    <div className="p-2.5 rounded border border-bp-border bg-bp-base/50">
      <p className="text-xs text-bp-muted mb-0.5">{label}</p>
      <p className={`text-lg font-bold font-mono ${accent}`}>{value}</p>
    </div>
  );
}
