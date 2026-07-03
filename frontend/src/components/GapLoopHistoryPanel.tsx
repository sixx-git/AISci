import { Database } from 'lucide-react';
import type { ClosedLoopEvent } from '@/types';

interface GapLoopHistoryPanelProps {
  events?: ClosedLoopEvent[];
  /** 来自 data_acquisition 阶段输出的 gap_loop（兜底） */
  gapLoop?: Array<Record<string, unknown>>;
}

export function GapLoopHistoryPanel({ events = [], gapLoop }: GapLoopHistoryPanelProps) {
  const gapEvent = [...events].reverse().find((e) => e.type === 'data_gap_loop');
  const rounds =
    (gapEvent?.gap_loop as Array<Record<string, unknown>> | undefined) ||
    gapLoop ||
    [];

  if (rounds.length === 0) return null;

  return (
    <div className="p-4 rounded-bp border border-bp-border bg-bp-panel/30">
      <h3 className="text-sm font-semibold text-bp-text flex items-center gap-2 mb-2">
        <Database className="w-4 h-4 text-bp-cyan" />
        数据采集 · Gap 补搜历史
      </h3>
      {gapEvent?.summary && (
        <p className="text-xs text-bp-muted mb-3">{String(gapEvent.summary)}</p>
      )}
      <div className="space-y-2">
        {rounds.map((row, idx) => {
          const skipped = Boolean(row.skipped);
          const round = row.round ?? idx + 1;
          return (
            <div
              key={`gap-${round}-${idx}`}
              className="text-xs p-2 rounded-bp border border-bp-border/80 bg-bp-base/40"
            >
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <span className="font-medium text-bp-text">第 {String(round)} 轮</span>
                {skipped ? (
                  <span className="text-bp-muted">已跳过 · {String(row.reason || '达标')}</span>
                ) : (
                  <>
                    {row.score_before != null && row.score_after != null && (
                      <span className="text-bp-cyan font-mono">
                        覆盖率 {String(row.score_before)}→{String(row.score_after)}
                      </span>
                    )}
                    {(row.import_meta as { imported_count?: number } | undefined)?.imported_count != null && (
                      <span className="text-bp-green">
                        导入 {(row.import_meta as { imported_count: number }).imported_count} 项
                      </span>
                    )}
                    {row.candidates_added != null && (
                      <span className="text-bp-muted">候选 +{String(row.candidates_added)}</span>
                    )}
                  </>
                )}
              </div>
              {Array.isArray(row.queries) && row.queries.length > 0 && (
                <p className="text-bp-muted line-clamp-2">
                  查询：{(row.queries as string[]).slice(0, 2).join(' · ')}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
