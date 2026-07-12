import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Orbit, Play, Lightbulb, BookOpen, Database, GitBranch,
  ChevronRight, FileText, FlaskConical,
} from 'lucide-react';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { IterationHistoryPanel } from '@/components/IterationHistoryPanel';
import { VerifiableChecksPanel } from '@/components/VerifiableChecksPanel';
import { FeedbackHubPanel } from '@/components/FeedbackHubPanel';
import { CollapsiblePanel } from '@/components/workspace/CollapsiblePanel';
import { LoadingState } from '@/components/workspace/LoadingState';
import { ErrorState } from '@/components/workspace/ErrorState';
import { pipelineService } from '@/services/pipelineService';
import hypothesisService, { type BackendHypothesis } from '@/services/hypothesisService';
import { navigateToProjectTab } from '@/lib/projectNavigation';
import { useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
import type {
  DiscoveryLoopData,
  PipelineRunExtraMetadata,
  PipelineRunResult,
  PipelineRunSummary,
  TeachingAutoRefinementData,
} from '@/types';

interface ResearchClosedLoopOverviewProps {
  projectId: string;
  latestRunId?: string | null;
  revalidateKey?: number;
}

const PIPELINE_STAGES = [
  { key: 'problem_understanding', label: 'P0 问题理解', tab: 'questions' },
  { key: 'literature_mining', label: 'P1 文献挖掘', tab: 'literature' },
  { key: 'data_acquisition', label: 'P2 数据采集', tab: 'datasets' },
  { key: 'knowledge_gap', label: 'P3 知识缺口', tab: 'workflow' },
  { key: 'hypothesis_generation', label: 'P4 假设生成', tab: 'hypotheses' },
  { key: 'hypothesis_review', label: 'P5 假设评估', tab: 'hypotheses' },
  { key: 'experiment_design', label: 'P6 实验设计', tab: 'experiments' },
  { key: 'small_validation', label: 'P7 小样验证', tab: 'experiments' },
  { key: 'report_generation', label: 'P8 报告生成', tab: 'reports' },
] as const;

const MACRO_FLOW_STEPS = [
  { key: 'problem_understanding', label: '问题理解', tab: 'questions' },
  { key: 'literature_mining', label: '知识整合', tab: 'literature' },
  { key: 'hypothesis_generation', label: '假设生成', tab: 'hypotheses' },
  { key: 'hypothesis_review', label: '证据梳理', tab: 'hypotheses' },
  { key: 'experiment_design', label: '研究计划', tab: 'experiments' },
  { key: 'report_generation', label: '反馈修正', tab: 'workflow' },
] as const;

function stageStatus(
  run: PipelineRunResult | null,
  stageKey: string,
): 'pending' | 'completed' | 'failed' | 'running' {
  if (!run) return 'pending';
  if (run.status === 'running') return 'running';
  const stage = run.stages?.find((s) => s.stage === stageKey);
  if (stage?.status === 'completed') return 'completed';
  if (stage?.status === 'failed' || run.failed_stage === stageKey) return 'failed';
  if (run.status === 'completed') return 'completed';
  return 'pending';
}

const STEP_STATUS_CLASS: Record<string, string> = {
  completed: 'border-bp-green/40 bg-bp-green/10 text-bp-green',
  failed: 'border-danger-500/40 bg-danger-500/10 text-danger-300',
  running: 'border-bp-cyan/40 bg-bp-cyan-tint text-bp-cyan',
  pending: 'border-bp-border bg-bp-panel/50 text-bp-muted',
};

const RUN_STATUS_LABEL: Record<string, string> = {
  completed: '已完成',
  running: '运行中',
  failed: '失败',
  pending: '等待中',
};

export function ResearchClosedLoopOverview({
  projectId,
  latestRunId,
  revalidateKey = 0,
}: ResearchClosedLoopOverviewProps) {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<PipelineRunSummary[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [runDetail, setRunDetail] = useState<PipelineRunResult | null>(null);
  const [hypotheses, setHypotheses] = useState<BackendHypothesis[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [flowView, setFlowView] = useState<'micro' | 'macro'>('micro');

  const loadRuns = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [runsRes, hypoRes] = await Promise.all([
        pipelineService.getRuns(projectId),
        hypothesisService.getProjectHypotheses(projectId),
      ]);

      const runList = runsRes.code === 200 && Array.isArray(runsRes.data)
        ? [...runsRes.data].sort(
            (a, b) => new Date(b.created_at || '').getTime() - new Date(a.created_at || '').getTime(),
          )
        : [];

      setRuns(runList);
      setHypotheses(hypoRes.code === 200 && Array.isArray(hypoRes.data) ? hypoRes.data : []);

      const preferred =
        latestRunId ||
        runList[0]?.run_id ||
        runList[0]?.id ||
        null;
      setSelectedRunId(preferred);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '加载闭环数据失败');
    } finally {
      setLoading(false);
    }
  }, [projectId, latestRunId]);

  useEffect(() => {
    loadRuns();
  }, [loadRuns, revalidateKey]);

  useEffect(() => {
    if (!selectedRunId) {
      setRunDetail(null);
      return;
    }

    let cancelled = false;

    pipelineService.getStatus(selectedRunId).then((res) => {
      if (cancelled) return;
      if (res.code === 200 && res.data) {
        setRunDetail(res.data);
      } else {
        setRunDetail(null);
      }
    }).catch(() => {
      if (!cancelled) setRunDetail(null);
    });

    return () => { cancelled = true; };
  }, [selectedRunId, revalidateKey]);

  const extra = runDetail?.extra_metadata as PipelineRunExtraMetadata | undefined;

  const discoveryLoopData = useMemo((): DiscoveryLoopData | null => {
    const aux = extra?.auxiliary_results?.discovery_loop as DiscoveryLoopData | undefined;
    return aux?.history?.length || aux?.version_snapshots?.length ? aux : null;
  }, [extra]);

  const teachingRefinementData = useMemo((): TeachingAutoRefinementData | null => {
    const aux = extra?.auxiliary_results?.teaching_auto_refinement as TeachingAutoRefinementData | undefined;
    return aux?.reran ? aux : null;
  }, [extra]);

  const federatedPilot = useMemo(() => {
    const sv = runDetail?.small_validation as Record<string, unknown> | undefined;
    if (sv?.federated_pilot) return sv.federated_pilot as Record<string, unknown>;
    const stage = runDetail?.stages?.find((s) => s.stage === 'small_validation');
    const out = stage?.output_data as Record<string, unknown> | undefined;
    return (out?.federated_pilot as Record<string, unknown> | undefined) ?? null;
  }, [runDetail]);

  const iterationMode =
    (extra?.run_options?.iteration_mode as string | undefined)
    || (extra?.iteration_mode as string | undefined)
    || 'human';
  const iterationModeLabel: Record<string, string> = {
    human: '人工主导',
    teaching_auto: '轻量自动',
    discovery_auto: 'Discovery 自动',
  };

  const verifiableValidation = useMemo(() => {
    const validationOut = runDetail?.small_validation as Record<string, unknown> | undefined;
    if (!validationOut) {
      const stage = runDetail?.stages?.find((s) => s.stage === 'small_validation');
      const out = stage?.output_data as Record<string, unknown> | undefined;
      if (!out) return null;
      return {
        checks: out.verifiable_checks as import('@/types').VerifiableCheck[] | undefined,
        passed: out.verifiable_passed as boolean | null | undefined,
        spec: out.verifiable_hypothesis as { claim?: string; primary_metric?: string } | undefined,
      };
    }
    return {
      checks: validationOut.verifiable_checks as import('@/types').VerifiableCheck[] | undefined,
      passed: validationOut.verifiable_passed as boolean | null | undefined,
      spec: validationOut.verifiable_hypothesis as { claim?: string; primary_metric?: string } | undefined,
    };
  }, [runDetail]);

  const primaryHypothesis = hypotheses.find((h) => h.is_primary) || hypotheses[0];
  const hasClosedLoopData =
    Boolean(extra?.closed_loop_events?.length) ||
    Boolean(extra?.quality_trend?.length) ||
    Boolean(discoveryLoopData) ||
    Boolean(teachingRefinementData) ||
    Boolean(extra?.version_snapshots?.length) ||
    Boolean(extra?.science_iteration?.rounds?.length);

  if (loading) {
    return <LoadingState message="正在加载科研闭环数据..." />;
  }

  if (error) {
    return (
      <Card className="border-danger-500/30 bg-danger-500/5">
        <ErrorState message={error} onRetry={loadRuns} compact />
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card
        title="科研闭环总览"
        subtitle="九阶段 Pipeline · Discovery / Teaching 双模式 · CQS 质量趋势"
      >
        <div className="mb-4 p-3 rounded-bp border border-bp-cyan/20 bg-bp-cyan-tint/40 text-xs text-bp-muted leading-relaxed">
          <strong className="text-bp-text">人工主导</strong>：关键阶段 HITL 门控 + 单阶段重跑（推荐）。
          <span className="mx-2 text-bp-border">|</span>
          <strong className="text-bp-text">轻量自动</strong>：验证失败时最多 1 轮自动精化。
          <span className="mx-2 text-bp-border">|</span>
          <strong className="text-bp-text">Discovery 自动</strong>：未 Accept 时多轮文献回退与假设→实验→报告迭代。
          <span className="ml-2 text-bp-cyan">
            当前：{iterationModeLabel[iterationMode] || iterationMode}
          </span>
        </div>

        <div className="flex items-center justify-between gap-2 mb-3">
          <p className="text-xs text-bp-muted">流程视图</p>
          <div className="flex rounded-bp border border-bp-border overflow-hidden text-xs">
            <button
              type="button"
              onClick={() => setFlowView('micro')}
              className={cn(
                'px-2 py-1',
                flowView === 'micro' ? 'bg-bp-cyan-tint text-bp-cyan' : 'text-bp-muted',
              )}
            >
              9 阶段
            </button>
            <button
              type="button"
              onClick={() => setFlowView('macro')}
              className={cn(
                'px-2 py-1 border-l border-bp-border',
                flowView === 'macro' ? 'bg-bp-cyan-tint text-bp-cyan' : 'text-bp-muted',
              )}
            >
              6 步宏观
            </button>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 mb-6">
          {(flowView === 'micro' ? PIPELINE_STAGES : MACRO_FLOW_STEPS).map((step, idx, arr) => {
            const status = stageStatus(runDetail, step.key);
            return (
              <div key={step.key} className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => navigateToProjectTab(navigate, projectId, step.tab)}
                  className={cn(
                    'px-3 py-1.5 rounded-bp border text-xs font-medium transition-colors hover:opacity-90',
                    STEP_STATUS_CLASS[status],
                  )}
                >
                  {step.label}
                </button>
                {idx < arr.length - 1 && (
                  <ChevronRight className="w-3.5 h-3.5 text-bp-muted shrink-0" />
                )}
              </div>
            );
          })}
        </div>

        <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4 p-4 rounded-bp bg-bp-panel/30 border border-bp-cyan-dim">
          <div className="flex flex-col sm:flex-row sm:flex-wrap sm:items-center gap-3 min-w-0">
            {runs.length > 0 ? (
              <label className="flex flex-col sm:flex-row sm:items-center gap-2 text-sm text-bp-muted">
                <span className="inline-flex items-center gap-2 shrink-0">
                  <Orbit className="w-4 h-4 text-bp-cyan" />
                  运行记录
                </span>
                <select
                  value={selectedRunId || ''}
                  onChange={(e) => setSelectedRunId(e.target.value || null)}
                  className="input-field py-1.5 text-xs min-w-[200px]"
                >
                  {runs.map((r) => {
                    const id = r.run_id || r.id;
                    const label = RUN_STATUS_LABEL[r.status] ?? r.status;
                    return (
                      <option key={id} value={id}>
                        {id.slice(0, 8)}… · {label} · {new Date(r.created_at).toLocaleDateString('zh-CN')}
                      </option>
                    );
                  })}
                </select>
              </label>
            ) : (
              <span className="text-bp-muted text-sm">尚未运行 Pipeline</span>
            )}
            {runDetail && (
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className={cn(
                  'px-2 py-0.5 rounded-bp border',
                  STEP_STATUS_CLASS[runDetail.status] ?? STEP_STATUS_CLASS.pending,
                )}>
                  {RUN_STATUS_LABEL[runDetail.status] ?? runDetail.status}
                </span>
                {runDetail.failed_stage && (
                  <span className="text-danger-300">失败阶段：{runDetail.failed_stage}</span>
                )}
                {runDetail.total_duration != null && (
                  <span className="text-bp-muted font-mono">
                    耗时 {runDetail.total_duration.toFixed(1)}s
                  </span>
                )}
              </div>
            )}
          </div>
          <div className="flex flex-wrap gap-2 shrink-0">
            <Button
              size="sm"
              variant="secondary"
              icon={<GitBranch className="w-4 h-4" />}
              onClick={() => navigateToProjectTab(navigate, projectId, 'workflow')}
            >
              运行 / 重跑 Pipeline
            </Button>
            <Button
              size="sm"
              variant="secondary"
              icon={<Lightbulb className="w-4 h-4" />}
              onClick={() => navigateToProjectTab(navigate, projectId, 'hypotheses')}
            >
              查看假设
            </Button>
          </div>
        </div>
      </Card>

      {primaryHypothesis && (
        <Card title="当前主假设与依据" subtitle="假设来源、证据引用与验证目标">
          <div className="space-y-3 text-sm">
            <p className="text-bp-text leading-relaxed">{primaryHypothesis.hypothesis}</p>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Metric label="文献 fact" value={String(primaryHypothesis.supporting_fact_ids?.length ?? 0)} />
              <Metric label="数据字段引用" value={String(primaryHypothesis.dataset_field_refs?.length ?? 0)} />
              <Metric label="证据级别" value={primaryHypothesis.evidence_level || '—'} />
              <Metric label="验证目标" value={primaryHypothesis.validation_target || '—'} />
            </div>
            {primaryHypothesis.rationale && (
              <p className="text-bp-muted text-xs border-t border-bp-cyan-dim pt-3">
                依据：{primaryHypothesis.rationale}
              </p>
            )}
            <div className="flex flex-wrap gap-2 pt-1">
              <QuickLink icon={BookOpen} label="文献库" onClick={() => navigateToProjectTab(navigate, projectId, 'literature')} />
              <QuickLink icon={Database} label="数据集" onClick={() => navigateToProjectTab(navigate, projectId, 'datasets')} />
              <QuickLink icon={FlaskConical} label="实验设计" onClick={() => navigateToProjectTab(navigate, projectId, 'experiments')} />
              <QuickLink icon={FileText} label="研究报告" onClick={() => navigateToProjectTab(navigate, projectId, 'reports')} />
            </div>
          </div>
        </Card>
      )}

      {!runDetail && runs.length === 0 && (
        <Card className="border-dashed border-bp-border">
          <div className="text-center py-10">
            <Orbit className="w-10 h-10 text-bp-muted mx-auto mb-3" />
            <p className="text-bp-text mb-2">尚无闭环迭代记录</p>
            <p className="text-bp-muted text-sm mb-4">
              运行 Pipeline 后，此处将展示 Discovery 多轮、证据 Diff、版本对比与质量验收
            </p>
            <Button
              icon={<Play className="w-4 h-4" />}
              onClick={() => navigateToProjectTab(navigate, projectId, 'workflow')}
            >
              前往工作流运行
            </Button>
          </div>
        </Card>
      )}

      {runDetail && (
        <CollapsiblePanel title="迭代历史" subtitle="里程碑 · 时间线 · 版本对比 · 拓扑" defaultOpen>
          <IterationHistoryPanel
            runId={selectedRunId}
            extraMetadata={extra}
            federatedPilot={federatedPilot}
          />
        </CollapsiblePanel>
      )}

      {verifiableValidation && (
        <CollapsiblePanel title="可验证性检查" subtitle="VerifiableChecksPanel" defaultOpen={false}>
          <VerifiableChecksPanel
            checks={verifiableValidation.checks}
            passed={verifiableValidation.passed ?? null}
            spec={verifiableValidation.spec}
          />
        </CollapsiblePanel>
      )}

      {!hasClosedLoopData && runDetail && (
        <Card className="border-bp-border bg-bp-panel/20">
          <p className="text-sm text-bp-muted text-center py-4">
            当前运行为单轮模式。启用 Discovery 或 Teaching 自动闭环后，将在此展示多轮迭代与版本对比。
          </p>
        </Card>
      )}

      <CollapsiblePanel title="反馈中心" subtitle="FeedbackHubPanel" defaultOpen={false}>
        <FeedbackHubPanel
          projectId={projectId}
          latestRunId={selectedRunId}
          onRerunStarted={loadRuns}
        />
      </CollapsiblePanel>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="bp-metric-box text-center !items-stretch">
      <div className="text-bp-metric font-bold text-bp-cyan truncate" title={value}>{value}</div>
      <div className="text-bp-muted text-xs">{label}</div>
    </div>
  );
}

function QuickLink({
  icon: Icon,
  label,
  onClick,
}: {
  icon: typeof BookOpen;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-bp text-xs text-bp-cyan border border-bp-cyan/20 bg-bp-cyan-tint hover-accent-bottom transition-colors"
    >
      <Icon className="w-3.5 h-3.5" />
      {label}
    </button>
  );
}
