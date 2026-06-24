import { useState } from 'react';
import { TrendingUp, GitBranch, FlaskConical, ShieldCheck, Sparkles, Image, BookOpen, RefreshCw, GitCommitHorizontal, Download } from 'lucide-react';
import type { ClosedLoopEvent, ClosedLoopDecision, QualityTrendEntry } from '@/types';
import { pipelineService } from '@/services/pipelineService';

interface ClosedLoopTimelineProps {
  events?: ClosedLoopEvent[];
  qualityTrend?: QualityTrendEntry[];
  decisions?: ClosedLoopDecision[];
  runId?: string | null;
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
  hitl_gate_pause: 'HITL Gate 暂停',
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

const DECISION_LABELS: Record<string, string> = {
  proceed_validation: '进入验证',
  block_validation: '阻断验证',
  discovery_refine: 'Discovery 迭代',
  stop_discovery: '停止迭代',
  skip_validation: '跳过验证',
};

export function ClosedLoopTimeline({ events = [], qualityTrend = [], decisions = [], runId }: ClosedLoopTimelineProps) {
  const [exporting, setExporting] = useState(false);

  const handleExportAudit = async () => {
    if (!runId || exporting) return;
    setExporting(true);
    try {
      const res = await pipelineService.exportAuditChain(runId);
      if (res.code === 200 && res.data) {
        const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `audit_${runId.slice(0, 8)}.json`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } finally {
      setExporting(false);
    }
  };

  if (events.length === 0 && qualityTrend.length === 0 && decisions.length === 0) return null;

  return (
    <div className="mb-6 p-4 rounded-lg border border-bp-border bg-bp-panel/30">
      <div className="flex items-center justify-between mb-3 gap-2">
        <h2 className="text-sm font-semibold text-bp-text flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-bp-cyan" />
          科研闭环 · 迭代质量趋势
        </h2>
        {runId && (
          <button
            type="button"
            onClick={handleExportAudit}
            disabled={exporting}
            className="flex items-center gap-1 text-[11px] text-bp-muted hover:text-bp-cyan disabled:opacity-50"
          >
            <Download className="w-3.5 h-3.5" />
            {exporting ? '导出中…' : '导出审计链'}
          </button>
        )}
      </div>

      {qualityTrend.length > 0 && (
        <div className="mb-4">
          <p className="text-[11px] text-bp-muted mb-2">综合质量分 CQS（0–100，越高越好）</p>
          <div className="flex flex-wrap items-end gap-2">
            {qualityTrend.map((entry, idx) => {
              const score = entry.cqs ?? entry.score ?? 0;
              const height = Math.max(8, Math.min(48, (score / 100) * 48));
              const label = entry.stage || entry.label || `R${entry.round ?? idx}`;
              const rawHint = entry.raw_score != null ? ` raw=${entry.raw_score}` : '';
              return (
                <div key={`${label}-${idx}`} className="flex flex-col items-center gap-1 min-w-[52px]">
                  <span className="text-[10px] font-mono text-bp-cyan">{formatScore(score)}</span>
                  <div
                    className="w-8 rounded-t bg-primary-500/40 border border-bp-cyan/30"
                    style={{ height: `${height}px` }}
                    title={`${label}: CQS ${formatScore(score)}${rawHint}`}
                  />
                  <span className="text-[9px] text-bp-muted text-center leading-tight max-w-[64px] truncate">
                    {label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {decisions.length > 0 && (
        <div className="mb-4 space-y-2">
          <p className="text-[11px] text-bp-muted flex items-center gap-1">
            <GitCommitHorizontal className="w-3 h-3" />
            闭环决策记录
          </p>
          {decisions.slice(-5).reverse().map((d, idx) => (
            <div
              key={`${d.trigger}-${d.at ?? idx}`}
              className="flex items-start gap-2 p-2 rounded border border-violet-500/20 bg-violet-500/5"
            >
              <GitCommitHorizontal className="w-3.5 h-3.5 text-violet-400 shrink-0 mt-0.5" />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-medium text-bp-text">{d.trigger}</span>
                  {d.action && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-bp-panel text-violet-300">
                      {DECISION_LABELS[d.action] || d.action}
                    </span>
                  )}
                  {d.round != null && (
                    <span className="text-[10px] text-bp-muted">R{d.round}</span>
                  )}
                </div>
                {d.reason && (
                  <p className="text-[11px] text-bp-muted mt-0.5 line-clamp-2">{d.reason}</p>
                )}
                {d.next_stage && (
                  <p className="text-[10px] text-bp-muted mt-0.5">下一步: {d.next_stage}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {events.length > 0 && (
        <div className="space-y-2">
          <p className="text-[11px] text-bp-muted">闭环事件</p>
          {events.slice(-6).reverse().map((evt, idx) => {
            const Icon = EVENT_ICONS[evt.type] || TrendingUp;
            const label = EVENT_LABELS[evt.type] || evt.type;
            return (
              <div
                key={`${evt.type}-${evt.at ?? idx}`}
                className="flex items-start gap-2 p-2 rounded border border-bp-border/80 bg-bp-base/40"
              >
                <Icon className="w-3.5 h-3.5 text-bp-muted shrink-0 mt-0.5" />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-medium text-bp-text">{label}</span>
                    {evt.at && (
                      <span className="text-[10px] text-bp-muted">{String(evt.at).slice(0, 19)}</span>
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
                    <p className="text-[11px] text-bp-muted mt-0.5 line-clamp-2">{String(evt.summary)}</p>
                  )}
                  {evt.success != null && evt.type === 'sandbox_validation' && (
                    <p className="text-[11px] text-bp-muted mt-0.5">
                      沙箱执行: {evt.success ? '成功' : '失败'}
                      {evt.experiment_id ? ` · ${evt.experiment_id}` : ''}
                    </p>
                  )}
                  {evt.type === 'quality_acceptance' && evt.summary && (
                    <p className="text-[11px] text-bp-muted mt-0.5">{String(evt.summary)}</p>
                  )}
                  {evt.type === 'teaching_auto_refinement' && Array.isArray(evt.reasons) && (
                    <p className="text-[11px] text-bp-muted mt-0.5 line-clamp-2">
                      {(evt.reasons as string[]).join('；')}
                    </p>
                  )}
                  {evt.type === 'discovery_literature_refresh' && evt.new_facts != null && (
                    <p className="text-[11px] text-bp-muted mt-0.5">
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
