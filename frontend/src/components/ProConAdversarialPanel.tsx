import { Shield, Swords, Users, AlertTriangle } from 'lucide-react';
import type { ProConAdversarialData } from '@/types';

interface ProConAdversarialPanelProps {
  data: ProConAdversarialData;
}

const MODE_LABELS: Record<string, string> = {
  single_group: '单研究组（正方多智能体 + 反方轮流质疑）',
  multi_group: '多研究组（组间互为攻防）',
  off: '已关闭',
};

export function ProConAdversarialPanel({ data }: ProConAdversarialPanelProps) {
  const mode = data.mode || 'single_group';
  const proGroups = data.pro_side?.research_groups ?? [];
  const conRounds = data.con_side?.rounds ?? [];
  const crossAttacks = data.cross_group_attacks ?? [];
  const evolution = data.evolution ?? {};
  const survival = data.group_survival_scores ?? [];

  return (
    <div className="p-4 rounded-lg border border-bp-border bg-bp-panel/30 space-y-4">
      <h3 className="text-sm font-semibold text-bp-text flex items-center gap-2">
        <Swords className="w-4 h-4 text-bp-cyan" />
        红蓝对抗（正方 / 反方）
      </h3>
      <p className="text-xs text-bp-muted">{MODE_LABELS[mode] ?? mode}</p>

      <section>
        <h4 className="text-xs font-medium text-bp-cyan mb-2 flex items-center gap-1.5">
          <Users className="w-3.5 h-3.5" />
          正方 — 多智能体研究组
        </h4>
        {data.pro_side?.agents && (
          <p className="text-xs text-bp-muted mb-2">
            组成：{data.pro_side.agents.join(' · ')}
          </p>
        )}
        <div className="space-y-2">
          {proGroups.map((g) => (
            <div key={g.group_index} className="p-2.5 rounded border border-bp-border/60 bg-bp-base/40 text-xs">
              <p className="font-medium text-bp-text mb-1">研究组 {g.group_index}</p>
              <p className="text-bp-muted line-clamp-3">{g.hypothesis}</p>
              {(g.literature_anchors?.length ?? 0) > 0 && (
                <p className="text-bp-muted/80 mt-1">
                  文献锚点 {g.literature_anchors!.length} 条
                  {g.evidence_level ? ` · 证据等级 ${g.evidence_level}` : ''}
                </p>
              )}
            </div>
          ))}
        </div>
      </section>

      {mode === 'single_group' && conRounds.length > 0 && (
        <section>
          <h4 className="text-xs font-medium text-danger-400 mb-2 flex items-center gap-1.5">
            <Shield className="w-3.5 h-3.5" />
            反方 — 轻量质疑智能体（{conRounds.length} 轮）
          </h4>
          <div className="space-y-3">
            {conRounds.map((rnd) => (
              <div key={rnd.round} className="p-2.5 rounded border border-danger-400/20 bg-danger-400/5">
                <p className="text-xs text-bp-muted mb-1">
                  第 {rnd.round} 轮
                  {rnd.overall_threat_level ? ` · 威胁 ${rnd.overall_threat_level}` : ''}
                </p>
                {rnd.round_summary && <p className="text-xs text-bp-text mb-2">{rnd.round_summary}</p>}
                <ul className="space-y-1">
                  {(rnd.challenges ?? []).slice(0, 4).map((c, i) => (
                    <li key={i} className="text-xs text-bp-muted flex gap-1.5">
                      <AlertTriangle className="w-3 h-3 text-danger-400/70 shrink-0 mt-0.5" />
                      <span>
                        [{c.attack_type ?? '?'}] {c.statement}
                        {c.counter_evidence_fact_ids?.length
                          ? ` (${c.counter_evidence_fact_ids.join(', ')})`
                          : ''}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </section>
      )}

      {mode === 'multi_group' && crossAttacks.length > 0 && (
        <section>
          <h4 className="text-xs font-medium text-danger-400 mb-2">组间攻防</h4>
          {survival.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-2">
              {survival.map((score, i) => (
                <span key={i} className="text-xs px-2 py-0.5 rounded bg-bp-base border border-bp-border">
                  组 {i} 生存分 {Number(score).toFixed(1)}
                </span>
              ))}
            </div>
          )}
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {crossAttacks.slice(0, 6).map((atk, idx) => (
              <div key={idx} className="text-xs text-bp-muted p-2 rounded border border-bp-border/50">
                {atk.attacker_label ?? `组 ${atk.attacker_index}`} → 组 {atk.defender_index}
                {(atk.challenges ?? []).slice(0, 1).map((c, i) => (
                  <p key={i} className="mt-1 text-bp-text/80">{c.statement}</p>
                ))}
              </div>
            ))}
          </div>
        </section>
      )}

      {(evolution.revision_points?.length ?? 0) > 0 && (
        <section>
          <h4 className="text-xs font-medium text-bp-yellow mb-2">假设进化（正方回应反方）</h4>
          {evolution.evolved_rationale && (
            <p className="text-xs text-bp-muted mb-2">{evolution.evolved_rationale}</p>
          )}
          <ul className="space-y-1">
            {evolution.revision_points!.slice(0, 5).map((p, i) => (
              <li key={i} className="text-xs text-bp-muted">• {p}</li>
            ))}
          </ul>
          {evolution.hypothesis_patch && (
            <p className="text-xs text-bp-cyan mt-2">微调建议：{evolution.hypothesis_patch}</p>
          )}
        </section>
      )}
    </div>
  );
}
