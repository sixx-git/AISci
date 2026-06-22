import { useState } from 'react';
import { Image, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import dataFinderService, { type DataFinderResult } from '@/services/dataFinderService';

interface FigureReviewPanelProps {
  projectId: string;
  figures?: DataFinderResult['figures'];
  onUpdated?: () => void;
}

interface FigureItem {
  figure_id?: string;
  figure_number?: string;
  caption?: string;
  extraction_method?: string;
  extraction_tier?: string;
  extraction_confidence?: number;
  needs_manual_review?: boolean;
  included_in_csv?: boolean;
  review_status?: string;
  extracted_series_preview?: Array<Record<string, unknown>>;
}

export function FigureReviewPanel({ projectId, figures = [], onUpdated }: FigureReviewPanelProps) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pending = (figures as FigureItem[]).filter(
    (f) => f.needs_manual_review && !f.included_in_csv && f.review_status !== 'rejected',
  );

  if (!figures?.length) return null;

  const handleReview = async (figureId: string, action: 'confirm' | 'reject') => {
    setBusyId(figureId);
    setError(null);
    try {
      const res = await dataFinderService.reviewFigure(projectId, figureId, action);
      if (res.code === 200) {
        onUpdated?.();
      } else {
        setError(res.message || '复核失败');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '复核失败');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <Card className="p-4 border-amber-500/20 bg-amber-500/5">
      <h4 className="text-sm font-semibold text-amber-300 mb-2 flex items-center gap-1.5">
        <Image className="w-4 h-4" />
        图表数据复核 · {pending.length} 待确认
      </h4>
      <p className="text-[10px] text-gray-500 mb-3">
        L1 元信息 → L2 近似序列（低置信）→ L3 人工确认后写入 CSV
      </p>

      {error && <p className="text-xs text-red-400 mb-2">{error}</p>}

      <div className="space-y-3 max-h-80 overflow-y-auto">
        {(figures as FigureItem[]).slice(0, 8).map((fig) => {
          const preview = fig.extracted_series_preview || [];
          return (
            <div
              key={fig.figure_id}
              className="p-3 rounded border border-dark-700 bg-dark-900/40 text-xs"
            >
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <span className="font-medium text-gray-200">Fig {fig.figure_number || '—'}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-dark-800 text-gray-400">
                  {fig.extraction_tier || fig.extraction_method || 'rule'}
                </span>
                <span className="text-[10px] text-amber-400">
                  conf={String(fig.extraction_confidence ?? '—')}
                </span>
                {fig.included_in_csv && (
                  <span className="text-[10px] text-green-400 flex items-center gap-0.5">
                    <CheckCircle2 className="w-3 h-3" /> 已入 CSV
                  </span>
                )}
              </div>
              <p className="text-[10px] text-gray-500 line-clamp-2 mb-2">{fig.caption}</p>
              {preview.length > 0 && (
                <div className="text-[10px] text-gray-400 mb-2 font-mono">
                  {preview.slice(0, 3).map((row, i) => (
                    <div key={i}>
                      {String(row.series)} = {String(row.value ?? '—')}
                    </div>
                  ))}
                </div>
              )}
              {!fig.included_in_csv && fig.review_status !== 'rejected' && (
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={busyId === fig.figure_id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                    onClick={() => fig.figure_id && handleReview(fig.figure_id, 'confirm')}
                    disabled={busyId === fig.figure_id}
                  >
                    确认入 CSV
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={<XCircle className="w-3.5 h-3.5" />}
                    onClick={() => fig.figure_id && handleReview(fig.figure_id, 'reject')}
                    disabled={busyId === fig.figure_id}
                  >
                    拒绝
                  </Button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}
