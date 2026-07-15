import { useMemo, useState } from 'react';
import { cn } from '@/lib/utils';
import type { IterationRecordMock } from '@/types/iterativeExperiment';
import env from '@/config/env';

const ASSESSMENT_LABEL: Record<string, string> = {
  success: '达标',
  promising: '有希望',
  needs_adjustment: '需调整',
  significant_issue: '存在显著问题',
};

function chartSrc(chart: { url?: string; path?: string; name?: string }): string {
  if (chart.url?.startsWith('http')) return chart.url;
  if (chart.url?.startsWith('/')) {
    const base = (env.API_BASE_URL || '').replace(/\/$/, '');
    return base ? `${base}${chart.url}` : chart.url;
  }
  const rel = (chart.path || chart.name || '').replace(/^\/+/, '');
  const path = `/api/v1/iterative-experiments/charts/${rel}`;
  const base = (env.API_BASE_URL || '').replace(/\/$/, '');
  return base ? `${base}${path}` : path;
}

function metricEntries(metrics: Record<string, number | string> | undefined) {
  if (!metrics) return [];
  const skip = new Set([
    'iteration', 'sample_size', 'dosage', 'frequency', 'run_scope',
    'dataset_rows', 'dataset_columns', 'n_splits', 'group_split_method',
  ]);
  return Object.entries(metrics).filter(([k, v]) => {
    if (skip.has(k)) return false;
    return typeof v === 'number' || (typeof v === 'string' && v.trim() !== '');
  });
}

interface IterationTimelineProps {
  iterations: IterationRecordMock[];
}

export function IterationTimeline({ iterations }: IterationTimelineProps) {
  const ordered = useMemo(
    () => [...iterations].sort((a, b) => b.iteration_number - a.iteration_number),
    [iterations],
  );

  if (!iterations.length) {
    return <p className="text-sm text-bp-muted">暂无迭代记录</p>;
  }

  return (
    <div className="space-y-4">
      <h5 className="text-sm font-medium text-bp-text">迭代历史</h5>
      {ordered.map((it) => (
        <IterationCard key={it.iteration_number} iteration={it} />
      ))}
    </div>
  );
}

function IterationCard({ iteration: it }: { iteration: IterationRecordMock }) {
  const [openSection, setOpenSection] = useState<'analysis' | 'decision' | 'plan' | 'log' | null>(
    'analysis',
  );
  const charts = it.result?.charts || [];
  const metrics = metricEntries(it.metrics || it.result?.metrics);
  const analysis = it.analysis || {};
  const decision = it.decision || { continue: true };
  const assessment = analysis.overall_assessment || '';
  const willContinue = decision.continue ?? decision.should_continue ?? true;

  return (
    <div className="rounded-lg border border-bp-border p-3 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <span className="font-semibold text-bp-text">第 {it.iteration_number} 轮</span>
        <span className="text-bp-muted truncate max-w-[240px]" title={it.plan?.title}>
          {it.plan?.title}
        </span>
        <span
          className={cn(
            it.status === 'success' && 'text-bp-green',
            it.status === 'failed' && 'text-danger-300',
            it.status === 'partial' && 'text-bp-yellow',
          )}
        >
          {it.status === 'success' ? '成功' : it.status === 'failed' ? '失败' : '部分成功'}
        </span>
        <span className="text-bp-muted">{Number(it.duration_seconds || 0).toFixed(1)}s</span>
      </div>

      {it.result?.summary && (
        <p className="text-xs text-bp-muted leading-relaxed">{it.result.summary}</p>
      )}

      {/* 图表 — 对齐 shaxiang 可视化结果 */}
      {charts.length > 0 && (
        <div>
          <div className="text-xs font-medium text-bp-text mb-2">可视化结果</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {charts.map((c) => (
              <figure key={c.path || c.name} className="rounded-lg border border-bp-border overflow-hidden bg-bp-base">
                <img
                  src={chartSrc(c)}
                  alt={c.name}
                  className="w-full h-auto object-contain bg-white"
                  loading="lazy"
                />
                <figcaption className="px-2 py-1.5 text-[11px] text-bp-muted leading-snug">
                  <div className="text-bp-text font-medium truncate">{c.name}</div>
                  {c.note && <div className="mt-0.5">{c.note}</div>}
                </figcaption>
              </figure>
            ))}
          </div>
        </div>
      )}

      {/* 核心指标 */}
      {metrics.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {metrics.slice(0, 9).map(([k, v]) => (
            <div key={k} className="rounded-lg border border-bp-border/80 px-2 py-1.5">
              <div className="text-[10px] text-bp-muted truncate" title={k}>
                {k.replace(/_/g, ' ')}
              </div>
              <div className="text-sm font-mono text-bp-text">
                {typeof v === 'number' ? v.toFixed(4) : String(v)}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 分析报告 */}
      <details
        open={openSection === 'analysis'}
        className="rounded-lg border border-bp-border/80 px-3 py-2"
        onToggle={(e) => {
          if ((e.target as HTMLDetailsElement).open) setOpenSection('analysis');
        }}
      >
        <summary className="text-xs font-medium text-bp-text cursor-pointer">分析报告</summary>
        <div className="mt-2 space-y-2 text-xs text-bp-muted leading-relaxed">
          {assessment && (
            <p>
              <span className="text-bp-text">整体评估：</span>
              {ASSESSMENT_LABEL[assessment] || assessment}
            </p>
          )}
          {analysis.summary && (
            <p>
              <span className="text-bp-text">摘要：</span>
              {analysis.summary}
            </p>
          )}
          {(analysis.visualization_notes || []).length > 0 && (
            <div>
              <div className="text-bp-text mb-1">可视化解读</div>
              <ul className="space-y-1 pl-3 list-disc">
                {analysis.visualization_notes!.map((n, i) => (
                  <li key={`${n.chart_name}-${i}`}>
                    {n.chart_name ? <strong className="text-bp-text">{n.chart_name}：</strong> : null}
                    {n.description}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {(analysis.findings || []).length > 0 && (
            <ListBlock title="关键发现" items={analysis.findings!} />
          )}
          {(analysis.identified_issues || []).length > 0 && (
            <ListBlock title="识别的问题" items={analysis.identified_issues!} tone="warn" />
          )}
          {(analysis.strengths || []).length > 0 && (
            <ListBlock title="优势" items={analysis.strengths!} />
          )}
          {(analysis.suggested_adjustments || []).length > 0 && (
            <ListBlock title="建议调整" items={analysis.suggested_adjustments!} tone="hint" />
          )}
        </div>
      </details>

      {/* 下轮迭代方向 */}
      <details
        open={openSection === 'decision'}
        className="rounded-lg border border-bp-cyan/30 bg-bp-cyan-tint/20 px-3 py-2"
        onToggle={(e) => {
          if ((e.target as HTMLDetailsElement).open) setOpenSection('decision');
        }}
      >
        <summary className="text-xs font-medium text-bp-cyan cursor-pointer">
          迭代决策 / 下轮方向
        </summary>
        <div className="mt-2 space-y-2 text-xs text-bp-muted leading-relaxed">
          <p>
            <span className="text-bp-text">继续迭代：</span>
            {willContinue ? '是' : '否'}
          </p>
          {decision.expected_improvement && (
            <p>
              <span className="text-bp-text">预期改进：</span>
              {decision.expected_improvement}
            </p>
          )}
          {decision.reason && (
            <p>
              <span className="text-bp-text">决策理由：</span>
              {decision.reason}
            </p>
          )}
          {(decision.focus_areas || []).length > 0 && (
            <ListBlock title="重点关注" items={decision.focus_areas!} />
          )}
          {(decision.next_plan_adjustments || []).length > 0 && (
            <ListBlock title="方案调整方向" items={decision.next_plan_adjustments!} tone="hint" />
          )}
          {(analysis.suggested_adjustments || []).length > 0 && !(decision.next_plan_adjustments || []).length && (
            <ListBlock title="建议的下一步" items={analysis.suggested_adjustments!} tone="hint" />
          )}
        </div>
      </details>

      {it.plan?.methodology && (
        <details className="rounded-lg border border-bp-border/80 px-3 py-2">
          <summary className="text-xs font-medium text-bp-text cursor-pointer">实验方案</summary>
          <div className="mt-2 text-xs text-bp-muted space-y-1">
            {it.plan.description && <p>{it.plan.description}</p>}
            <p>{it.plan.methodology}</p>
            {(it.plan.success_criteria || []).length > 0 && (
              <ListBlock title="成功标准" items={it.plan.success_criteria!} />
            )}
          </div>
        </details>
      )}

      {it.result?.script_log && (
        <details className="rounded-lg border border-bp-border/80 px-3 py-2">
          <summary className="text-xs font-medium text-bp-text cursor-pointer">执行日志</summary>
          <pre className="mt-2 text-[11px] text-bp-muted overflow-x-auto max-h-40 bg-bp-base p-2 rounded whitespace-pre-wrap">
            {it.result.script_log}
          </pre>
        </details>
      )}

      {it.error_message && (
        <p className="text-xs text-danger-300">错误：{it.error_message}</p>
      )}
    </div>
  );
}

function ListBlock({
  title,
  items,
  tone,
}: {
  title: string;
  items: string[];
  tone?: 'warn' | 'hint';
}) {
  return (
    <div>
      <div className="text-bp-text mb-1">{title}</div>
      <ul className="space-y-1 pl-3 list-disc">
        {items.map((item) => (
          <li
            key={item.slice(0, 48)}
            className={cn(
              tone === 'warn' && 'text-bp-yellow',
              tone === 'hint' && 'text-bp-cyan/90',
            )}
          >
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}
