import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { EmptyState } from '@/components/EmptyState';
import { LoadingState } from '@/components/workspace/LoadingState';
import { ErrorState } from '@/components/workspace/ErrorState';
import {
  FlaskConical, CheckCircle, XCircle, Database,
  BarChart3, ListChecks, Target, BookOpen,
  AlertTriangle, Lightbulb, Play,
  Sparkles, Upload,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import experimentService from '@/services/experimentService';
import { pipelineService } from '@/services/pipelineService';
import humanLoopService from '@/services/humanLoopService';
import { useToast } from '@/hooks/useToast';
import { getErrorMessage } from '@/lib/errors';
import { activeRunKey, activeRunStatusKey } from '@/lib/storageKeys';
import {
  categoryColor,
  categoryLabel,
  mapBackendExperimentDesignToDetailed,
} from '@/lib/mappers/experimentDesignMapper';
import { selectedHypothesisKey } from '@/lib/storageKeys';
import { navigateToProjectTab } from '@/lib/projectNavigation';
import { AdversarialReviewSummary } from '@/components/AdversarialReviewSummary';
import { useHypothesisReviewExtras } from '@/hooks/useHypothesisReviewExtras';
import type { DetailedExperimentDesign, PipelineRunResult } from '@/types';

interface ExperimentDataRequirements {
  upload_status?: string;
  uploaded_dataset_count?: number;
  uploaded_datasets?: Array<{
    filename?: string;
    data_type?: string;
    n_rows?: number;
    n_columns?: number;
    columns?: string[];
  }>;
  required_data_description?: string;
  validation_target?: string;
  metrics?: string;
  recommended_public_datasets?: string[];
  gaps?: string[];
  summary?: string;
  next_action?: string;
}

function extractDataRequirements(run: PipelineRunResult | null | undefined): ExperimentDataRequirements | null {
  const raw = run?.experiment_design?.data_requirements;
  if (!raw || typeof raw !== 'object') return null;
  return raw as ExperimentDataRequirements;
}

interface ExperimentDesignPageProps {
  projectId?: string;
  projectMode?: string;
  compact?: boolean;
  revalidateKey?: number;
  latestRunId?: string | null;
  selectedHypothesisId?: string | null;
}

async function resolvePipelineRunId(
  projectId: string,
  latestRunId?: string | null,
): Promise<string | null> {
  try {
    const res = await pipelineService.getRuns(projectId);
    if (res.code === 200 && res.data?.length) {
      const completed = res.data.find((r) => r.status === 'completed');
      if (completed?.run_id) return completed.run_id;
    }
  } catch {
    /* ignore */
  }
  if (latestRunId) return latestRunId;
  try {
    const saved = localStorage.getItem(activeRunKey(projectId));
    if (saved) return saved;
  } catch {
    /* ignore */
  }
  const res = await pipelineService.getRuns(projectId);
  if (res.code === 200 && res.data?.length) {
    return res.data[0].run_id;
  }
  return null;
}

function rememberActiveRun(projectId: string, runId: string) {
  try {
    localStorage.setItem(activeRunKey(projectId), runId);
    localStorage.setItem(activeRunStatusKey(projectId), 'running');
  } catch {
    /* ignore */
  }
}

async function pollPipelineUntilDone(runId: string): Promise<'completed' | 'failed' | 'timeout'> {
  for (let i = 0; i < 120; i += 1) {
    await new Promise((resolve) => setTimeout(resolve, 3000));
    try {
      const res = await pipelineService.getStatus(runId);
      if (res.code !== 200 || !res.data) continue;
      const status = res.data.status;
      if (status === 'completed') return 'completed';
      if (status === 'failed') return 'failed';
    } catch {
      /* keep polling */
    }
  }
  return 'timeout';
}

function DataRequirementsPanel({
  requirements,
  onUploadClick,
  onRegenerate,
  regenerating,
}: {
  requirements: ExperimentDataRequirements;
  onUploadClick: () => void;
  onRegenerate: () => void;
  regenerating?: boolean;
}) {
  const pending = requirements.upload_status === 'pending_upload'
    || (requirements.uploaded_dataset_count ?? 0) === 0;
  const uploaded = requirements.uploaded_datasets ?? [];

  return (
    <Card className={cn(
      'mb-6 border',
      pending ? 'border-bp-yellow/40 bg-bp-yellow/5' : 'border-bp-green/30 bg-bp-green/5',
    )}>
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <Database className={cn('w-5 h-5 shrink-0', pending ? 'text-bp-yellow' : 'text-bp-green')} />
          <div>
            <h3 className="text-sm font-semibold text-bp-text">数据需求与上传状态</h3>
            <p className="text-xs text-bp-muted mt-0.5">
              {requirements.summary || (pending
                ? '请先在「数据集」页上传研究数据，再重跑实验设计。'
                : '已结合上传数据生成实验方案。')}
            </p>
          </div>
        </div>
        <span className={cn(
          'text-xs px-2 py-1 rounded-full border font-medium',
          pending
            ? 'text-bp-yellow border-bp-yellow/40 bg-bp-yellow/10'
            : 'text-bp-green border-bp-green/30 bg-bp-green/10',
        )}>
          {pending ? '待上传数据' : `已上传 ${requirements.uploaded_dataset_count ?? uploaded.length} 个数据集`}
        </span>
      </div>

      {requirements.required_data_description && (
        <div className="mt-4 p-3 rounded-lg bg-bp-base/60 border border-bp-border">
          <p className="text-xs text-bp-muted mb-1">所需数据</p>
          <p className="text-sm text-bp-text whitespace-pre-wrap">{requirements.required_data_description}</p>
        </div>
      )}

      {(requirements.validation_target || requirements.metrics) && (
        <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
          {requirements.validation_target && (
            <div>
              <span className="text-xs text-bp-muted">验证目标</span>
              <p className="text-bp-text mt-0.5">{requirements.validation_target}</p>
            </div>
          )}
          {requirements.metrics && (
            <div>
              <span className="text-xs text-bp-muted">评估指标</span>
              <p className="text-bp-text mt-0.5">{requirements.metrics}</p>
            </div>
          )}
        </div>
      )}

      {Array.isArray(requirements.gaps) && requirements.gaps.length > 0 && (
        <div className="mt-3">
          <p className="text-xs text-bp-muted mb-1.5">数据缺口</p>
          <ul className="text-sm text-bp-text space-y-1 list-disc list-inside">
            {requirements.gaps.map((gap) => (
              <li key={gap}>{gap}</li>
            ))}
          </ul>
        </div>
      )}

      {uploaded.length > 0 && (
        <div className="mt-4 overflow-x-auto">
          <p className="text-xs text-bp-muted mb-2">已上传数据集</p>
          <table className="w-full text-xs text-left">
            <thead>
              <tr className="text-bp-muted border-b border-bp-border">
                <th className="py-1.5 pr-3 font-medium">文件名</th>
                <th className="py-1.5 pr-3 font-medium">类型</th>
                <th className="py-1.5 pr-3 font-medium">规模</th>
                <th className="py-1.5 font-medium">列（节选）</th>
              </tr>
            </thead>
            <tbody>
              {uploaded.map((ds) => (
                <tr key={ds.filename || JSON.stringify(ds)} className="border-b border-bp-border/50">
                  <td className="py-1.5 pr-3 text-bp-text">{ds.filename || '—'}</td>
                  <td className="py-1.5 pr-3 text-bp-muted">{ds.data_type || '—'}</td>
                  <td className="py-1.5 pr-3 text-bp-muted">
                    {ds.n_rows != null && ds.n_columns != null
                      ? `${ds.n_rows} × ${ds.n_columns}`
                      : '—'}
                  </td>
                  <td className="py-1.5 text-bp-muted truncate max-w-[200px]">
                    {(ds.columns ?? []).slice(0, 6).join(', ') || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        <Button variant="secondary" size="sm" icon={<Upload className="w-4 h-4" />} onClick={onUploadClick}>
          前往数据集页上传
        </Button>
        {pending && (
          <Button
            variant="primary"
            size="sm"
            icon={<Sparkles className="w-4 h-4" />}
            onClick={onRegenerate}
            isLoading={regenerating}
          >
            上传后重跑实验设计
          </Button>
        )}
      </div>
    </Card>
  );
}

function VerifiabilityChecklist({ exp }: { exp: DetailedExperimentDesign }) {
  const items = [
    { label: '是否有数据集', ok: !!(exp.sourceDataset && exp.targetDataset) },
    { label: '是否有基线方法', ok: exp.baselines.length > 0 },
    { label: '是否有评估指标', ok: exp.metrics.length > 0 },
    { label: '是否有实验步骤', ok: exp.steps.length > 0 },
    { label: '是否有预期结果', ok: !!exp.expectedResults },
  ];

  const allOk = items.every((i) => i.ok);

  return (
    <Card>
      <div className="flex items-center gap-2 mb-4">
        <ListChecks className="w-4 h-4 text-bp-cyan" />
        <h3 className="text-sm font-semibold text-bp-text">可验证性检查</h3>
      </div>
      <div className="space-y-2">
        {items.map((item) => (
          <div key={item.label} className="flex items-center gap-2 text-sm">
            {item.ok ? (
              <CheckCircle className="w-4 h-4 text-bp-green shrink-0" />
            ) : (
              <XCircle className="w-4 h-4 text-danger-400 shrink-0" />
            )}
            <span className={item.ok ? 'text-bp-text' : 'text-danger-300'}>
              {item.label}
            </span>
          </div>
        ))}
      </div>
      <div className={cn(
        'mt-4 p-2.5 rounded-lg text-xs text-center font-medium',
        allOk ? 'bg-bp-green/10 text-bp-green border border-bp-green/20' :
        'bg-danger-500/10 text-danger-400 border border-danger-500/20',
      )}>
        {allOk ? '✓ 实验方案可验证' : '✗ 实验方案不完整'}
      </div>
    </Card>
  );
}

function FlExperimentPlanSidebar({ experiment }: { experiment: DetailedExperimentDesign }) {
  return (
    <Card className="p-4 border-bp-cyan/20 bg-bp-cyan/5">
      <h3 className="text-sm font-semibold text-bp-cyan mb-3">联邦实验计划</h3>
      <div className="space-y-3 text-xs">
        <div>
          <p className="text-bp-muted mb-1">Baselines</p>
          <div className="flex flex-wrap gap-1">
            {experiment.baselines.map((b) => (
              <span key={b.name} className="px-1.5 py-0.5 rounded bg-bp-panel text-bp-text border border-bp-border">
                {b.name}
              </span>
            ))}
          </div>
        </div>
        <div>
          <p className="text-bp-muted mb-1">Metrics</p>
          <div className="flex flex-wrap gap-1">
            {experiment.metrics.map((m) => (
              <span key={m.name} className="px-1.5 py-0.5 rounded bg-bp-panel text-bp-text border border-bp-border">
                {m.name}
              </span>
            ))}
          </div>
        </div>
      </div>
      <p className="text-xs text-bp-muted mt-3 leading-relaxed">
        隐私机制建议：DP、Secure Aggregation、PSI（垂直联邦）— 详见 Pipeline 生成的 federated_plan
      </p>
    </Card>
  );
}

function PrimaryHypothesisActions({
  onGenerate,
  onSmallValidation,
  onOpenWorkflow,
  generatingDesign,
  runningValidation,
}: {
  onGenerate: () => void;
  onSmallValidation: () => void;
  onOpenWorkflow: () => void;
  generatingDesign?: boolean;
  runningValidation?: boolean;
}) {
  const busy = generatingDesign || runningValidation;
  return (
    <Card>
      <h4 className="text-sm font-semibold text-bp-text mb-3 flex items-center gap-2">
        <Lightbulb className="w-4 h-4 text-bp-yellow" />
        Primary Hypothesis Actions
      </h4>
      <div className="flex flex-col gap-2">
        <Button
          variant="primary"
          size="sm"
          icon={<Sparkles className="w-4 h-4" />}
          onClick={onGenerate}
          isLoading={generatingDesign}
          disabled={busy && !generatingDesign}
        >
          生成实验设计
        </Button>
        <Button
          variant="secondary"
          size="sm"
          icon={<Play className="w-4 h-4" />}
          onClick={onSmallValidation}
          isLoading={runningValidation}
          disabled={busy && !runningValidation}
        >
          运行小样验证
        </Button>
        {(generatingDesign || runningValidation) && (
          <Button variant="secondary" size="sm" onClick={onOpenWorkflow}>
            在工作流查看进度
          </Button>
        )}
      </div>
    </Card>
  );
}

export function ExperimentDesignPage({
  projectId: _projectId,
  projectMode,
  compact: _compact = false,
  revalidateKey: _revalidateKey,
  latestRunId: _latestRunId,
  selectedHypothesisId: _selectedHypothesisId,
}: ExperimentDesignPageProps) {
  const navigate = useNavigate();
  const { message: alertMsg, showAlert } = useToast();
  const [experiment, setExperiment] = useState<DetailedExperimentDesign | null>(null);
  const [dataRequirements, setDataRequirements] = useState<ExperimentDataRequirements | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadTick, setReloadTick] = useState(0);
  const [generatingDesign, setGeneratingDesign] = useState(false);
  const [runningValidation, setRunningValidation] = useState(false);

  const { proCon: proConAdversarial, loading: reviewExtrasLoading } = useHypothesisReviewExtras(
    _projectId,
    _latestRunId,
    _revalidateKey,
  );

  const selectedHypothesisId = _selectedHypothesisId
    || (() => {
      try { return _projectId ? localStorage.getItem(selectedHypothesisKey(_projectId)) : null; }
      catch { return null; }
    })();

  useEffect(() => {
    if (!_projectId) {
      setLoading(false);
      setError('未提供项目 ID');
      return;
    }

    setLoading(true);
    setError(null);

    const loadExperiment = experimentService.getProjectExperimentDesigns(_projectId)
      .then((res) => {
        if (res.code === 200 && Array.isArray(res.data) && res.data.length > 0) {
          setExperiment(mapBackendExperimentDesignToDetailed(res.data[0]));
        } else {
          setExperiment(null);
        }
      })
      .catch((err) => {
        setError(getErrorMessage(err, '获取实验设计失败，请检查后端服务是否启动'));
        setExperiment(null);
      });

    const loadDataRequirements = resolvePipelineRunId(_projectId, _latestRunId)
      .then(async (runId) => {
        if (!runId) {
          setDataRequirements(null);
          return;
        }
        const res = await pipelineService.getStatus(runId);
        if (res.code === 200 && res.data) {
          setDataRequirements(extractDataRequirements(res.data));
        } else {
          setDataRequirements(null);
        }
      })
      .catch(() => setDataRequirements(null));

    Promise.all([loadExperiment, loadDataRequirements]).finally(() => setLoading(false));
  }, [_projectId, _revalidateKey, _latestRunId, reloadTick]);

  const handleOpenDatasets = useCallback(() => {
    if (_projectId) {
      navigateToProjectTab(navigate, _projectId, 'datasets');
    }
  }, [_projectId, navigate]);

  const handleOpenWorkflow = useCallback(() => {
    if (_projectId) {
      navigate(`/projects/${_projectId}?tab=workflow`);
    }
  }, [_projectId, navigate]);

  const runPipelineStage = useCallback(async (stage: 'experiment_design' | 'small_validation') => {
    if (!_projectId) {
      showAlert('缺少项目 ID');
      return;
    }
    const setBusy = stage === 'experiment_design' ? setGeneratingDesign : setRunningValidation;
    setBusy(true);
    try {
      const parentRunId = await resolvePipelineRunId(_projectId, _latestRunId);
      if (!parentRunId) {
        showAlert('未找到 Pipeline 运行记录，请先到工作流页运行一次 Pipeline');
        return;
      }
      const label = stage === 'experiment_design' ? '实验设计' : '小样验证';
      showAlert(`正在启动「${label}」阶段…`);
      const res = await humanLoopService.rerunFromStage({
        project_id: _projectId,
        run_id: parentRunId,
        stage,
        use_human_modified_output: true,
        rerun_mode: 'single_stage',
      });
      if (res.code !== 200 || !res.data?.run_id) {
        showAlert(res.message || `${label}启动失败`);
        return;
      }
      const newRunId = res.data.run_id;
      rememberActiveRun(_projectId, newRunId);
      showAlert(`${label}已在后台运行，可在工作流页查看进度`);
      const outcome = await pollPipelineUntilDone(newRunId);
      if (outcome === 'completed') {
        showAlert(`${label}已完成，页面数据已刷新`);
        setReloadTick((t) => t + 1);
      } else if (outcome === 'failed') {
        showAlert(`${label}执行失败，请在工作流页查看错误详情`);
      } else {
        showAlert(`${label}仍在运行，请稍后在工作流页查看结果`);
      }
    } catch (err) {
      showAlert(getErrorMessage(err, stage === 'experiment_design' ? '生成实验设计失败' : '运行小样验证失败'));
    } finally {
      setBusy(false);
    }
  }, [_projectId, _latestRunId, showAlert]);

  const handleGenerate = useCallback(() => {
    void runPipelineStage('experiment_design');
  }, [runPipelineStage]);

  const handleSmallValidation = useCallback(() => {
    void runPipelineStage('small_validation');
  }, [runPipelineStage]);

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-bp-text mb-2">实验设计</h1>
        <p className="text-bp-muted">
          为选定科学假设生成可执行、可复现的验证方案；请先在工作流完成假设评估，上传数据集后再运行实验设计
          {projectMode === 'federated_learning' && (
            <span className="ml-2 text-bp-cyan text-sm">· 联邦学习模式</span>
          )}
        </p>
      </div>

      {alertMsg && (
        <div className="mb-4 px-4 py-2.5 rounded-lg bg-bp-cyan-tint border border-bp-cyan/20 text-sm text-bp-cyan animate-pulse">
          {alertMsg}
        </div>
      )}

      {!reviewExtrasLoading && proConAdversarial && _projectId && (
        <div className="mb-4">
          <AdversarialReviewSummary
            data={proConAdversarial}
            onViewDetail={() => navigateToProjectTab(navigate, _projectId, 'hypotheses')}
          />
        </div>
      )}

      {!loading && dataRequirements && _projectId && (
        <DataRequirementsPanel
          requirements={dataRequirements}
          onUploadClick={handleOpenDatasets}
          onRegenerate={handleGenerate}
          regenerating={generatingDesign}
        />
      )}

      {loading && (
        <Card>
          <LoadingState message="正在加载实验设计..." />
        </Card>
      )}

      {!loading && error && (
        <Card>
          <ErrorState
            title="加载实验设计失败"
            message={error}
            onRetry={() => setReloadTick((t) => t + 1)}
          />
        </Card>
      )}

      {!loading && !error && !experiment && (
        <Card>
          <EmptyState
            icon={selectedHypothesisId
              ? <Lightbulb className="w-8 h-8 text-bp-yellow" />
              : <AlertTriangle className="w-8 h-8 text-bp-yellow" />}
            title={selectedHypothesisId ? '当前主假设尚未生成实验设计' : '暂无实验设计'}
            description={selectedHypothesisId
              ? '请在工作流完成假设评估；在「数据集」页上传 CSV 后运行实验设计阶段。'
              : '请先在候选假设页面选择一个主假设，完成评估并上传数据集后运行实验设计。'}
            action={{ label: '前往工作流', onClick: handleGenerate }}
          />
        </Card>
      )}

      {experiment && (
        <>
          <div className="mb-6">
            <Card className="flex items-center gap-2 p-4">
              <Lightbulb className="w-5 h-5 text-bp-yellow shrink-0" />
              <div>
                <span className="text-xs text-bp-muted">当前主假设</span>
                <p className="text-sm text-bp-text font-medium mt-0.5">{experiment.hypothesisTitle}</p>
              </div>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            <div className="lg:col-span-3 space-y-5">

              <Card>
                <div className="flex items-center gap-2 mb-4">
                  <Target className="w-4 h-4 text-bp-cyan" />
                  <div>
                    <h3 className="text-sm font-semibold text-bp-text">实验目标</h3>
                    <p className="text-xs text-bp-muted">Objective</p>
                  </div>
                </div>
                <p className="text-sm text-bp-text leading-relaxed">{experiment.objective}</p>
              </Card>

              <Card>
                <div className="flex items-center gap-2 mb-4">
                  <FlaskConical className="w-4 h-4 text-bp-purple" />
                  <div>
                    <h3 className="text-sm font-semibold text-bp-text">实验方法</h3>
                    <p className="text-xs text-bp-muted">Methods</p>
                  </div>
                </div>
                <p className="text-sm text-bp-text leading-relaxed">{experiment.methods}</p>
              </Card>

              <Card>
                <div className="flex items-center gap-2 mb-4">
                  <Database className="w-4 h-4 text-bp-green" />
                  <div>
                    <h3 className="text-sm font-semibold text-bp-text">数据集</h3>
                    <p className="text-xs text-bp-muted">Datasets</p>
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-3 bg-bp-base/70 rounded-lg border border-bp-border">
                    <div className="flex items-center gap-1.5 mb-2">
                      <span className="text-xs px-1.5 py-0.5 rounded bg-bp-cyan-tint text-bp-cyan border border-bp-cyan/20 font-medium">
                        Source
                      </span>
                      <span className="text-sm font-medium text-bp-text">{experiment.sourceDataset}</span>
                    </div>
                    <p className="text-xs text-bp-muted leading-relaxed">{experiment.sourceDescription}</p>
                  </div>
                  <div className="p-3 bg-bp-base/70 rounded-lg border border-bp-border">
                    <div className="flex items-center gap-1.5 mb-2">
                      <span className="text-xs px-1.5 py-0.5 rounded bg-bp-yellow/15 text-bp-yellow border border-bp-yellow/20 font-medium">
                        Target
                      </span>
                      <span className="text-sm font-medium text-bp-text">{experiment.targetDataset}</span>
                    </div>
                    <p className="text-xs text-bp-muted leading-relaxed">{experiment.targetDescription}</p>
                  </div>
                </div>
              </Card>

              <Card>
                <div className="flex items-center gap-2 mb-4">
                  <BarChart3 className="w-4 h-4 text-bp-yellow" />
                  <div>
                    <h3 className="text-sm font-semibold text-bp-text">Baselines</h3>
                    <p className="text-xs text-bp-muted">{experiment.baselines.length} 个基线方法</p>
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-bp-border">
                        <th className="pb-2 text-xs text-bp-muted font-medium w-1/3">方法名称</th>
                        <th className="pb-2 text-xs text-bp-muted font-medium">描述</th>
                        <th className="pb-2 text-xs text-bp-muted font-medium w-24">类别</th>
                      </tr>
                    </thead>
                    <tbody>
                      {experiment.baselines.map((bl, idx) => (
                        <tr key={bl.name + idx} className="border-b border-bp-border/50 last:border-0">
                          <td className="py-2.5 pr-3 text-bp-text font-medium font-mono text-xs">{bl.name}</td>
                          <td className="py-2.5 pr-3 text-bp-muted text-xs">{bl.description}</td>
                          <td className="py-2.5">
                            <span className={cn('text-xs px-1.5 py-0.5 rounded border', categoryColor[bl.category] || categoryColor.traditional)}>
                              {categoryLabel[bl.category] || categoryLabel.traditional}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>

              <Card>
                <div className="flex items-center gap-2 mb-4">
                  <Target className="w-4 h-4 text-bp-green" />
                  <div>
                    <h3 className="text-sm font-semibold text-bp-text">Metrics</h3>
                    <p className="text-xs text-bp-muted">{experiment.metrics.length} 项评估指标</p>
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-bp-border">
                        <th className="pb-2 text-xs text-bp-muted font-medium w-1/4">指标名称</th>
                        <th className="pb-2 text-xs text-bp-muted font-medium">描述</th>
                        <th className="pb-2 text-xs text-bp-muted font-medium w-40">目标值</th>
                      </tr>
                    </thead>
                    <tbody>
                      {experiment.metrics.map((m, idx) => (
                        <tr key={m.name + idx} className="border-b border-bp-border/50 last:border-0">
                          <td className="py-2.5 pr-3 text-bp-text font-medium font-mono text-xs">{m.name}</td>
                          <td className="py-2.5 pr-3 text-bp-muted text-xs">{m.description}</td>
                          <td className="py-2.5">
                            <span className="text-xs font-mono text-bp-green bg-bp-green/10 px-2 py-0.5 rounded">
                              {m.target}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>

              <Card>
                <div className="flex items-center gap-2 mb-4">
                  <ListChecks className="w-4 h-4 text-bp-cyan" />
                  <div>
                    <h3 className="text-sm font-semibold text-bp-text">Experimental Steps</h3>
                    <p className="text-xs text-bp-muted">{experiment.steps.length} 个步骤</p>
                  </div>
                </div>
                <div className="space-y-0">
                  {experiment.steps.map((s, idx) => (
                    <div key={s.step + '-' + idx} className="flex gap-3">
                      <div className="flex flex-col items-center shrink-0 w-8">
                        <div className="w-8 h-8 rounded-full bg-bp-cyan-tint border border-bp-cyan/30 flex items-center justify-center">
                          <span className="text-xs font-bold text-bp-cyan">{s.step}</span>
                        </div>
                        {idx < experiment.steps.length - 1 && (
                          <div className="w-0.5 flex-1 min-h-[12px] bg-bp-surface rounded-full my-1" />
                        )}
                      </div>
                      <div className={cn(idx < experiment.steps.length - 1 && 'pb-4')}>
                        <h4 className="text-sm font-semibold text-bp-text mb-1">{s.title}</h4>
                        <p className="text-xs text-bp-muted leading-relaxed mb-2">{s.description}</p>
                        <div className="flex items-start gap-1.5">
                          <CheckCircle className="w-3.5 h-3.5 text-bp-green mt-0.5 shrink-0" />
                          <span className="text-xs text-bp-green/90">{s.expected}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>

              <Card>
                <div className="flex items-center gap-2 mb-4">
                  <BarChart3 className="w-4 h-4 text-bp-green" />
                  <div>
                    <h3 className="text-sm font-semibold text-bp-text">Expected Results</h3>
                    <p className="text-xs text-bp-muted">初步分析预期</p>
                  </div>
                </div>
                <p className="text-sm text-bp-text leading-relaxed">{experiment.expectedResults}</p>
              </Card>

              <Card>
                <div className="flex items-center gap-2 mb-4">
                  <AlertTriangle className="w-4 h-4 text-bp-yellow" />
                  <div>
                    <h3 className="text-sm font-semibold text-bp-text">Limitations</h3>
                    <p className="text-xs text-bp-muted">{experiment.limitations.length} 项潜在限制</p>
                  </div>
                </div>
                <div className="space-y-2">
                  {experiment.limitations.map((lim, idx) => (
                    <div key={idx} className="flex items-start gap-2 p-2.5 rounded-lg bg-bp-yellow/5 border border-bp-yellow/10">
                      <AlertTriangle className="w-4 h-4 text-bp-yellow mt-0.5 shrink-0" />
                      <span className="text-xs text-bp-yellow/90 leading-relaxed">{lim}</span>
                    </div>
                  ))}
                </div>
              </Card>
            </div>

            <div className="lg:col-span-1">
              <div className="sticky top-6 space-y-4">
                <PrimaryHypothesisActions
                  onGenerate={handleGenerate}
                  onSmallValidation={handleSmallValidation}
                  onOpenWorkflow={handleOpenWorkflow}
                  generatingDesign={generatingDesign}
                  runningValidation={runningValidation}
                />
                {projectMode === 'federated_learning' && (
                  <FlExperimentPlanSidebar experiment={experiment} />
                )}
                <VerifiabilityChecklist exp={experiment} />

                <Card>
                  <h4 className="text-sm font-semibold text-bp-text mb-3 flex items-center gap-2">
                    <BookOpen className="w-4 h-4 text-bp-cyan" />
                    实验概览
                  </h4>
                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between">
                      <span className="text-bp-muted">基线方法</span>
                      <span className="text-bp-text font-mono">{experiment.baselines.length}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-bp-muted">评估指标</span>
                      <span className="text-bp-text font-mono">{experiment.metrics.length}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-bp-muted">实验步骤</span>
                      <span className="text-bp-text font-mono">{experiment.steps.length}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-bp-muted">潜在限制</span>
                      <span className="text-bp-text font-mono">{experiment.limitations.length}</span>
                    </div>
                  </div>
                </Card>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}