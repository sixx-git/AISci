import { GitCompare } from 'lucide-react';
import type { IterationSnapshot } from '@/types';

interface VersionComparePanelProps {
  snapshots: IterationSnapshot[];
  title?: string;
}

function diffHighlight(before?: string, after?: string): { changed: boolean; preview: string } {
  const b = (before || '').trim();
  const a = (after || '').trim();
  return {
    changed: b !== a && Boolean(b || a),
    preview: a || b || '—',
  };
}

export function VersionComparePanel({ snapshots, title = '假设 / 计划版本对比' }: VersionComparePanelProps) {
  if (snapshots.length < 2) return null;

  const pairs: Array<{ before: IterationSnapshot; after: IterationSnapshot }> = [];
  for (let i = 1; i < snapshots.length; i += 1) {
    pairs.push({ before: snapshots[i - 1], after: snapshots[i] });
  }

  return (
    <div className="p-4 rounded-lg border border-dark-700 bg-dark-800/30">
      <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
        <GitCompare className="w-4 h-4 text-violet-400" />
        {title}
      </h3>

      <div className="space-y-4">
        {pairs.map(({ before, after }) => {
          const hypo = diffHighlight(before.hypothesis, after.hypothesis);
          const steps = diffHighlight(before.experimental_steps_preview, after.experimental_steps_preview);
          const scoreBefore = before.ensemble_overall;
          const scoreAfter = after.ensemble_overall;
          const scoreDelta =
            scoreBefore != null && scoreAfter != null
              ? Number(scoreAfter) - Number(scoreBefore)
              : null;

          return (
            <div
              key={`${before.label}-${after.label}`}
              className="p-3 rounded border border-dark-700/80 bg-dark-900/40"
            >
              <div className="flex flex-wrap items-center gap-2 mb-2 text-[11px]">
                <span className="text-gray-400">{before.label || `R${before.round}`}</span>
                <span className="text-gray-600">→</span>
                <span className="text-gray-300">{after.label || `R${after.round}`}</span>
                {scoreDelta != null && (
                  <span
                    className={`font-mono ${scoreDelta >= 0 ? 'text-green-400' : 'text-red-400'}`}
                  >
                    评审分 {scoreDelta >= 0 ? '+' : ''}{scoreDelta.toFixed(1)}
                  </span>
                )}
              </div>

              <div className="space-y-2 text-xs">
                <CompareRow label="假设" changed={hypo.changed} text={hypo.preview} />
                <CompareRow label="实验步骤" changed={steps.changed} text={steps.preview} />
                <div className="flex gap-4 text-[10px] text-gray-500">
                  <span>沙箱: {String(before.sandbox_success ?? '—')} → {String(after.sandbox_success ?? '—')}</span>
                  <span>决策: {before.ensemble_decision || '—'} → {after.ensemble_decision || '—'}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CompareRow({ label, changed, text }: { label: string; changed: boolean; text: string }) {
  return (
    <div>
      <p className="text-[10px] text-gray-500 mb-0.5">
        {label}
        {changed && <span className="ml-1 text-amber-400">已变更</span>}
      </p>
      <p className={`text-gray-300 line-clamp-3 ${changed ? 'border-l-2 border-amber-500/50 pl-2' : ''}`}>
        {text}
      </p>
    </div>
  );
}
