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
    <div className="p-4 rounded-lg border border-dark-700 bg-dark-800/30">
      <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
        <ShieldCheck className="w-4 h-4 text-blue-400" />
        集成评审（Ensemble Review）
      </h3>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        <StatBox label="综合分" value={overall != null ? Number(overall).toFixed(1) : '—'} accent="text-amber-400" />
        <StatBox
          label="决策"
          value={decision || '—'}
          accent={decision === 'Accept' ? 'text-green-400' : decision === 'Reject' ? 'text-red-400' : 'text-gray-400'}
        />
        <StatBox label="评审者" value={String(members.length || 4)} accent="text-primary-400" />
        <StatBox label="需人工复核" value={needsHuman ? '是' : '否'} accent={needsHuman ? 'text-yellow-400' : 'text-gray-500'} />
      </div>

      {members.length > 0 && (
        <div className="mb-4">
          <p className="text-[11px] text-gray-500 mb-2">各评审者得分</p>
          <div className="space-y-1.5">
            {members.map((m) => (
              <div key={String(m.reviewer_id)} className="flex items-center justify-between text-xs">
                <span className="text-gray-400">
                  {String(m.reviewer_id)}
                  {m.weight != null ? ` (${(Number(m.weight) * 100).toFixed(0)}%)` : ''}
                </span>
                <span className="font-mono text-gray-200">{Number(m.overall_score ?? 0).toFixed(1)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {flags.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-1.5">
          {flags.map((f) => (
            <span key={f} className="text-[10px] px-2 py-0.5 rounded bg-yellow-500/10 text-yellow-400 border border-yellow-500/20">
              {f}
            </span>
          ))}
        </div>
      )}

      {(review.weaknesses?.length ?? 0) > 0 && (
        <div className="mb-3">
          <p className="text-[11px] text-gray-500 mb-1">主要不足</p>
          <ul className="space-y-1">
            {review.weaknesses!.slice(0, 5).map((w, i) => (
              <li key={i} className="text-xs text-gray-400 flex gap-1.5">
                <AlertTriangle className="w-3 h-3 text-red-400/70 shrink-0 mt-0.5" />
                {w}
              </li>
            ))}
          </ul>
        </div>
      )}

      {(review.revision_suggestions?.length ?? 0) > 0 && (
        <div className="mb-3">
          <p className="text-[11px] text-gray-500 mb-1">修订建议</p>
          <ul className="space-y-1">
            {review.revision_suggestions!.slice(0, 4).map((s, i) => (
              <li key={i} className="text-xs text-gray-400">• {s}</li>
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
          从假设评审阶段重跑
        </Button>
      )}
    </div>
  );
}

function StatBox({ label, value, accent }: { label: string; value: string; accent: string }) {
  return (
    <div className="p-2.5 rounded border border-dark-700 bg-dark-900/50">
      <p className="text-[10px] text-gray-500 mb-0.5">{label}</p>
      <p className={`text-lg font-bold font-mono ${accent}`}>{value}</p>
    </div>
  );
}
