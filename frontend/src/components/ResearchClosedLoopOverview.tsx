import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Orbit, Play, Lightbulb, BookOpen, Database, GitBranch, Loader2, AlertTriangle,
  ChevronRight, FileText, FlaskConical,
} from 'lucide-react';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { ClosedLoopTimeline } from '@/components/ClosedLoopTimeline';
import { DiscoveryLoopPanel } from '@/components/DiscoveryLoopPanel';
import { EvidenceDiffPanel } from '@/components/EvidenceDiffPanel';
import { VersionComparePanel } from '@/components/VersionComparePanel';
import { VerifiableChecksPanel } from '@/components/VerifiableChecksPanel';
import { FeedbackHubPanel } from '@/components/FeedbackHubPanel';
import { pipelineService } from '@/services/pipelineService';
import hypothesisService, { type BackendHypothesis } from '@/services/hypothesisService';
import { navigateToProjectTab } from '@/lib/projectNavigation';
import { useNavigate } from 'react-router-dom';
import type {
  DiscoveryLoopData,
  PipelineRunExtraMetadata,
  PipelineRunResult,
  PipelineRunSummary,
  TeachingAutoRefinementData,
  QualityAcceptance,
} from '@/types';

interface ResearchClosedLoopOverviewProps {
  projectId: string;
  latestRunId?: string | null;
  revalidateKey?: number;
}

const FLOW_STEPS = [
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

  const qualityAcceptance = useMemo((): QualityAcceptance | null => {
    return extra?.quality_acceptance ?? null;
  }, [extra]);

  const versionSnapshots = useMemo(() => extra?.version_snapshots ?? [], [extra]);

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
    versionSnapshots.length >= 2;

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-gray-400">
        <Loader2 className="w-8 h-8 animate-spin mb-3" />
        <span className="text-sm">正在加载科研闭环数据...</span>
      </div>
    );
  }

  if (error) {
    return (
      <Card className="border-red-500/30 bg-red-500/5">
        <div className="flex flex-col items-center py-8 text-center">
          <AlertTriangle className="w-10 h-10 text-red-400 mb-3" />
          <p className="text-red-300 text-sm mb-4">{error}</p>
          <Button variant="secondary" onClick={loadRuns}>重试</Button>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card
        title="科研闭环总览"
        subtitle="问题理解 → 知识整合 → 假设生成 → 证据梳理 → 研究计划 → 反馈修正"
      >
        <div className="flex flex-wrap items-center gap-2 mb-6">
          {FLOW_STEPS.map((step, idx) => {
            const status = stageStatus(runDetail, step.key);
            const color =
              status === 'completed'
                ? 'border-green-500/40 bg-green-500/10 text-green-300'
                : status === 'failed'
                  ? 'border-red-500/40 bg-red-500/10 text-red-300'
                  : status === 'running'
                    ? 'border-blue-500/40 bg-blue-500/10 text-blue-300'
                    : 'border-dark-600 bg-dark-800/50 text-gray-400';

            return (
              <div key={step.key} className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => navigateToProjectTab(navigate, projectId, step.tab)}
                  className={`px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors hover:opacity-90 ${color}`}
                >
                  {step.label}
                </button>
                {idx < FLOW_STEPS.length - 1 && (
                  <ChevronRight className="w-3.5 h-3.5 text-gray-600 shrink-0" />
                )}
              </div>
            );
          })}
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3 text-sm">
            {runs.length > 0 ? (
              <label className="flex items-center gap-2 text-gray-400">
                <Orbit className="w-4 h-4 text-primary-400" />
                运行记录
                <select
                  value={selectedRunId || ''}
                  onChange={(e) => setSelectedRunId(e.target.value || null)}
                  className="px-2 py-1 bg-dark-800 border border-dark-600 rounded text-gray-200 text-xs"
                >
                  {runs.map((r) => (
                    <option key={r.run_id || r.id} value={r.run_id || r.id}>
                      {(r.run_id || r.id).slice(0, 8)} · {r.status} · {new Date(r.created_at).toLocaleDateString('zh-CN')}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <span className="text-gray-500 text-sm">尚未运行 Pipeline</span>
            )}
            {runDetail && (
              <span className="text-xs text-gray-500">
                状态：{runDetail.status}
                {runDetail.failed_stage ? ` · 失败阶段 ${runDetail.failed_stage}` : ''}
              </span>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
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
            <p className="text-gray-200 leading-relaxed">{primaryHypothesis.hypothesis}</p>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 text-xs">
              <Metric label="文献 fact" value={String(primaryHypothesis.supporting_fact_ids?.length ?? 0)} />
              <Metric label="数据字段引用" value={String(primaryHypothesis.dataset_field_refs?.length ?? 0)} />
              <Metric label="证据级别" value={primaryHypothesis.evidence_level || '—'} />
              <Metric label="验证目标" value={primaryHypothesis.validation_target || '—'} />
            </div>
            {primaryHypothesis.rationale && (
              <p className="text-gray-400 text-xs border-t border-dark-700 pt-3">
                依据：{primaryHypothesis.rationale}
              </p>
            )}
            <div className="flex flex-wrap gap-2 pt-1">
              <QuickLink
                icon={BookOpen}
                label="文献库"
                onClick={() => navigateToProjectTab(navigate, projectId, 'literature')}
              />
              <QuickLink
                icon={Database}
                label="数据集"
                onClick={() => navigateToProjectTab(navigate, projectId, 'datasets')}
              />
              <QuickLink
                icon={FlaskConical}
                label="实验设计"
                onClick={() => navigateToProjectTab(navigate, projectId, 'experiments')}
              />
              <QuickLink
                icon={FileText}
                label="研究报告"
                onClick={() => navigateToProjectTab(navigate, projectId, 'reports')}
              />
            </div>
          </div>
        </Card>
      )}

      {!runDetail && runs.length === 0 && (
        <Card className="border-dashed border-dark-600">
          <div className="text-center py-10">
            <Orbit className="w-10 h-10 text-gray-600 mx-auto mb-3" />
            <p className="text-gray-300 mb-2">尚无闭环迭代记录</p>
            <p className="text-gray-500 text-sm mb-4">
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

      {(extra?.closed_loop_events?.length
        || extra?.quality_trend?.length
        || extra?.closed_loop_decisions?.length) ? (
        <ClosedLoopTimeline
          events={extra?.closed_loop_events}
          qualityTrend={extra?.quality_trend}
          decisions={extra?.closed_loop_decisions}
          runId={selectedRunId}
        />
      ) : null}

      <DiscoveryLoopPanel
        discoveryLoop={discoveryLoopData}
        teachingRefinement={teachingRefinementData}
        qualityAcceptance={qualityAcceptance}
      />

      {versionSnapshots.length >= 2 && (
        <>
          <VersionComparePanel snapshots={versionSnapshots} />
          <EvidenceDiffPanel snapshots={versionSnapshots} />
        </>
      )}

      {verifiableValidation && (
        <VerifiableChecksPanel
          checks={verifiableValidation.checks}
          passed={verifiableValidation.passed ?? null}
          spec={verifiableValidation.spec}
        />
      )}

      {!hasClosedLoopData && runDetail && (
        <Card className="border-dark-600 bg-dark-800/20">
          <p className="text-sm text-gray-400 text-center py-4">
            当前运行为单轮模式。启用 Discovery 或 Teaching 自动闭环后，将在此展示多轮迭代与版本对比。
          </p>
        </Card>
      )}

      <FeedbackHubPanel projectId={projectId} />
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="p-3 rounded-lg bg-dark-800/50 border border-dark-700">
      <div className="text-gray-500 mb-1">{label}</div>
      <div className="text-gray-200 font-medium truncate" title={value}>{value}</div>
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
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs text-primary-400 border border-primary-500/20 bg-primary-500/5 hover:bg-primary-500/10 transition-colors"
    >
      <Icon className="w-3.5 h-3.5" />
      {label}
    </button>
  );
}
