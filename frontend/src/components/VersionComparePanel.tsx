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
    <div className="p-4 rounded-lg border border-bp-border bg-bp-panel/30">
      <h3 className="text-sm font-semibold text-bp-text mb-3 flex items-center gap-2">
        <GitCompare className="w-4 h-4 text-bp-purple" />
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
              className="p-3 rounded border border-bp-border/80 bg-bp-base/40"
            >
              <div className="flex flex-wrap items-center gap-2 mb-2 text-[11px]">
                <span className="text-bp-muted">{before.label || `R${before.round}`}</span>
                <span className="text-bp-muted">→</span>
                <span className="text-bp-text">{after.label || `R${after.round}`}</span>
                {scoreDelta != null && (
                  <span
                    className={`font-mono ${scoreDelta >= 0 ? 'text-bp-green' : 'text-danger-400'}`}
                  >
                    评审分 {scoreDelta >= 0 ? '+' : ''}{scoreDelta.toFixed(1)}
                  </span>
                )}
              </div>

              <div className="space-y-2 text-xs">
                <CompareRow label="假设" changed={hypo.changed} text={hypo.preview} />
                <CompareRow label="实验步骤" changed={steps.changed} text={steps.preview} />
                <EvidenceCompareRow before={before} after={after} />
                <div className="flex gap-4 text-[10px] text-bp-muted">
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
      <p className="text-[10px] text-bp-muted mb-0.5">
        {label}
        {changed && <span className="ml-1 text-bp-yellow">已变更</span>}
      </p>
      <p className={`text-bp-text line-clamp-3 ${changed ? 'border-l-2 border-bp-yellow/50 pl-2' : ''}`}>
        {text}
      </p>
    </div>
  );
}

function EvidenceCompareRow({ before, after }: { before: IterationSnapshot; after: IterationSnapshot }) {
  const countBefore = before.supporting_fact_count ?? 0;
  const countAfter = after.supporting_fact_count ?? 0;
  const changed =
    countBefore !== countAfter
    || before.evidence_level !== after.evidence_level
    || (before.verifiable_spec_summary || '') !== (after.verifiable_spec_summary || '');

  if (!changed && countAfter === 0 && !after.verifiable_spec_summary) return null;

  return (
    <div>
      <p className="text-[10px] text-bp-muted mb-0.5">
        证据 / 可验证 spec
        {changed && <span className="ml-1 text-bp-green">已变更</span>}
      </p>
      <p className="text-bp-muted text-[11px]">
        fact {countBefore}→{countAfter}
        {before.evidence_level || after.evidence_level
          ? ` · 等级 ${before.evidence_level || '—'}→${after.evidence_level || '—'}`
          : ''}
      </p>
      {after.verifiable_primary_metric && (
        <p className="text-bp-green/80 text-[10px] font-mono mt-0.5">
          主指标 {after.verifiable_primary_metric}
        </p>
      )}
    </div>
  );
}
