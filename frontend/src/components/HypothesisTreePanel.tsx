import { GitBranch, Scissors, Star } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { HypothesisTreeData } from '@/types';

interface HypothesisTreePanelProps {
  tree: HypothesisTreeData;
  embedded?: boolean;
  className?: string;
}

export function HypothesisTreePanel({ tree, embedded = false, className }: HypothesisTreePanelProps) {
  const branches = tree.branches ?? [];
  const pruned = tree.pruned_branches ?? [];
  const selectedId = tree.selected_branch_id;

  if (branches.length === 0) return null;

  return (
    <div className={cn(
      embedded ? '' : 'mb-5 p-4 rounded-bp border border-bp-border bg-bp-panel/30',
      className,
    )}>
      <h2 className="text-sm font-semibold text-bp-text mb-2 flex items-center gap-2">
        <GitBranch className="w-4 h-4 text-bp-cyan" />
        假设树 · BFTS 轻量剪枝
      </h2>

      {tree.iteration_summary && (
        <p className="text-xs text-bp-muted mb-3">{tree.iteration_summary}</p>
      )}

      <div className="space-y-2 mb-3 max-h-[360px] overflow-y-auto pr-1">
        {branches.map((branch) => {
          const isSelected = branch.branch_id === selectedId;
          return (
            <div
              key={branch.branch_id}
              className={cn(
                'p-2.5 rounded-bp border',
                isSelected
                  ? 'border-bp-yellow/40 bg-bp-yellow/5'
                  : 'border-bp-border bg-bp-base/40',
              )}
            >
              <div className="flex items-start justify-between gap-2 mb-1.5">
                <div className="flex items-center gap-1.5 min-w-0">
                  {isSelected && <Star className="w-3 h-3 text-bp-yellow shrink-0" />}
                  <span className="text-xs font-medium text-bp-text line-clamp-2">
                    {branch.label || branch.hypothesis}
                  </span>
                </div>
                <span className="text-sm font-mono font-bold text-bp-cyan shrink-0">
                  {branch.composite_score?.toFixed?.(1) ?? branch.composite_score}
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5 text-xs text-bp-muted">
                {branch.scores && Object.entries(branch.scores).map(([k, v]) => (
                  <span key={k} className="px-1.5 py-0.5 rounded-bp bg-bp-panel border border-bp-border">
                    {k}: {Number(v).toFixed(1)}
                  </span>
                ))}
                {branch.supporting_fact_count != null && (
                  <span>证据 {branch.supporting_fact_count} 条</span>
                )}
                {branch.alignment_score != null && (
                  <span>对齐 {branch.alignment_score}%</span>
                )}
                {branch.pilot_score != null && (
                  <span className="text-bp-cyan">pilot {branch.pilot_score.toFixed(1)}</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {pruned.length > 0 && (
        <div className="pt-2 border-t border-bp-border/80">
          <p className="text-xs text-bp-muted mb-1.5 flex items-center gap-1">
            <Scissors className="w-3 h-3" />
            已剪枝 {pruned.length} 条低分分支
          </p>
          <div className="flex flex-wrap gap-1.5">
            {pruned.slice(0, 6).map((p) => (
              <span
                key={p.branch_id}
                className="text-xs px-2 py-0.5 rounded-bp bg-danger-500/5 text-danger-400/80 border border-danger-500/10"
              >
                #{p.index + 1} · {p.composite_score?.toFixed?.(1)}
              </span>
            ))}
          </div>
        </div>
      )}

      {tree.evidence_coverage && (
        <div className="mt-3 text-xs text-bp-muted">
          证据覆盖: 已验证 {String(tree.evidence_coverage.verified_fact_refs ?? 0)}/
          {String(tree.evidence_coverage.total_fact_refs ?? 0)} 条 fact
          {tree.evidence_coverage.has_data_evidence ? ' · 含数据证据' : ''}
        </div>
      )}
    </div>
  );
}
