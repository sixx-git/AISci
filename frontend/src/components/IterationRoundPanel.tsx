import {
  RefreshCw, AlertCircle, CheckCircle2, Search, Database, BookOpen, GitCompare,
} from 'lucide-react';
import type {
  IterationRoundRecord,
  MaterialSupplementPlan,
  ScienceIterationSession,
} from '@/types';

interface IterationRoundPanelProps {
  session: ScienceIterationSession | null;
  loading?: boolean;
  error?: string | null;
}

const TRIGGER_LABEL: Record<string, string> = {
  initial: '初始假设',
  evidence_weak: '证据不足',
  review_reject: '评审未通过',
  review_refine_complete: '评审精化完成',
  validation_fail: '验证失败',
  hypothesis_review: '假设评审',
};

function ScoreChip({ label, value, delta }: { label: string; value?: number | null; delta?: unknown }) {
  if (value == null) return null;
  const deltaNum = typeof delta === 'number' ? delta : null;
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded border border-bp-border bg-bp-panel text-xs">
      <span className="text-bp-muted">{label}</span>
      <span className="font-mono text-bp-text">{value.toFixed(1)}</span>
      {deltaNum != null && (
        <span className={`font-mono ${deltaNum >= 0 ? 'text-bp-green' : 'text-danger-400'}`}>
          ({deltaNum >= 0 ? '+' : ''}{deltaNum.toFixed(1)})
        </span>
      )}
    </span>
  );
}

function MaterialPlanBlock({ plan }: { plan?: MaterialSupplementPlan | null }) {
  if (!plan?.actions?.length && !plan?.suggested_queries?.length) return null;
  return (
    <div className="mt-2 p-2 rounded border border-bp-yellow/20 bg-bp-yellow/5 text-xs">
      <p className="text-bp-yellow font-medium mb-1 flex items-center gap-1">
        <Search className="w-3.5 h-3.5" />
        资料补充计划
      </p>
      {plan.triggers && plan.triggers.length > 0 && (
        <p className="text-bp-muted mb-1">触发: {plan.triggers.join(' · ')}</p>
      )}
      {plan.actions && plan.actions.length > 0 && (
        <ul className="space-y-1 mb-1">
          {plan.actions.map((a, i) => (
            <li key={i} className="flex items-start gap-1.5 text-bp-text">
              {a.action_type === 'literature_search' && <BookOpen className="w-3 h-3 mt-0.5 shrink-0" />}
              {a.action_type === 'data_gap_enrich' && <Database className="w-3 h-3 mt-0.5 shrink-0" />}
              {a.action_type === 'hypothesis_refine' && <RefreshCw className="w-3 h-3 mt-0.5 shrink-0" />}
              <span>{a.description}</span>
            </li>
          ))}
        </ul>
      )}
      {plan.suggested_queries && plan.suggested_queries.length > 0 && (
        <p className="text-bp-muted">建议检索: {plan.suggested_queries.slice(0, 3).join('；')}</p>
      )}
    </div>
  );
}

function RoundCard({ round }: { round: IterationRoundRecord }) {
  const triggerLabel = TRIGGER_LABEL[round.trigger || ''] || round.trigger || '—';
  const scores = round.scores || {};
  const delta = round.delta_from_prev || {};

  return (
    <div className="p-3 rounded-lg border border-bp-border bg-bp-panel/30">
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <span className="text-xs font-semibold text-bp-text">{round.label || `R${round.round}`}</span>
        <span className="text-xs px-1.5 py-0.5 rounded border border-bp-border text-bp-muted">
          {triggerLabel}
        </span>
      </div>
      {round.hypothesis_preview && (
        <p className="text-xs text-bp-text mb-2 line-clamp-2">{round.hypothesis_preview}</p>
      )}
      <div className="flex flex-wrap gap-1.5 mb-2">
        <ScoreChip label="评审" value={scores.ensemble_overall} delta={delta.ensemble_delta} />
        <ScoreChip label="假设树" value={scores.hypothesis_tree} delta={delta.tree_score_delta} />
        <ScoreChip label="CQS" value={scores.cqs} />
        <ScoreChip label="逻辑" value={scores.logic_score} />
      </div>
      {round.actions_taken && round.actions_taken.length > 0 && (
        <p className="text-xs text-bp-muted mb-1">
          动作: {round.actions_taken.join(' · ')}
        </p>
      )}
      <MaterialPlanBlock plan={round.material_plan} />
    </div>
  );
}

export function IterationRoundPanel({ session, loading, error }: IterationRoundPanelProps) {
  if (loading) {
    return <p className="text-sm text-bp-muted py-4 text-center">加载自迭代会话...</p>;
  }
  if (error) {
    return (
      <div className="p-3 rounded border border-danger-500/30 bg-danger-500/5 text-xs text-danger-300 flex items-center gap-2">
        <AlertCircle className="w-4 h-4 shrink-0" />
        {error}
      </div>
    );
  }
  if (!session?.rounds?.length) {
    return (
      <p className="text-sm text-bp-muted py-4 text-center">
        暂无自迭代轮次记录。启用 project.config.science_iteration 后，Pipeline 将自动记录里程碑。
      </p>
    );
  }

  const best = session.current_best || {};
  const plan = session.material_supplement_plan;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3 text-xs">
        {best.ensemble_decision && (
          <span className="flex items-center gap-1 text-bp-green">
            <CheckCircle2 className="w-3.5 h-3.5" />
            当前决策: {String(best.ensemble_decision)}
          </span>
        )}
        {session.config?.enabled === false && (
          <span className="text-bp-muted">自迭代已禁用</span>
        )}
        {session.config?.max_rounds != null && (
          <span className="text-bp-muted">最大轮次: {session.config.max_rounds}</span>
        )}
      </div>

      {plan && (plan.actions?.length || plan.suggested_queries?.length) ? (
        <MaterialPlanBlock plan={plan} />
      ) : null}

      <div className="space-y-3">
        {session.rounds.map((r, idx) => (
          <RoundCard key={`${r.round}-${r.label}-${idx}`} round={r} />
        ))}
      </div>

      {(session.version_snapshots?.length ?? 0) >= 2 && (
        <p className="text-xs text-bp-muted flex items-center gap-1">
          <GitCompare className="w-3.5 h-3.5" />
          共 {session.version_snapshots?.length} 个版本快照，可在下方「版本对比」面板查看 Diff
        </p>
      )}
    </div>
  );
}
