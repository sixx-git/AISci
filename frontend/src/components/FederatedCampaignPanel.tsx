import { FlaskConical, ShieldAlert, CheckCircle2, RefreshCw, Target, TrendingUp } from 'lucide-react';
import { FederatedPareto3DPanel, type Pareto3DData } from '@/components/FederatedPareto3DPanel';
import type { ClosedLoopEvent, IterationSnapshot, ReplanAction } from '@/types';

export interface ParetoPoint {
  method?: string;
  accuracy?: number;
  communication_cost?: number;
  privacy_risk?: number;
  simulated?: boolean;
}

export interface ParetoFrontier {
  points?: ParetoPoint[];
  frontier?: ParetoPoint[];
  best_tradeoff_method?: string;
}

interface FederatedCampaignRefinement {
  round?: number;
  reasons?: string[];
  reran?: boolean;
  improved?: boolean;
  improvement?: { summary?: string; accuracy_delta?: number };
  pilot_before_mode?: string;
  pilot_after_mode?: string;
}

interface FederatedCampaignPanelProps {
  federatedPilot?: Record<string, unknown> | null;
  replanActions?: ReplanAction[];
  events?: ClosedLoopEvent[];
  snapshots?: IterationSnapshot[];
  campaignRefinement?: FederatedCampaignRefinement | null;
}

function pickPilot(data: FederatedCampaignPanelProps): Record<string, unknown> | null {
  if (data.federatedPilot && Object.keys(data.federatedPilot).length > 0) {
    return data.federatedPilot;
  }
  const evt = (data.events || []).find((e) => e.type === 'federated_campaign');
  if (evt) {
    return {
      execution_mode: evt.execution_mode,
      best_method: evt.best_method,
      alignment_gate: evt.gate_passed != null ? { passed: evt.gate_passed } : undefined,
      replan_actions: evt.replan_actions,
    };
  }
  return null;
}

function ParetoChart({ pareto }: { pareto: ParetoFrontier }) {
  const points = pareto.points || [];
  const frontierMethods = new Set((pareto.frontier || []).map((p) => p.method));
  if (points.length === 0) return null;

  const maxAcc = Math.max(...points.map((p) => p.accuracy ?? 0), 0.01);
  const maxComm = Math.max(...points.map((p) => p.communication_cost ?? 0), 1);

  return (
    <div className="mb-4">
      <p className="text-[11px] text-gray-500 mb-2 flex items-center gap-1">
        <TrendingUp className="w-3 h-3" />
        精度—通信 Pareto 前沿
        {pareto.best_tradeoff_method && (
          <span className="text-violet-400 ml-1">推荐: {pareto.best_tradeoff_method}</span>
        )}
      </p>
      <div className="space-y-1.5">
        {points.map((p) => {
          const accW = Math.round(((p.accuracy ?? 0) / maxAcc) * 100);
          const commW = Math.round(((p.communication_cost ?? 0) / maxComm) * 100);
          const onFrontier = frontierMethods.has(p.method);
          return (
            <div key={p.method} className="text-[10px]">
              <div className="flex justify-between text-gray-500 mb-0.5">
                <span className={onFrontier ? 'text-violet-300 font-medium' : ''}>{p.method}</span>
                <span>
                  acc={(p.accuracy ?? 0).toFixed(3)} · comm={p.communication_cost ?? 0}
                </span>
              </div>
              <div className="flex gap-1 h-2">
                <div
                  className="bg-green-500/40 rounded-l"
                  style={{ width: `${accW}%` }}
                  title={`accuracy ${p.accuracy}`}
                />
                <div
                  className="bg-amber-500/30 rounded-r flex-1 max-w-[40%]"
                  style={{ width: `${Math.max(8, commW * 0.4)}%` }}
                  title={`communication ${p.communication_cost}`}
                />
              </div>
            </div>
          );
        })}
      </div>
      <p className="text-[9px] text-gray-600 mt-1">绿=精度归一化 · 琥珀=通信成本（越低越好）</p>
    </div>
  );
}

export function FederatedCampaignPanel({
  federatedPilot,
  replanActions = [],
  events = [],
  snapshots = [],
  campaignRefinement,
}: FederatedCampaignPanelProps) {
  const pilot = pickPilot({ federatedPilot, events, snapshots, campaignRefinement });
  const actions =
    replanActions.length > 0
      ? replanActions
      : ((pilot?.replan_actions as ReplanAction[]) || []);

  const pareto = (federatedPilot?.pareto_frontier || pilot?.pareto_frontier) as ParetoFrontier | undefined;
  const pareto3d = (federatedPilot?.pareto_frontier_3d || pilot?.pareto_frontier_3d) as Pareto3DData | undefined;

  const refineEvt = (events || []).find((e) => e.type === 'federated_campaign_refine');

  if (!pilot && actions.length === 0 && snapshots.length === 0 && !campaignRefinement) {
    return null;
  }

  const mode = String(pilot?.execution_mode || '—');
  const best = String(pilot?.best_method || '—');
  const gate = pilot?.alignment_gate as { passed?: boolean; reason?: string } | undefined;
  const gatePassed = gate?.passed;

  return (
    <div className="mb-6 p-4 rounded-lg border border-violet-500/20 bg-violet-500/5">
      <h2 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
        <FlaskConical className="w-4 h-4 text-violet-400" />
        联邦 Campaign · 可验证迭代闭环
      </h2>

      {(campaignRefinement?.reran || refineEvt) && (
        <div className="mb-3 p-2 rounded border border-cyan-500/20 bg-cyan-500/5 text-[11px]">
          <span className="text-cyan-300 font-medium">
            自动 Campaign R{campaignRefinement?.round ?? refineEvt?.round ?? 2}
          </span>
          {campaignRefinement?.improvement?.summary && (
            <p className="text-gray-500 mt-0.5">{campaignRefinement.improvement.summary}</p>
          )}
          {(campaignRefinement?.reasons || (refineEvt?.reasons as string[])) && (
            <p className="text-gray-600 mt-0.5">
              触发：{(campaignRefinement?.reasons || (refineEvt?.reasons as string[]) || []).join('；')}
            </p>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4 text-xs">
        <div className="p-2 rounded border border-dark-700 bg-dark-900/40">
          <span className="text-gray-500">Pilot 模式</span>
          <p className="text-white font-mono mt-0.5">{mode}</p>
          {(federatedPilot?.runtime_engine as string) && (
            <p className="text-[10px] text-cyan-500/80 mt-0.5">
              engine: {String(federatedPilot?.runtime_engine)}
            </p>
          )}
        </div>
        <div className="p-2 rounded border border-dark-700 bg-dark-900/40">
          <span className="text-gray-500">当前最优方法</span>
          <p className="text-violet-300 font-mono mt-0.5">{best}</p>
        </div>
        <div className="p-2 rounded border border-dark-700 bg-dark-900/40">
          <span className="text-gray-500">VFL 对齐 Gate</span>
          <p className="mt-0.5 flex items-center gap-1">
            {gate == null ? (
              <span className="text-gray-500">—</span>
            ) : gatePassed ? (
              <>
                <CheckCircle2 className="w-3.5 h-3.5 text-green-400" />
                <span className="text-green-400">通过</span>
              </>
            ) : (
              <>
                <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
                <span className="text-amber-400">未通过</span>
              </>
            )}
          </p>
        </div>
      </div>

      {pareto3d?.points && pareto3d.points.length > 0 && (
        <FederatedPareto3DPanel data={pareto3d} />
      )}

      {pareto?.points && pareto.points.length > 0 && <ParetoChart pareto={pareto} />}

      {actions.length > 0 && (
        <div className="mb-4">
          <p className="text-[11px] text-gray-500 mb-2 flex items-center gap-1">
            <Target className="w-3 h-3" />
            结构化 Replan Actions（含 expected_check，可验收）
          </p>
          <div className="space-y-2">
            {actions.slice(0, 6).map((act, idx) => (
              <div
                key={act.action_id || idx}
                className="p-2 rounded border border-dark-700/80 bg-dark-900/40 text-[11px]"
              >
                <div className="flex flex-wrap items-center gap-2 mb-1">
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] ${
                      act.priority === 'critical'
                        ? 'bg-red-500/10 text-red-400'
                        : act.priority === 'high'
                          ? 'bg-amber-500/10 text-amber-400'
                          : 'bg-gray-500/10 text-gray-400'
                    }`}
                  >
                    {act.priority || 'medium'}
                  </span>
                  <span className="font-mono text-violet-300">{act.action_id}</span>
                  <span className="text-gray-400">
                    {act.parameter} → {String(act.to_value ?? '—')}
                  </span>
                </div>
                <p className="text-gray-500">
                  <span className="text-gray-400">验收：</span>
                  {act.expected_check}
                </p>
                {act.rationale && (
                  <p className="text-gray-600 mt-0.5">{act.rationale}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {snapshots.length > 0 && (
        <div>
          <p className="text-[11px] text-gray-500 mb-2 flex items-center gap-1">
            <RefreshCw className="w-3 h-3" />
            Campaign 快照
          </p>
          <div className="flex flex-wrap gap-2">
            {snapshots.slice(-6).map((snap, idx) => (
              <div
                key={`${snap.label}-${idx}`}
                className="px-2 py-1.5 rounded border border-dark-700 bg-dark-900/30 text-[10px] max-w-xs"
              >
                <span className="text-violet-300 font-medium">{snap.label || `R${snap.round}`}</span>
                {snap.federated_best_method && (
                  <span className="text-gray-500 ml-2">best={snap.federated_best_method}</span>
                )}
                {snap.federated_execution_mode && (
                  <span className="text-gray-600 ml-1">({snap.federated_execution_mode})</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
