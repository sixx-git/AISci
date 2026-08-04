import { useEffect, useMemo, useState } from 'react';
import {
  ArrowLeft, Trash2, Upload, FolderOpen, Sparkles,
  Play, RefreshCw, AlertTriangle, CheckCircle2, FileCode2, Network,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { cn } from '@/lib/utils';
import { toAbsoluteDatasetUrl } from '@/lib/datasetUrls';
import iterativeExperimentService from '@/services/iterativeExperimentService';
import flSimulationService from '@/services/flSimulationService';
import type {
  DataConfig,
  DataSourceType,
  IterativeExperiment,
  RunMode,
  QualityMode,
} from '@/types/iterativeExperiment';
import type { FlSimBackend, FlSimulationCapabilities, FlSimulationRunResult } from '@/types';
import { PHASE_EMOJI, PHASE_LABEL } from './phaseLabels';
import { IterationTimeline } from './IterationTimeline';

interface ExperimentDetailProps {
  projectId: string;
  projectMode?: string;
  experiment: IterativeExperiment;
  busy?: boolean;
  error?: string | null;
  onClearError?: () => void;
  onBack: () => void;
  onDelete: () => void;
  onRecommend: (feedback?: string) => void;
  onUploadFile: (file: File) => Promise<DataConfig>;
  onAutoDetect: (directoryPath: string) => Promise<{
    preview: Record<string, unknown>;
    data_config: DataConfig;
  }>;
  onDesignScript: (dataConfig: DataConfig) => void;
  onSetRunMode: (mode: RunMode) => void;
  onSetQualityMode: (mode: QualityMode) => void;
  onRunIteration: () => void;
  onRunToCompletion: () => void;
  onSubmitFeedback: (text: string) => void;
  onRedesignFromFeedback: (text: string) => void;
  onExperimentUpdated?: (exp: IterativeExperiment) => void;
}

const SOURCE_OPTIONS: Array<{ label: string; value: DataSourceType; icon: typeof Upload }> = [
  { label: '上传文件', value: 'uploaded', icon: Upload },
  { label: '本地目录路径', value: 'directory', icon: FolderOpen },
];

const PROFILES = ['', 'SisFall', 'MobiAct', 'UCI_HAR', 'AutoDetect'];

function resolveInitialSourceType(cfg?: DataConfig | null): DataSourceType {
  if (cfg?.source_type === 'directory') return 'directory';
  return 'uploaded';
}

function resolveInitialProfileName(cfg?: DataConfig | null): string {
  if (!cfg) return '';
  if (cfg.profile_name) return cfg.profile_name;
  // AutoDetect 结果通常带 profile_json 而无显式 profile_name
  if (cfg.source_type === 'directory' && cfg.profile_json) return 'AutoDetect';
  return '';
}

export function ExperimentDetail({
  projectId,
  projectMode = 'general',
  experiment,
  busy,
  error,
  onClearError,
  onBack,
  onDelete,
  onRecommend,
  onUploadFile,
  onAutoDetect,
  onDesignScript,
  onSetRunMode,
  onSetQualityMode,
  onRunIteration,
  onRunToCompletion,
  onSubmitFeedback,
  onRedesignFromFeedback,
  onExperimentUpdated,
}: ExperimentDetailProps) {
  const phase = experiment.phase;
  const hasDatasetRecommendations = Boolean(experiment.dataset_recommendations?.length);
  const isSandbox = experiment.executor_type === 'sandbox';
  const isFederatedProject = projectMode === 'federated_learning';
  const boundConfig = experiment.data_config ?? null;

  const [sourceType, setSourceType] = useState<DataSourceType>(() =>
    resolveInitialSourceType(boundConfig),
  );
  const [uploadedConfig, setUploadedConfig] = useState<DataConfig | null>(
    boundConfig?.source_type === 'uploaded' || boundConfig?.source_type === 'local_json'
      ? boundConfig
      : null,
  );
  const [fileName, setFileName] = useState(boundConfig?.file_name || '');
  const [filePath, setFilePath] = useState(boundConfig?.source_path || '');
  const [profileName, setProfileName] = useState(() => resolveInitialProfileName(boundConfig));
  const [profileConfirmed, setProfileConfirmed] = useState(() =>
    Boolean(boundConfig?.source_path && (
      resolveInitialProfileName(boundConfig) !== 'AutoDetect'
      || Boolean(boundConfig.profile_json)
    )),
  );
  const [autodetectPreview, setAutodetectPreview] = useState<Record<string, unknown> | null>(null);
  const [autodetectConfig, setAutodetectConfig] = useState<DataConfig | null>(() =>
    resolveInitialProfileName(boundConfig) === 'AutoDetect' && boundConfig?.source_path
      ? boundConfig
      : null,
  );
  const [feedback, setFeedback] = useState(experiment.human_feedback || '');
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    setFeedback(experiment.human_feedback || '');
  }, [experiment.id, experiment.human_feedback]);
  const [flScripts, setFlScripts] = useState<Array<{
    id: string;
    path?: string;
    recommended_when?: string;
    setting?: string;
    preview?: string;
  }>>([]);
  const [applyingScript, setApplyingScript] = useState<string | null>(null);
  const [simCaps, setSimCaps] = useState<FlSimulationCapabilities | null>(null);
  const [simBackend, setSimBackend] = useState<FlSimBackend>('local_pack');
  const [simClients, setSimClients] = useState(5);
  const [simRounds, setSimRounds] = useState(10);
  const [simStrategy, setSimStrategy] = useState('FedAvg');
  const [simPartition, setSimPartition] = useState('dirichlet');
  const [simRunning, setSimRunning] = useState(false);
  const [simResult, setSimResult] = useState<FlSimulationRunResult | null>(
    () => (experiment.fl_simulation_latest as FlSimulationRunResult | null) || null,
  );
  const [simPanelOpen, setSimPanelOpen] = useState(true);

  useEffect(() => {
    let cancelled = false;
    if (!isFederatedProject) {
      setFlScripts([]);
      return () => { cancelled = true; };
    }
    void iterativeExperimentService.listFlScriptTemplates(projectId)
      .then((items) => {
        if (!cancelled) setFlScripts(items.slice(0, 3));
      })
      .catch(() => {
        if (!cancelled) setFlScripts([]);
      });
    void flSimulationService.getCapabilities(projectId)
      .then((caps) => {
        if (cancelled) return;
        setSimCaps(caps);
      })
      .catch(() => {
        if (!cancelled) setSimCaps(null);
      });
    void flSimulationService.getConfig(projectId)
      .then((cfg) => {
        if (cancelled) return;
        if (cfg.backend === 'local_pack' || cfg.backend === 'flower' || cfg.backend === 'fedml') {
          setSimBackend(cfg.backend);
        }
        if (cfg.spec?.num_clients) setSimClients(Number(cfg.spec.num_clients));
        if (cfg.spec?.rounds) setSimRounds(Number(cfg.spec.rounds));
        if (cfg.spec?.strategy) setSimStrategy(String(cfg.spec.strategy));
        if (cfg.spec?.partition) setSimPartition(String(cfg.spec.partition));
      })
      .catch(() => { /* ignore */ });
    void flSimulationService.getLatest(projectId, experiment.id)
      .then((latest) => {
        if (!cancelled && latest.result) setSimResult(latest.result);
      })
      .catch(() => { /* ignore */ });
    return () => { cancelled = true; };
  }, [projectId, isFederatedProject, experiment.id]);

  useEffect(() => {
    if (experiment.fl_simulation_latest) {
      setSimResult(experiment.fl_simulation_latest as FlSimulationRunResult);
    }
  }, [experiment.fl_simulation_latest]);

  const canShowUpload = isSandbox && phase !== 'running' && phase !== 'completed';
  const canIterate =
    phase === 'script_designed'
    || phase === 'running'
    || phase === 'needs_human_review'
    || (Boolean(experiment.initial_plan) && phase !== 'completed' && phase !== 'failed');

  const flowerReady = Boolean(
    simCaps?.backends?.find((b) => b.id === 'flower')?.installed,
  );
  const fedmlReady = Boolean(
    simCaps?.backends?.find((b) => b.id === 'fedml')?.installed,
  );
  const fedmlFeatureOn = Boolean(
    simCaps?.backends?.find((b) => b.id === 'fedml')?.enabled ?? true,
  );
  const simFeatureOn = Boolean(simCaps?.enabled);
  const overviewHistory = useMemo(() => {
    const rows = experiment.iterations.map((it) => ({
      n: it.iteration_number,
      duration: Number(it.duration_seconds || 0),
    }));
    const maxDuration = Math.max(0, ...rows.map((r) => r.duration));
    return { rows, maxDuration };
  }, [experiment.iterations]);

  const autodetectBlocked =
    sourceType === 'directory'
    && profileName === 'AutoDetect'
    && !profileConfirmed
    && !boundConfig?.source_path;

  const hasBoundData = Boolean(boundConfig?.source_path);
  const formReadyForDesign =
    sourceType === 'uploaded'
      ? Boolean(uploadedConfig?.source_path)
      : Boolean(filePath.trim())
        && Boolean(profileName)
        && !autodetectBlocked;
  const canDesignScript = !busy && (hasBoundData || formReadyForDesign);

  const buildDataConfig = (): DataConfig => {
    if (sourceType === 'uploaded') {
      if (uploadedConfig?.source_path) return uploadedConfig;
      if (boundConfig?.source_path) return boundConfig;
      throw new Error('请先上传并完成试加载的数据文件');
    }
    if (profileName === 'AutoDetect') {
      if (autodetectConfig && profileConfirmed) return autodetectConfig;
      if (boundConfig?.source_path) return boundConfig;
      throw new Error('请先完成 AutoDetect 识别试加载并确认');
    }
    const path = filePath.trim() || boundConfig?.source_path || '';
    if (!path) {
      throw new Error('请填写数据目录路径');
    }
    if (!profileName) {
      throw new Error('请选择数据集 Profile');
    }
    return {
      source_type: 'directory',
      source_path: path,
      profile_name: profileName || boundConfig?.profile_name || undefined,
      sample_size: boundConfig?.sample_size ?? 5000,
      preprocessing_steps: boundConfig?.preprocessing_steps || [],
      profile_json: boundConfig?.profile_json,
      row_count: boundConfig?.row_count,
      columns: boundConfig?.columns,
      file_name: boundConfig?.file_name,
    };
  };

  const displayError = error || localError;

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
          <div className="min-w-0">
            <h3 className="text-lg font-semibold text-bp-text flex items-center gap-2">
              <span>{PHASE_EMOJI[phase]}</span>
              <span className="truncate">{experiment.title}</span>
            </h3>
            <p className="text-xs text-bp-muted mt-1">
              阶段: {PHASE_LABEL[phase]} · 迭代: {experiment.current_iteration}/{experiment.max_iterations}
              {' · '}
              {isSandbox ? '数据驱动' : '模拟实验'}
              {' · '}
              模式 {experiment.run_mode === 'full' ? '全量' : 'smoke'}
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" icon={<ArrowLeft className="w-4 h-4" />} onClick={onBack}>
              返回列表
            </Button>
            <Button
              variant="secondary"
              size="sm"
              icon={<Trash2 className="w-4 h-4" />}
              onClick={() => {
                if (window.confirm('确认删除该实验？')) onDelete();
              }}
            >
              删除
            </Button>
          </div>
        </div>

        {displayError && (
          <div className="mb-3 p-2.5 rounded-lg border border-danger-500/30 bg-danger-500/10 text-xs text-danger-300 flex gap-2 items-start">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
            <span className="flex-1 min-w-0">{displayError}</span>
            <button
              type="button"
              className="shrink-0 text-danger-300/70 hover:text-danger-200 px-1"
              title="关闭提示"
              onClick={() => {
                setLocalError(null);
                onClearError?.();
              }}
            >
              ×
            </button>
          </div>
        )}

        <details open className="rounded-bp border border-bp-border bg-bp-base/40 px-3 py-2">
          <summary className="text-sm font-medium text-bp-text cursor-pointer">实验假设</summary>
          <p className="text-sm text-bp-text mt-2 leading-relaxed">{experiment.hypothesis}</p>
          {experiment.constraints.length > 0 && (
            <ul className="mt-2 space-y-1">
              {experiment.constraints.map((c) => (
                <li key={c} className="text-xs text-bp-muted">· 约束: {c}</li>
              ))}
            </ul>
          )}
        </details>
      </Card>

      {/* 有推荐时优先展示推荐列表 */}
      {isSandbox
        && hasDatasetRecommendations
        && (phase === 'created' || phase === 'data_recommended' || phase === 'data_uploaded') && (
        <Card title="推荐数据集" subtitle="根据实验假设由 LLM 推荐经典数据集">
          <div className="space-y-3 mb-3">
            {experiment.dataset_recommendations!.filter((d) => d.is_required).map((d) => (
              <div key={d.name} className="rounded-lg border border-bp-border p-3">
                <div className="text-sm font-medium text-bp-text">{d.name}</div>
                <p className="text-xs text-bp-muted mt-1">{d.description}</p>
                <p className="text-xs text-bp-cyan/80 mt-1">推荐理由: {d.reason}</p>
                {(() => {
                  const href = toAbsoluteDatasetUrl(d.download_url, d.name);
                  return href ? (
                    <a href={href} className="text-xs text-bp-cyan underline mt-1 inline-block" target="_blank" rel="noreferrer">
                      下载链接
                    </a>
                  ) : null;
                })()}
                {d.expected_columns && (
                  <p className="text-[11px] text-bp-muted mt-1">
                    预期字段: {d.expected_columns.join(', ')}
                  </p>
                )}
              </div>
            ))}
            {experiment.dataset_recommendations!.some((d) => !d.is_required) && (
              <details className="text-xs text-bp-muted">
                <summary className="cursor-pointer text-bp-text">可选补充数据集</summary>
                <ul className="mt-2 space-y-1 pl-2">
                  {experiment.dataset_recommendations!.filter((d) => !d.is_required).map((d) => (
                    <li key={d.name}>· {d.name}: {d.reason || d.description}</li>
                  ))}
                </ul>
              </details>
            )}
          </div>
          <Button
            variant="secondary"
            disabled={busy}
            icon={<Sparkles className="w-4 h-4" />}
            onClick={() => onRecommend()}
          >
            重新推荐
          </Button>
        </Card>
      )}

      {/* 绑定 / 上传数据 */}
      {canShowUpload && (
        <Card
          title={hasDatasetRecommendations ? '上传数据集' : '绑定已有数据'}
          subtitle={
            hasDatasetRecommendations
              ? '缺数据不可设计脚本 / 不可迭代（与 shaxiang 一致）'
              : '上传文件或指定本地目录路径；绑定后即可设计脚本'
          }
        >
          <div className="flex flex-wrap gap-2 mb-4">
            {SOURCE_OPTIONS.map((opt) => {
              const Icon = opt.icon;
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => {
                    setSourceType(opt.value);
                    setProfileConfirmed(false);
                    setAutodetectPreview(null);
                    setAutodetectConfig(null);
                    setLocalError(null);
                  }}
                  className={cn(
                    'inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs border transition-colors',
                    sourceType === opt.value
                      ? 'border-bp-cyan/40 bg-bp-cyan-tint text-bp-cyan'
                      : 'border-bp-border text-bp-muted hover:text-bp-text',
                  )}
                >
                  <Icon className="w-3.5 h-3.5" />
                  {opt.label}
                </button>
              );
            })}
          </div>

          {sourceType === 'uploaded' && (
            <div className="mb-3">
              <label className="text-xs text-bp-muted mb-1 block">
                选择数据文件（上传到服务端并试加载）
              </label>
              <input
                type="file"
                accept=".csv,.json,.jsonl,.parquet,.xlsx,.tsv"
                disabled={busy}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  setLocalError(null);
                  setFileName(file.name);
                  void onUploadFile(file)
                    .then((cfg) => {
                      setUploadedConfig(cfg);
                    })
                    .catch((err: unknown) => {
                      setUploadedConfig(null);
                      setLocalError(err instanceof Error ? err.message : '上传失败');
                    });
                }}
                className="block w-full text-xs text-bp-muted file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:bg-bp-panel file:text-bp-text"
              />
              {fileName && uploadedConfig?.source_path && (
                <p className="text-xs text-bp-cyan mt-1">
                  已上传并通过试加载: {fileName}
                  {uploadedConfig.row_count != null ? `（${uploadedConfig.row_count} 行）` : ''}
                </p>
              )}
            </div>
          )}

          {sourceType === 'directory' && (
            <div className="space-y-3 mb-3">
              <p className="text-xs text-bp-muted">
                打开文件资源管理器，进入数据集文件夹，复制完整路径并粘贴。
              </p>
              <input
                type="text"
                value={filePath}
                onChange={(e) => setFilePath(e.target.value)}
                placeholder={String.raw`例如: D:\data\SisFall`}
                className="w-full bg-bp-base border border-bp-border rounded-lg px-3 py-2 text-sm text-bp-text"
              />
              <select
                value={profileName}
                onChange={(e) => {
                  setProfileName(e.target.value);
                  setProfileConfirmed(false);
                  setAutodetectPreview(null);
                  setAutodetectConfig(null);
                }}
                className="w-full bg-bp-base border border-bp-border rounded-lg px-3 py-2 text-sm text-bp-text"
              >
                {PROFILES.map((p) => (
                  <option key={p || 'empty'} value={p}>
                    {p || '选择数据集 Profile'}
                  </option>
                ))}
              </select>
              {profileName === 'AutoDetect' && (
                <div className="space-y-2">
                  <p className="text-xs text-bp-muted">
                    支持文本型表格（.csv / .tsv / .txt / .dat，按分隔表解析）；不支持原始二进制 .dat。
                  </p>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={!filePath.trim() || busy}
                    onClick={() => {
                      setLocalError(null);
                      onClearError?.();
                      const normalized = filePath.trim().replace(/^["']+|["']+$/g, '');
                      if (normalized !== filePath.trim()) setFilePath(normalized);
                      void onAutoDetect(normalized)
                        .then((out) => {
                          setAutodetectPreview(out.preview);
                          setAutodetectConfig(out.data_config);
                          // 试加载已成功则直接确认，避免漏点确认导致设计脚本用空配置
                          setProfileConfirmed(true);
                          setLocalError(null);
                          onClearError?.();
                        })
                        .catch((err: unknown) => {
                          setAutodetectPreview(null);
                          setAutodetectConfig(null);
                          setProfileConfirmed(false);
                          setLocalError(err instanceof Error ? err.message : '自动识别失败');
                        });
                    }}
                  >
                    自动识别并试加载验证
                  </Button>
                  {autodetectPreview && (
                    <div className="rounded-lg border border-bp-border p-3 text-xs space-y-2">
                      {(autodetectPreview.files_scanned != null ||
                        autodetectPreview.files_used != null) && (
                        <p className="text-bp-text">
                          目录扫描{' '}
                          <span className="font-medium text-bp-cyan">
                            {autodetectPreview.files_scanned ?? '?'}
                          </span>{' '}
                          个数据文件，合并采用{' '}
                          <span className="font-medium text-bp-cyan">
                            {autodetectPreview.files_used ?? '?'}
                          </span>{' '}
                          个
                          {Array.isArray(autodetectPreview.used_files) &&
                            autodetectPreview.used_files.length > 0 && (
                              <span className="text-bp-muted">
                                {' '}
                                （{autodetectPreview.used_files.join('、')}）
                              </span>
                            )}
                        </p>
                      )}
                      <div className="max-h-64 overflow-y-auto overflow-x-auto rounded-md bg-bp-base/40 border border-bp-border/60">
                        <pre className="text-bp-muted whitespace-pre-wrap p-2 m-0">
                          {JSON.stringify(autodetectPreview, null, 2)}
                        </pre>
                      </div>
                      <div className="flex gap-2">
                        <Button size="sm" onClick={() => setProfileConfirmed(true)}>
                          确认使用此配置
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => {
                            setAutodetectPreview(null);
                            setAutodetectConfig(null);
                            setProfileConfirmed(false);
                          }}
                        >
                          清除重新识别
                        </Button>
                      </div>
                      {profileConfirmed && (
                        <p className="text-bp-green inline-flex items-center gap-1">
                          <CheckCircle2 className="w-3.5 h-3.5" /> 已确认配置
                        </p>
                      )}
                    </div>
                  )}
                  {autodetectBlocked && (
                    <p className="text-xs text-bp-yellow flex gap-1">
                      <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                      AutoDetect 模式下，请先完成识别试加载并确认，才能设计脚本。
                    </p>
                  )}
                </div>
              )}
            </div>
          )}

          {boundConfig && (
            <p className="text-xs text-bp-green mb-3">
              已绑定数据: {boundConfig.file_name || boundConfig.source_path}
              （{boundConfig.row_count ?? '?'} 行）
              {hasBoundData && !formReadyForDesign ? ' · 可直接设计脚本' : ''}
            </p>
          )}

          <Button
            className="w-full"
            disabled={!canDesignScript}
            onClick={() => {
              try {
                setLocalError(null);
                onDesignScript(buildDataConfig());
              } catch (err: unknown) {
                setLocalError(err instanceof Error ? err.message : '请完善数据配置');
              }
            }}
          >
            {busy ? '设计中（后台执行，可切换页面）…' : '确认并设计分析脚本'}
          </Button>
        </Card>
      )}

      {/* 无推荐时：绑定区之后提供可选推荐入口 */}
      {isSandbox
        && !hasDatasetRecommendations
        && (phase === 'created' || phase === 'data_recommended' || phase === 'data_uploaded') && (
        <Card
          title="数据集推荐（可选）"
          subtitle="已跳过自动推荐。需要时可让 AI 推荐经典数据集"
        >
          <p className="text-sm text-bp-muted mb-3">暂无推荐列表。可直接使用上方绑定已有数据，或按需触发推荐。</p>
          <Button
            variant="secondary"
            disabled={busy}
            icon={<Sparkles className="w-4 h-4" />}
            onClick={() => onRecommend()}
          >
            推荐数据集
          </Button>
        </Card>
      )}

      {/* 迭代区 */}
      {canIterate && (
        <Card title="执行与分析" subtitle="smoke / 全量 · 自我纠正在脚本设计阶段完成">
          {isSandbox && (
            <div className="mb-4 space-y-3">
              <div className="p-3 rounded-lg border border-bp-border">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-bp-text">运行模式</div>
                    <p className="text-xs text-bp-muted mt-0.5">
                      关闭（推荐）：仅小样验收；打开后 smoke 通过再正式全量推演。
                    </p>
                  </div>
                  <label className="inline-flex items-center gap-2 text-xs text-bp-text cursor-pointer">
                    <input
                      type="checkbox"
                      checked={experiment.run_mode === 'full'}
                      onChange={(e) => onSetRunMode(e.target.checked ? 'full' : 'smoke_only')}
                      className="accent-bp-cyan"
                    />
                    正式全量推演
                  </label>
                </div>
              </div>
              <div className="p-3 rounded-lg border border-bp-border">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-bp-text">质量模式</div>
                    <p className="text-xs text-bp-muted mt-0.5">
                      草稿：有图且非「显著问题」即通过（含「需调整」）；严格：需 promising/success。
                    </p>
                  </div>
                  <select
                    value={experiment.quality_mode === 'strict' ? 'strict' : 'draft'}
                    onChange={(e) => onSetQualityMode(e.target.value as QualityMode)}
                    className="bg-bp-base border border-bp-border rounded-lg px-2 py-1.5 text-xs text-bp-text"
                  >
                    <option value="draft">草稿模式</option>
                    <option value="strict">严格模式</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          {isFederatedProject && flScripts.length > 0 && (
            <div className="mb-4 rounded-lg border border-bp-cyan/25 bg-bp-cyan-tint/40 p-3 space-y-2">
              <div className="flex items-center gap-2 text-sm font-medium text-bp-text">
                <FileCode2 className="w-4 h-4 text-bp-cyan" />
                FL 参考脚本模板
              </div>
              <p className="text-xs text-bp-muted leading-relaxed">
                不会直接替换 analysis_script。点击后会把该模板当作「反馈」，结合已绑定数据与实验假设，
                让大模型重新设计可证伪的新脚本（与「基于反馈重新设计脚本」同路径）。
              </p>
              <div className="space-y-2">
                {flScripts.map((s) => (
                  <div
                    key={s.id}
                    className="rounded-md border border-bp-border bg-bp-base/60 px-3 py-2 flex flex-col sm:flex-row sm:items-center gap-2"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-medium text-bp-text truncate">
                        {s.recommended_when || s.id}
                      </div>
                      <div className="text-[11px] text-bp-muted truncate">
                        {(s.setting || '').toUpperCase()} · {s.path || s.id}
                      </div>
                    </div>
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={busy || applyingScript === s.id}
                      onClick={async () => {
                        setApplyingScript(s.id);
                        setLocalError(null);
                        try {
                          const updated = await iterativeExperimentService.applyFlScript(
                            projectId,
                            experiment.id,
                            s.id,
                          );
                          onExperimentUpdated?.(updated);
                        } catch (err) {
                          // 长任务若前端超时，后端可能已完成：强制拉取一次最新实验
                          try {
                            const latest = await iterativeExperimentService.get(
                              projectId,
                              experiment.id,
                            );
                            if (latest) onExperimentUpdated?.(latest);
                          } catch {
                            /* ignore refresh failure */
                          }
                          setLocalError(
                            err instanceof Error
                              ? err.message
                              : '基于 FL 模板设计脚本失败',
                          );
                        } finally {
                          setApplyingScript(null);
                        }
                      }}
                    >
                      {applyingScript === s.id ? '设计中（可等待）…' : '基于模板重新设计脚本'}
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {isFederatedProject && simFeatureOn && (
            <div className="mb-4 rounded-lg border border-dashed border-violet-500/40 bg-violet-500/5 p-4 space-y-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 text-sm font-semibold text-bp-text">
                    <Network className="w-4 h-4 text-violet-400 shrink-0" />
                    联邦仿真控制台
                    <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-violet-500/15 text-violet-300">
                      独立通道
                    </span>
                  </div>
                  <p className="text-xs text-bp-muted mt-1 leading-relaxed">
                    只控制下方「仿真模式 / 仿真参数」。不走 analysis_script，也不同于上方的
                    「正式全量推演」与「执行下一轮」沙箱按钮。
                  </p>
                </div>
                <button
                  type="button"
                  className="text-[11px] text-bp-muted hover:text-bp-text shrink-0"
                  onClick={() => setSimPanelOpen((v) => !v)}
                >
                  {simPanelOpen ? '收起' : '展开'}
                </button>
              </div>

              {simPanelOpen && (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <div className="text-xs font-medium text-bp-text">仿真模式</div>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                      {([
                        {
                          id: 'local_pack' as FlSimBackend,
                          title: 'FL Pack 本地',
                          desc: 'sklearn pilot（默认）',
                          ready: true,
                          disabled: false,
                        },
                        {
                          id: 'flower' as FlSimBackend,
                          title: 'Flower',
                          desc: flowerReady ? '已安装 flwr' : '兼容模式',
                          ready: flowerReady,
                          disabled: false,
                        },
                        {
                          id: 'fedml' as FlSimBackend,
                          title: 'FedML',
                          desc: !fedmlFeatureOn
                            ? '功能已关闭'
                            : fedmlReady
                              ? '已安装 fedml'
                              : '兼容模式',
                          ready: fedmlReady,
                          disabled: !fedmlFeatureOn,
                        },
                      ]).map((opt) => (
                        <button
                          key={opt.id}
                          type="button"
                          disabled={opt.disabled}
                          onClick={() => setSimBackend(opt.id)}
                          className={cn(
                            'text-left rounded-lg border px-3 py-2.5 transition-colors',
                            opt.disabled && 'opacity-45 cursor-not-allowed',
                            simBackend === opt.id
                              ? 'border-violet-400/60 bg-violet-500/15 ring-1 ring-violet-400/30'
                              : 'border-bp-border bg-bp-base/50 hover:border-violet-400/35',
                          )}
                        >
                          <div className="text-xs font-medium text-bp-text">{opt.title}</div>
                          <div className="text-[11px] text-bp-muted mt-0.5">{opt.desc}</div>
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-2">
                    <div className="text-xs font-medium text-bp-text">仿真参数</div>
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 rounded-lg border border-bp-border bg-bp-base/40 p-3">
                      <label className="text-[11px] text-bp-muted space-y-1">
                        <span>客户端数（≥2）</span>
                        <input
                          type="number"
                          min={2}
                          max={50}
                          value={simClients}
                          onChange={(e) => {
                            const n = Number(e.target.value);
                            if (!Number.isFinite(n)) {
                              setSimClients(2);
                              return;
                            }
                            setSimClients(Math.max(2, Math.min(Math.trunc(n), 50)));
                          }}
                          className="input-field text-xs"
                        />
                      </label>
                      <label className="text-[11px] text-bp-muted space-y-1">
                        <span>通信轮次</span>
                        <input
                          type="number"
                          min={1}
                          max={200}
                          value={simRounds}
                          onChange={(e) => setSimRounds(Number(e.target.value) || 10)}
                          className="input-field text-xs"
                        />
                      </label>
                      <label className="text-[11px] text-bp-muted space-y-1">
                        <span>聚合策略</span>
                        <select
                          value={simStrategy}
                          onChange={(e) => setSimStrategy(e.target.value)}
                          className="input-field text-xs"
                        >
                          <option value="FedAvg">FedAvg</option>
                          <option value="FedProx">FedProx</option>
                        </select>
                      </label>
                      <label className="text-[11px] text-bp-muted space-y-1">
                        <span>数据分区</span>
                        <select
                          value={simPartition}
                          onChange={(e) => setSimPartition(e.target.value)}
                          className="input-field text-xs"
                        >
                          <option value="dirichlet">Dirichlet</option>
                          <option value="iid">IID</option>
                          <option value="pathological">Pathological</option>
                        </select>
                      </label>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-violet-500/20">
                    <Button
                      size="sm"
                      variant="secondary"
                      className="!border-violet-400/40 !text-violet-200 hover:!bg-violet-500/10"
                      icon={<Network className="w-3.5 h-3.5" />}
                      disabled={busy || simRunning || (simBackend === 'fedml' && !fedmlFeatureOn)}
                      onClick={async () => {
                        setSimRunning(true);
                        setLocalError(null);
                        try {
                          const payload = {
                            backend: simBackend,
                            num_clients: simClients,
                            rounds: simRounds,
                            strategy: simStrategy,
                            partition: simPartition,
                          };
                          const { result, experiment: updated } = await flSimulationService.run(
                            projectId,
                            experiment.id,
                            payload,
                          );
                          setSimResult(result);
                          if (updated) {
                            onExperimentUpdated?.(updated as unknown as IterativeExperiment);
                          }
                        } catch (err) {
                          setLocalError(err instanceof Error ? err.message : '仿真失败');
                        } finally {
                          setSimRunning(false);
                        }
                      }}
                    >
                      {simRunning ? '联邦仿真中…' : '运行联邦仿真'}
                    </Button>
                    <span className="text-[11px] text-bp-muted">
                      不会触发下方「执行下一轮」沙箱迭代
                    </span>
                  </div>

                  {simResult && (
                    <div className="rounded-lg border border-violet-500/25 bg-bp-base/60 px-3 py-2 space-y-1 text-xs">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-[10px] font-medium text-violet-300">最近一次仿真结果</span>
                        <span className={cn(
                          'px-1.5 py-0.5 rounded text-[10px] font-medium',
                          simResult.success
                            ? 'bg-emerald-500/15 text-emerald-400'
                            : 'bg-amber-500/15 text-amber-400',
                        )}
                        >
                          {simResult.execution_mode || 'unknown'}
                        </span>
                        <span className="text-bp-muted">{simResult.framework}</span>
                        {simResult.success ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                        ) : (
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                        )}
                      </div>
                      {simResult.metrics && (
                        <div className="text-bp-text">
                          acc={String(simResult.metrics.global_accuracy ?? '—')}
                          {' · '}
                          rounds={String(simResult.metrics.communication_rounds ?? '—')}
                          {' · '}
                          clients={String(simResult.metrics.num_clients ?? '—')}
                        </div>
                      )}
                      {simResult.error && (
                        <p className="text-amber-400/90 break-words">{simResult.error}</p>
                      )}
                      {(simResult.notes || []).slice(0, 2).map((n) => (
                        <p key={n} className="text-bp-muted">{n}</p>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {experiment.initial_plan && (
            <details className="mb-4 rounded-lg border border-bp-border px-3 py-2">
              <summary className="text-sm text-bp-text cursor-pointer">
                当前 analysis_script 方案: {experiment.initial_plan.title}
              </summary>
              <p className="text-[11px] text-bp-muted mt-1">
                供下方「执行下一轮」沙箱使用；与上方「联邦仿真控制台」相互独立。
              </p>
              <p className="text-xs text-bp-muted mt-2">{experiment.initial_plan.methodology}</p>
              <pre className="mt-2 text-[11px] text-bp-muted overflow-x-auto max-h-40 bg-bp-base p-2 rounded">
                {experiment.initial_plan.analysis_script}
              </pre>
            </details>
          )}

          <div className="flex flex-wrap gap-2 mb-4">
            <Button
              disabled={busy}
              icon={<Play className="w-4 h-4" />}
              onClick={onRunIteration}
            >
              {experiment.run_mode === 'smoke_only' ? '执行下一轮（smoke）' : '执行下一轮（全量）'}
            </Button>
            {(phase === 'running' || experiment.current_iteration > 0) && (
              <Button
                variant="secondary"
                disabled={busy}
                icon={<RefreshCw className="w-4 h-4" />}
                onClick={onRunToCompletion}
              >
                自动运行至完成
              </Button>
            )}
            <span className="self-center text-[11px] text-bp-muted">
              沙箱迭代（analysis_script）
            </span>
          </div>

          {overviewHistory.rows.length > 0 && (
            <div className="mb-4">
              <h5 className="text-sm font-medium text-bp-text mb-2">概览</h5>
              <div className="space-y-2">
                {overviewHistory.rows.map((m) => {
                  const barPct = overviewHistory.maxDuration > 0
                    ? Math.round((m.duration / overviewHistory.maxDuration) * 100)
                    : 0;
                  return (
                    <div key={m.n} className="flex items-center gap-3 text-xs">
                      <span className="w-12 text-bp-muted">#{m.n}</span>
                      <div className="flex-1 h-2 rounded bg-bp-panel overflow-hidden">
                        <div
                          className="h-full bg-bp-cyan"
                          style={{ width: `${barPct}%` }}
                        />
                      </div>
                      <span className="font-mono text-bp-text w-28 text-right">
                        耗时 {m.duration.toFixed(1)}s
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {experiment.iterations.length > 0 && (
            <div className="mb-4">
              <IterationTimeline iterations={experiment.iterations} />
            </div>
          )}

          <div className="pt-3 border-t border-bp-border">
            <h5 className="text-sm font-medium text-bp-text mb-1">人工反馈</h5>
            <p className="text-xs text-bp-muted mb-2">
              「提交反馈」在第 2 轮及以后执行迭代时才会完整重设计脚本；第 1 轮或需立即生效请用「基于反馈重新设计脚本」。
            </p>
            <textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              rows={4}
              placeholder={'例如：\n1) 当前 Accuracy 疑似泄漏，请改为 GroupKFold\n2) 增加类别分布图与逻辑回归基线'}
              className="w-full bg-bp-base border border-bp-border rounded-lg px-3 py-2 text-sm text-bp-text resize-none mb-2"
            />
            <div className="flex flex-wrap gap-2">
              <Button
                variant="secondary"
                size="sm"
                disabled={!feedback.trim() || busy}
                onClick={() => onSubmitFeedback(feedback)}
              >
                提交反馈
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={busy}
                onClick={() => onRecommend(feedback)}
              >
                基于反馈推荐新数据集
              </Button>
              <Button
                size="sm"
                disabled={!feedback.trim() || busy}
                onClick={() => onRedesignFromFeedback(feedback)}
              >
                基于反馈重新设计脚本
              </Button>
            </div>
            {experiment.human_feedback && (
              <p className="text-xs text-bp-muted mt-2">
                当前反馈状态: {experiment.feedback_status}
              </p>
            )}
          </div>
        </Card>
      )}

      {phase === 'completed' && (
        <Card title="实验已完成">
          <p className="text-sm text-bp-green mb-3">本实验已完成迭代。可在列表中勾选「用于报告」以纳入报告生成。</p>

          {/* 即使实验已完成，也允许查看之前的实验方案与脚本 */}
          {experiment.initial_plan && (
            <details className="mb-4 rounded-lg border border-bp-border bg-bp-base/40 px-3 py-2">
              <summary className="text-sm text-bp-text cursor-pointer">
                查看实验方案与脚本: {experiment.initial_plan.title}
              </summary>
              <p className="text-[11px] text-bp-muted mt-1">
                本实验在脚本设计阶段产出的 analysis_script，供回顾参考。
              </p>
              <p className="text-xs text-bp-muted mt-2">{experiment.initial_plan.methodology}</p>
              <pre className="mt-2 text-[11px] text-bp-muted overflow-x-auto max-h-72 bg-bp-base p-2 rounded">
                {experiment.initial_plan.analysis_script}
              </pre>
            </details>
          )}

          <div className="mb-4">
            <IterationTimeline iterations={experiment.iterations} />
          </div>

          {experiment.human_feedback && (
            <details className="mt-3 rounded-lg border border-bp-border bg-bp-base/40 px-3 py-2">
              <summary className="text-sm text-bp-text cursor-pointer">查看历史反馈</summary>
              <p className="text-xs text-bp-muted mt-2 whitespace-pre-wrap">{experiment.human_feedback}</p>
              <p className="text-[11px] text-bp-muted mt-1">反馈状态: {experiment.feedback_status}</p>
            </details>
          )}
        </Card>
      )}
    </div>
  );
}
