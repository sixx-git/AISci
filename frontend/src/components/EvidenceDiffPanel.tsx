import { GitBranch, FileText, Target } from 'lucide-react';
import type { IterationSnapshot } from '@/types';

interface EvidenceDiffPanelProps {
  snapshots: IterationSnapshot[];
  title?: string;
}

function diffFacts(before?: string[], after?: string[]) {
  const b = new Set(before || []);
  const a = new Set(after || []);
  const added = [...a].filter((id) => !b.has(id));
  const removed = [...b].filter((id) => !a.has(id));
  return { added, removed, delta: (after?.length ?? 0) - (before?.length ?? 0) };
}

export function EvidenceDiffPanel({
  snapshots,
  title = '证据与可验证 spec 迭代',
}: EvidenceDiffPanelProps) {
  if (snapshots.length < 2) return null;

  const pairs: Array<{ before: IterationSnapshot; after: IterationSnapshot }> = [];
  for (let i = 1; i < snapshots.length; i += 1) {
    pairs.push({ before: snapshots[i - 1], after: snapshots[i] });
  }

  return (
    <div className="p-4 rounded-lg border border-emerald-500/20 bg-emerald-500/5">
      <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
        <GitBranch className="w-4 h-4 text-emerald-400" />
        {title}
      </h3>

      <div className="space-y-3">
        {pairs.map(({ before, after }) => {
          const facts = diffFacts(
            before.supporting_fact_ids_sample,
            after.supporting_fact_ids_sample,
          );
          const levelChanged =
            before.evidence_level && after.evidence_level
              ? before.evidence_level !== after.evidence_level
              : false;
          const specChanged =
            (before.verifiable_spec_summary || '') !== (after.verifiable_spec_summary || '');

          return (
            <div
              key={`evidence-${before.label}-${after.label}`}
              className="p-3 rounded border border-dark-700/80 bg-dark-900/40 text-xs"
            >
              <div className="flex flex-wrap items-center gap-2 mb-2 text-[11px]">
                <span className="text-gray-400">{before.label || `R${before.round}`}</span>
                <span className="text-gray-600">→</span>
                <span className="text-gray-300">{after.label || `R${after.round}`}</span>
                {facts.delta !== 0 && (
                  <span className={facts.delta > 0 ? 'text-green-400' : 'text-red-400'}>
                    证据 {facts.delta > 0 ? '+' : ''}{facts.delta}
                  </span>
                )}
              </div>

              <div className="grid gap-2 sm:grid-cols-2 text-[11px]">
                <div>
                  <p className="text-gray-500 mb-1 flex items-center gap-1">
                    <FileText className="w-3 h-3" />
                    文献 fact
                  </p>
                  <p className="text-gray-300">
                    {before.supporting_fact_count ?? '—'} → {after.supporting_fact_count ?? '—'}
                  </p>
                  {facts.added.length > 0 && (
                    <p className="text-green-400/90 mt-1">+ {facts.added.join(', ')}</p>
                  )}
                  {facts.removed.length > 0 && (
                    <p className="text-red-400/80 mt-0.5">− {facts.removed.join(', ')}</p>
                  )}
                </div>
                <div>
                  <p className="text-gray-500 mb-1">证据等级</p>
                  <p className={levelChanged ? 'text-amber-300' : 'text-gray-300'}>
                    {before.evidence_level || '—'} → {after.evidence_level || '—'}
                    {levelChanged && <span className="ml-1 text-amber-400">已变更</span>}
                  </p>
                </div>
              </div>

              {(after.verifiable_primary_metric || specChanged) && (
                <div className="mt-2 pt-2 border-t border-dark-700/60">
                  <p className="text-gray-500 mb-1 flex items-center gap-1">
                    <Target className="w-3 h-3" />
                    可验证 spec
                  </p>
                  <p className="text-gray-400 line-clamp-2">
                    {after.verifiable_spec_summary || before.verifiable_spec_summary || '—'}
                  </p>
                  {after.verifiable_primary_metric && (
                    <p className="text-emerald-400/90 mt-1 font-mono text-[10px]">
                      主指标: {after.verifiable_primary_metric}
                    </p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
