import { useState, useCallback, useEffect } from 'react';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import {
  FlaskConical, CheckCircle, XCircle, Database,
  BarChart3, ListChecks, Target, BookOpen,
  AlertTriangle, Lightbulb, FileText, Play,
  Sparkles, Loader2, AlertCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import experimentService from '@/services/experimentService';
import { useToast } from '@/hooks/useToast';
import { getErrorMessage } from '@/lib/errors';
import {
  categoryColor,
  categoryLabel,
  mapBackendExperimentDesignToDetailed,
} from '@/lib/mappers/experimentDesignMapper';
import { selectedHypothesisKey } from '@/lib/storageKeys';
import type { DetailedExperimentDesign } from '@/types';

interface ExperimentDesignPageProps {
  projectId?: string;
  projectMode?: string;
  compact?: boolean;
  revalidateKey?: number;
  latestRunId?: string | null;
  selectedHypothesisId?: string | null;
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
              <CheckCircle className="w-4 h-4 text-green-400 shrink-0" />
            ) : (
              <XCircle className="w-4 h-4 text-red-400 shrink-0" />
            )}
            <span className={item.ok ? 'text-bp-text' : 'text-red-300'}>
              {item.label}
            </span>
          </div>
        ))}
      </div>
      <div className={cn(
        'mt-4 p-2.5 rounded-lg text-xs text-center font-medium',
        allOk ? 'bg-green-500/10 text-green-400 border border-green-500/20' :
        'bg-red-500/10 text-red-400 border border-red-500/20',
      )}>
        {allOk ? '✓ 实验方案可验证' : '✗ 实验方案不完整'}
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
  const { message: alertMsg, showAlert } = useToast();
  const [experiment, setExperiment] = useState<DetailedExperimentDesign | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

    experimentService.getProjectExperimentDesigns(_projectId)
      .then((res) => {
        if (res.code === 200 && Array.isArray(res.data) && res.data.length > 0) {
          const mapped = mapBackendExperimentDesignToDetailed(res.data[0]);
          setExperiment(mapped);
        } else {
          setExperiment(null);
        }
      })
      .catch((err) => {
        setError(getErrorMessage(err, '获取实验设计失败，请检查后端服务是否启动'));
        setExperiment(null);
      })
      .finally(() => setLoading(false));
  }, [_projectId, _revalidateKey, _latestRunId]);

  const handleGenerate = useCallback(() => {
    showAlert('请先在工作流页面运行 Pipeline，完成 experiment_design 阶段后返回查看');
  }, [showAlert]);

  const handleSmallValidation = useCallback(() => {
    showAlert('请先运行 Pipeline 的 small_validation 阶段');
  }, [showAlert]);

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-bp-text mb-2">实验设计</h1>
        <p className="text-bp-muted">
          为选定科学假设生成可执行、可复现的验证方案
          {projectMode === 'federated_learning' && (
            <span className="ml-2 text-cyan-400 text-sm">· 联邦学习模式</span>
          )}
        </p>
      </div>

      {projectMode === 'federated_learning' && experiment && (
        <Card className="p-4 mb-6 border-cyan-500/20 bg-cyan-500/5">
          <h3 className="text-sm font-semibold text-cyan-300 mb-3">联邦实验计划</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
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
          <p className="text-[11px] text-bp-muted mt-3">
            隐私机制建议：DP、Secure Aggregation、PSI（垂直联邦）— 详见 Pipeline 生成的 federated_plan
          </p>
        </Card>
      )}

      {alertMsg && (
        <div className="mb-4 px-4 py-2.5 rounded-lg bg-bp-cyan-tint border border-bp-cyan/20 text-sm text-bp-cyan animate-pulse">
          {alertMsg}
        </div>
      )}

      {loading && (
        <div className="flex flex-col items-center justify-center py-20 text-bp-muted">
          <Loader2 className="w-8 h-8 animate-spin mb-3 text-bp-cyan" />
          <p className="text-sm">正在加载实验设计...</p>
        </div>
      )}

      {!loading && error && (
        <div className="flex flex-col items-center justify-center py-20 text-bp-muted">
          <AlertCircle className="w-8 h-8 mb-3 text-red-400" />
          <p className="text-sm text-red-400 mb-2">加载实验设计失败</p>
          <p className="text-xs text-bp-muted">{error}</p>
        </div>
      )}

      {!loading && !error && !experiment && (
        <div className="flex flex-col items-center justify-center py-20 text-bp-muted">
          {selectedHypothesisId ? (
            <>
              <Lightbulb className="w-8 h-8 mb-3 text-amber-400" />
              <p className="text-base text-bp-text mb-2">当前主假设尚未生成实验设计</p>
              <p className="text-xs text-bp-muted mb-4">
                请在候选假设页面选择主假设后，运行工作流中的实验设计阶段。
              </p>
            </>
          ) : (
            <>
              <AlertTriangle className="w-8 h-8 mb-3 text-amber-400" />
              <p className="text-sm text-bp-muted mb-2">暂无实验设计</p>
              <p className="text-xs text-bp-muted mb-4">
                请先在候选假设页面选择一个主假设，然后运行 Pipeline 的实验设计阶段。
              </p>
            </>
          )}
          <Button
            variant="secondary"
            size="sm"
            icon={<FlaskConical className="w-4 h-4" />}
            onClick={() => showAlert('请前往工作流页面运行 Pipeline')}
          >
            前往工作流
          </Button>
        </div>
      )}

      {experiment && (
        <>
          <div className="mb-6">
            <Card className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div className="flex items-center gap-2">
                <Lightbulb className="w-5 h-5 text-amber-400" />
                <div>
                  <span className="text-xs text-bp-muted">当前主假设</span>
                  <p className="text-sm text-bp-text font-medium mt-0.5">{experiment.hypothesisTitle}</p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="primary" size="sm" icon={<Sparkles className="w-4 h-4" />}
                  onClick={handleGenerate}>
                  生成实验设计
                </Button>
                <Button variant="secondary" size="sm" icon={<Play className="w-4 h-4" />}
                  onClick={handleSmallValidation}>
                  运行小样验证
                </Button>
                <Button variant="secondary" size="sm" icon={<FileText className="w-4 h-4" />}
                  onClick={() => showAlert('跳转至研究报告页面（待对接）')}>
                  进入研究报告
                </Button>
              </div>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            <div className="lg:col-span-3 space-y-5">

              <Card>
                <div className="flex items-center gap-2 mb-4">
                  <Target className="w-4 h-4 text-blue-400" />
                  <div>
                    <h3 className="text-sm font-semibold text-bp-text">实验目标</h3>
                    <p className="text-xs text-bp-muted">Objective</p>
                  </div>
                </div>
                <p className="text-sm text-bp-text leading-relaxed">{experiment.objective}</p>
              </Card>

              <Card>
                <div className="flex items-center gap-2 mb-4">
                  <FlaskConical className="w-4 h-4 text-purple-400" />
                  <div>
                    <h3 className="text-sm font-semibold text-bp-text">实验方法</h3>
                    <p className="text-xs text-bp-muted">Methods</p>
                  </div>
                </div>
                <p className="text-sm text-bp-text leading-relaxed">{experiment.methods}</p>
              </Card>

              <Card>
                <div className="flex items-center gap-2 mb-4">
                  <Database className="w-4 h-4 text-green-400" />
                  <div>
                    <h3 className="text-sm font-semibold text-bp-text">数据集</h3>
                    <p className="text-xs text-bp-muted">Datasets</p>
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-3 bg-bp-base/70 rounded-lg border border-bp-border">
                    <div className="flex items-center gap-1.5 mb-2">
                      <span className="text-[11px] px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-400 border border-blue-500/20 font-medium">
                        Source
                      </span>
                      <span className="text-sm font-medium text-bp-text">{experiment.sourceDataset}</span>
                    </div>
                    <p className="text-xs text-bp-muted leading-relaxed">{experiment.sourceDescription}</p>
                  </div>
                  <div className="p-3 bg-bp-base/70 rounded-lg border border-bp-border">
                    <div className="flex items-center gap-1.5 mb-2">
                      <span className="text-[11px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-500/20 font-medium">
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
                  <BarChart3 className="w-4 h-4 text-amber-400" />
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
                            <span className={cn('text-[11px] px-1.5 py-0.5 rounded border', categoryColor[bl.category] || categoryColor.traditional)}>
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
                  <Target className="w-4 h-4 text-green-400" />
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
                            <span className="text-xs font-mono text-green-400 bg-green-500/10 px-2 py-0.5 rounded">
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
                  <ListChecks className="w-4 h-4 text-blue-400" />
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
                          <CheckCircle className="w-3.5 h-3.5 text-green-400 mt-0.5 shrink-0" />
                          <span className="text-xs text-green-400/80">{s.expected}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>

              <Card>
                <div className="flex items-center gap-2 mb-4">
                  <BarChart3 className="w-4 h-4 text-green-400" />
                  <div>
                    <h3 className="text-sm font-semibold text-bp-text">Expected Results</h3>
                    <p className="text-xs text-bp-muted">初步分析预期</p>
                  </div>
                </div>
                <p className="text-sm text-bp-text leading-relaxed">{experiment.expectedResults}</p>
              </Card>

              <Card>
                <div className="flex items-center gap-2 mb-4">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  <div>
                    <h3 className="text-sm font-semibold text-bp-text">Limitations</h3>
                    <p className="text-xs text-bp-muted">{experiment.limitations.length} 项潜在限制</p>
                  </div>
                </div>
                <div className="space-y-2">
                  {experiment.limitations.map((lim, idx) => (
                    <div key={idx} className="flex items-start gap-2 p-2.5 rounded-lg bg-amber-500/5 border border-amber-500/10">
                      <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
                      <span className="text-xs text-amber-300/80 leading-relaxed">{lim}</span>
                    </div>
                  ))}
                </div>
              </Card>
            </div>

            <div className="lg:col-span-1">
              <div className="sticky top-6 space-y-4">
                <VerifiabilityChecklist exp={experiment} />

                <Card>
                  <h4 className="text-sm font-semibold text-bp-text mb-3 flex items-center gap-2">
                    <BookOpen className="w-4 h-4 text-blue-400" />
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