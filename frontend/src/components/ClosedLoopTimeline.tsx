import { TrendingUp, GitBranch, FlaskConical, ShieldCheck, Sparkles, Image, BookOpen, RefreshCw } from 'lucide-react';
import type { ClosedLoopEvent, QualityTrendEntry } from '@/types';

interface ClosedLoopTimelineProps {
  events?: ClosedLoopEvent[];
  qualityTrend?: QualityTrendEntry[];
}

const EVENT_LABELS: Record<string, string> = {
  hypothesis_tree: '假设树剪枝',
  hypothesis_tree_pilot: '假设树 Pilot 融合',
  ensemble_review: '集成评审',
  sandbox_validation: '沙箱验证',
  ideation_novelty: 'Ideation 新颖性',
  plot_vlm_critique: 'VLM 图表评审',
  discovery_refine: 'Discovery 迭代',
  discovery_literature_refresh: '文献刷新回退',
  teaching_auto_refinement: 'Teaching 自动闭环',
  quality_acceptance: '质量验收',
  federated_campaign: '联邦 Campaign Pilot',
  federated_campaign_refine: '联邦 Campaign 自动 R2',
  discovery_federated: 'Discovery 联邦双门槛',
};

const EVENT_ICONS: Record<string, typeof GitBranch> = {
  hypothesis_tree: GitBranch,
  ensemble_review: ShieldCheck,
  sandbox_validation: FlaskConical,
  ideation_novelty: Sparkles,
  plot_vlm_critique: Image,
  discovery_refine: TrendingUp,
  discovery_literature_refresh: BookOpen,
  federated_campaign: FlaskConical,
  federated_campaign_refine: RefreshCw,
};

function formatScore(score?: number): string {
  if (score == null || Number.isNaN(score)) return '—';
  return Number(score).toFixed(1);
}

export function ClosedLoopTimeline({ events = [], qualityTrend = [] }: ClosedLoopTimelineProps) {
  if (events.length === 0 && qualityTrend.length === 0) return null;

  return (
    <div className="mb-6 p-4 rounded-lg border border-dark-700 bg-dark-800/30">
      <h2 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
        <TrendingUp className="w-4 h-4 text-primary-400" />
        科研闭环 · 迭代质量趋势
      </h2>

      {qualityTrend.length > 0 && (
        <div className="mb-4">
          <p className="text-[11px] text-gray-500 mb-2">各阶段综合分（越高越好）</p>
          <div className="flex flex-wrap items-end gap-2">
            {qualityTrend.map((entry, idx) => {
              const score = entry.score ?? 0;
              const height = Math.max(8, Math.min(48, (score / 10) * 48));
              const label = entry.stage || entry.label || `R${entry.round ?? idx}`;
              return (
                <div key={`${label}-${idx}`} className="flex flex-col items-center gap-1 min-w-[52px]">
                  <span className="text-[10px] font-mono text-primary-300">{formatScore(score)}</span>
                  <div
                    className="w-8 rounded-t bg-primary-500/40 border border-primary-500/30"
                    style={{ height: `${height}px` }}
                    title={`${label}: ${formatScore(score)}`}
                  />
                  <span className="text-[9px] text-gray-500 text-center leading-tight max-w-[64px] truncate">
                    {label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {events.length > 0 && (
        <div className="space-y-2">
          <p className="text-[11px] text-gray-500">闭环事件</p>
          {events.slice(-6).reverse().map((evt, idx) => {
            const Icon = EVENT_ICONS[evt.type] || TrendingUp;
            const label = EVENT_LABELS[evt.type] || evt.type;
            return (
              <div
                key={`${evt.type}-${evt.at ?? idx}`}
                className="flex items-start gap-2 p-2 rounded border border-dark-700/80 bg-dark-900/40"
              >
                <Icon className="w-3.5 h-3.5 text-gray-500 shrink-0 mt-0.5" />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-medium text-gray-300">{label}</span>
                    {evt.at && (
                      <span className="text-[10px] text-gray-600">{String(evt.at).slice(0, 19)}</span>
                    )}
                    {evt.decision && (
                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded ${
                          evt.decision === 'Accept'
                            ? 'bg-green-500/10 text-green-400'
                            : 'bg-red-500/10 text-red-400'
                        }`}
                      >
                        {evt.decision}
                      </span>
                    )}
                    {evt.overall != null && (
                      <span className="text-[10px] font-mono text-amber-400">
                        综合 {formatScore(Number(evt.overall))}
                      </span>
                    )}
                  </div>
                  {evt.summary && (
                    <p className="text-[11px] text-gray-500 mt-0.5 line-clamp-2">{String(evt.summary)}</p>
                  )}
                  {evt.success != null && evt.type === 'sandbox_validation' && (
                    <p className="text-[11px] text-gray-500 mt-0.5">
                      沙箱执行: {evt.success ? '成功' : '失败'}
                      {evt.experiment_id ? ` · ${evt.experiment_id}` : ''}
                    </p>
                  )}
                  {evt.type === 'quality_acceptance' && evt.summary && (
                    <p className="text-[11px] text-gray-500 mt-0.5">{String(evt.summary)}</p>
                  )}
                  {evt.type === 'teaching_auto_refinement' && Array.isArray(evt.reasons) && (
                    <p className="text-[11px] text-gray-500 mt-0.5 line-clamp-2">
                      {(evt.reasons as string[]).join('；')}
                    </p>
                  )}
                  {evt.type === 'discovery_literature_refresh' && evt.new_facts != null && (
                    <p className="text-[11px] text-gray-500 mt-0.5">
                      文献刷新 +{String(evt.new_facts)} 条 fact
                      {evt.search_query ? ` · ${String(evt.search_query).slice(0, 60)}` : ''}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
