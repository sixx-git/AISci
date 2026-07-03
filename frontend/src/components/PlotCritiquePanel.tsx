import { Image, AlertTriangle, RefreshCw } from 'lucide-react';
import type { PlotQualityData } from '@/types';

interface PlotCritiquePanelProps {
  plotQuality: PlotQualityData;
}

export function PlotCritiquePanel({ plotQuality }: PlotCritiquePanelProps) {
  const critique = plotQuality.critique;
  const critiques = critique?.critiques ?? [];
  const avg = critique?.average_score;

  return (
    <div className="p-4 rounded-lg border border-bp-border bg-bp-panel/30">
      <h3 className="text-sm font-semibold text-bp-text mb-3 flex items-center gap-2">
        <Image className="w-4 h-4 text-bp-cyan" />
        VLM 图表质量评审
      </h3>

      <div className="flex flex-wrap gap-3 mb-3 text-xs">
        {avg != null && (
          <span className="font-mono text-bp-yellow">平均分 {Number(avg).toFixed(1)}</span>
        )}
        {plotQuality.redraw_count != null && plotQuality.redraw_count > 0 && (
          <span className="flex items-center gap-1 text-bp-green">
            <RefreshCw className="w-3 h-3" /> 已自动重绘 {plotQuality.redraw_count} 次
          </span>
        )}
        {plotQuality.needs_human_review && (
          <span className="flex items-center gap-1 text-bp-yellow">
            <AlertTriangle className="w-3 h-3" /> 需人工复核
          </span>
        )}
        {critique?.degradation_reason && (
          <span className="text-xs text-bp-muted block w-full mt-1">
            {critique.degradation_reason}
            {critique.review_mode ? ` · 模式: ${critique.review_mode}` : ''}
          </span>
        )}
      </div>

      {critiques.length > 0 && (
        <div className="space-y-2">
          {critiques.map((c) => (
            <div key={String(c.plot_id)} className="p-2 rounded border border-bp-border/80 bg-bp-base/40 text-xs">
              <div className="flex justify-between mb-1">
                <span className="text-bp-text truncate">{String(c.plot_id)}</span>
                <span className="font-mono text-bp-text">{Number(c.overall_score ?? 0).toFixed(1)}</span>
              </div>
              <div className="text-xs text-bp-muted">
                reviewer: {String(c.reviewer ?? '—')} · misleading: {String(c.misleading_risk ?? '—')}
              </div>
              {(c.issues as string[] | undefined)?.slice(0, 2).map((issue, i) => (
                <p key={i} className="text-xs text-danger-400/80 mt-0.5">• {issue}</p>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
