import { GitBranch, Scissors, Star } from 'lucide-react';
import type { HypothesisTreeData } from '@/types';

interface HypothesisTreePanelProps {
  tree: HypothesisTreeData;
}

export function HypothesisTreePanel({ tree }: HypothesisTreePanelProps) {
  const branches = tree.branches ?? [];
  const pruned = tree.pruned_branches ?? [];
  const selectedId = tree.selected_branch_id;

  if (branches.length === 0) return null;

  return (
    <div className="mb-5 p-4 rounded-lg border border-dark-700 bg-dark-800/30">
      <h2 className="text-sm font-semibold text-gray-300 mb-2 flex items-center gap-2">
        <GitBranch className="w-4 h-4 text-primary-400" />
        假设树 · BFTS 轻量剪枝
      </h2>

      {tree.iteration_summary && (
        <p className="text-xs text-gray-500 mb-3">{tree.iteration_summary}</p>
      )}

      <div className="space-y-2 mb-3">
        {branches.map((branch) => {
          const isSelected = branch.branch_id === selectedId;
          return (
            <div
              key={branch.branch_id}
              className={`p-3 rounded-lg border ${
                isSelected
                  ? 'border-amber-500/40 bg-amber-500/5'
                  : 'border-dark-700 bg-dark-900/40'
              }`}
            >
              <div className="flex items-start justify-between gap-2 mb-1.5">
                <div className="flex items-center gap-1.5 min-w-0">
                  {isSelected && <Star className="w-3 h-3 text-amber-400 shrink-0" />}
                  <span className="text-xs font-medium text-gray-200 line-clamp-2">
                    {branch.label || branch.hypothesis}
                  </span>
                </div>
                <span className="text-sm font-mono font-bold text-primary-300 shrink-0">
                  {branch.composite_score?.toFixed?.(1) ?? branch.composite_score}
                </span>
              </div>
              <div className="flex flex-wrap gap-2 text-[10px] text-gray-500">
                {branch.scores && Object.entries(branch.scores).map(([k, v]) => (
                  <span key={k} className="px-1.5 py-0.5 rounded bg-dark-800 border border-dark-700">
                    {k}: {Number(v).toFixed(1)}
                  </span>
                ))}
                {branch.supporting_fact_count != null && (
                  <span>证据 {branch.supporting_fact_count} 条</span>
                )}
                {branch.alignment_score != null && (
                  <span>对齐 {branch.alignment_score}%</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {pruned.length > 0 && (
        <div className="pt-2 border-t border-dark-700/80">
          <p className="text-[11px] text-gray-500 mb-1.5 flex items-center gap-1">
            <Scissors className="w-3 h-3" />
            已剪枝 {pruned.length} 条低分分支
          </p>
          <div className="flex flex-wrap gap-1.5">
            {pruned.slice(0, 6).map((p) => (
              <span
                key={p.branch_id}
                className="text-[10px] px-2 py-0.5 rounded bg-red-500/5 text-red-400/80 border border-red-500/10"
              >
                #{p.index + 1} · {p.composite_score?.toFixed?.(1)}
              </span>
            ))}
          </div>
        </div>
      )}

      {tree.evidence_coverage && (
        <div className="mt-3 text-[11px] text-gray-500">
          证据覆盖: 已验证 {String(tree.evidence_coverage.verified_fact_refs ?? 0)}/
          {String(tree.evidence_coverage.total_fact_refs ?? 0)} 条 fact
          {tree.evidence_coverage.has_data_evidence ? ' · 含数据证据' : ''}
        </div>
      )}
    </div>
  );
}
