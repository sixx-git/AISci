import { useMemo, useState } from 'react';
import {
  ArrowLeft, Trash2, Upload, FolderOpen, Link2, Sparkles,
  Play, RefreshCw, AlertTriangle, CheckCircle2,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { cn } from '@/lib/utils';
import type {
  DataConfig,
  DataSourceType,
  IterativeExperiment,
  RunMode,
} from '@/types/iterativeExperiment';
import { PHASE_EMOJI, PHASE_LABEL } from './phaseLabels';

interface ExperimentDetailProps {
  experiment: IterativeExperiment;
  busy?: boolean;
  error?: string | null;
  onBack: () => void;
  onDelete: () => void;
  onRecommend: (feedback?: string) => void;
  onDesignScript: (dataConfig: DataConfig) => void;
  onSetRunMode: (mode: RunMode) => void;
  onRunIteration: () => void;
  onRunToCompletion: () => void;
  onSubmitFeedback: (text: string) => void;
  onRedesignFromFeedback: (text: string) => void;
}

const SOURCE_OPTIONS: Array<{ label: string; value: DataSourceType; icon: typeof Upload }> = [
  { label: '上传文件', value: 'uploaded', icon: Upload },
  { label: '本地目录路径', value: 'directory', icon: FolderOpen },
  { label: '本地文件路径', value: 'local_csv', icon: Link2 },
  { label: 'HuggingFace', value: 'huggingface', icon: Sparkles },
];

const PROFILES = ['', 'SisFall', 'MobiAct', 'UCI_HAR', 'AutoDetect'];

export function ExperimentDetail({
  experiment,
  busy,
  error,
  onBack,
  onDelete,
  onRecommend,
  onDesignScript,
  onSetRunMode,
  onRunIteration,
  onRunToCompletion,
  onSubmitFeedback,
  onRedesignFromFeedback,
}: ExperimentDetailProps) {
  const phase = experiment.phase;
  const isSandbox = experiment.executor_type === 'sandbox';

  const [sourceType, setSourceType] = useState<DataSourceType>('uploaded');
  const [fileName, setFileName] = useState('');
  const [filePath, setFilePath] = useState('');
  const [profileName, setProfileName] = useState('');
  const [profileConfirmed, setProfileConfirmed] = useState(false);
  const [autodetectPreview, setAutodetectPreview] = useState<Record<string, unknown> | null>(null);
  const [feedback, setFeedback] = useState(experiment.human_feedback || '');

  const canShowUpload = isSandbox && phase !== 'running' && phase !== 'completed';
  const canIterate =
    phase === 'script_designed'
    || phase === 'running'
    || (Boolean(experiment.initial_plan) && phase !== 'completed' && phase !== 'failed');

  const metricsHistory = useMemo(
    () => experiment.iterations.map((it) => ({
      n: it.iteration_number,
      accuracy: Number(it.metrics.accuracy ?? 0),
      f1: Number(it.metrics.f1 ?? 0),
    })),
    [experiment.iterations],
  );

  const autodetectBlocked =
    sourceType === 'directory'
    && profileName === 'AutoDetect'
    && !profileConfirmed;

  const buildDataConfig = (): DataConfig => {
    const path = sourceType === 'uploaded' ? (fileName || 'mock_upload.csv') : filePath.trim();
    return {
      source_type: sourceType === 'local_csv' && path.endsWith('.json') ? 'local_json' : sourceType,
      source_path: path,
      file_name: sourceType === 'uploaded' ? fileName || 'mock_upload.csv' : undefined,
      profile_name: sourceType === 'directory'
        ? (profileName === 'AutoDetect' ? 'AutoDetect' : profileName || undefined)
        : undefined,
      sample_size: 5000,
      preprocessing_steps: [],
      columns: ['id', 'feature_1', 'feature_2', 'label'],
      row_count: 4800,
    };
  };

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

        {error && (
          <div className="mb-3 p-2.5 rounded-lg border border-danger-500/30 bg-danger-500/10 text-xs text-danger-300 flex gap-2">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
            {error}
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

      {/* 推荐数据集 */}
      {isSandbox && (phase === 'created' || phase === 'data_recommended' || phase === 'data_uploaded') && (
        <Card title="推荐数据集" subtitle="AI 分析假设后的推荐（mock）">
          {!experiment.dataset_recommendations?.length ? (
            <p className="text-sm text-bp-muted mb-3">暂无推荐。可点击下方按钮让 AI 推荐，或直接上传数据。</p>
          ) : (
            <div className="space-y-3 mb-3">
              {experiment.dataset_recommendations.filter((d) => d.is_required).map((d) => (
                <div key={d.name} className="rounded-lg border border-bp-border p-3">
                  <div className="text-sm font-medium text-bp-text">{d.name}</div>
                  <p className="text-xs text-bp-muted mt-1">{d.description}</p>
                  <p className="text-xs text-bp-cyan/80 mt-1">推荐理由: {d.reason}</p>
                  {d.download_url && (
                    <a href={d.download_url} className="text-xs text-bp-cyan underline mt-1 inline-block" target="_blank" rel="noreferrer">
                      下载链接
                    </a>
                  )}
                  {d.expected_columns && (
                    <p className="text-[11px] text-bp-muted mt-1">
                      预期字段: {d.expected_columns.join(', ')}
                    </p>
                  )}
                </div>
              ))}
              {experiment.dataset_recommendations.some((d) => !d.is_required) && (
                <details className="text-xs text-bp-muted">
                  <summary className="cursor-pointer text-bp-text">可选补充数据集</summary>
                  <ul className="mt-2 space-y-1 pl-2">
                    {experiment.dataset_recommendations.filter((d) => !d.is_required).map((d) => (
                      <li key={d.name}>· {d.name}: {d.reason || d.description}</li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          )}
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

      {/* 上传数据 */}
      {canShowUpload && (
        <Card title="上传数据集" subtitle="对齐 shaxiang：缺数据不可设计脚本 / 不可迭代">
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
                选择数据文件（mock：仅记录文件名，不实际上传）
              </label>
              <input
                type="file"
                accept=".csv,.json,.jsonl,.parquet,.xlsx,.tsv"
                onChange={(e) => setFileName(e.target.files?.[0]?.name || '')}
                className="block w-full text-xs text-bp-muted file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:bg-bp-panel file:text-bp-text"
              />
              {fileName && <p className="text-xs text-bp-cyan mt-1">已选择: {fileName}</p>}
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
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={!filePath.trim() || busy}
                    onClick={() => {
                      setAutodetectPreview({
                        modality: 'tabular',
                        row_count: 5000,
                        column_count: 4,
                        numeric_columns: ['feature_1', 'feature_2'],
                        suggested_target_columns: ['label'],
                        profile: 'AutoDetect(mock)',
                      });
                      setProfileConfirmed(false);
                    }}
                  >
                    自动识别并试加载验证
                  </Button>
                  {autodetectPreview && (
                    <div className="rounded-lg border border-bp-border p-3 text-xs space-y-2">
                      <pre className="text-bp-muted whitespace-pre-wrap">
                        {JSON.stringify(autodetectPreview, null, 2)}
                      </pre>
                      <div className="flex gap-2">
                        <Button size="sm" onClick={() => setProfileConfirmed(true)}>
                          确认使用此配置
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => {
                            setAutodetectPreview(null);
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

          {(sourceType === 'local_csv' || sourceType === 'huggingface') && (
            <div className="mb-3">
              <input
                type="text"
                value={filePath}
                onChange={(e) => setFilePath(e.target.value)}
                placeholder={
                  sourceType === 'huggingface'
                    ? '例如: scikit-learn/iris'
                    : String.raw`例如: D:\data\my_dataset.csv`
                }
                className="w-full bg-bp-base border border-bp-border rounded-lg px-3 py-2 text-sm text-bp-text"
              />
            </div>
          )}

          {experiment.data_config && (
            <p className="text-xs text-bp-green mb-3">
              已绑定数据: {experiment.data_config.file_name || experiment.data_config.source_path}
              （{experiment.data_config.row_count ?? '?'} 行）
            </p>
          )}

          <Button
            className="w-full"
            disabled={
              busy
              || autodetectBlocked
              || (sourceType === 'uploaded' ? !fileName : !filePath.trim())
            }
            onClick={() => onDesignScript(buildDataConfig())}
          >
            {busy ? '设计中（生成 → 试跑 → 修补）…' : '确认并设计分析脚本'}
          </Button>
        </Card>
      )}

      {/* 迭代区 */}
      {canIterate && (
        <Card title="执行与分析" subtitle="对齐 shaxiang：smoke / 全量 · 自我纠正在脚本设计阶段完成">
          {isSandbox && (
            <div className="mb-4 p-3 rounded-lg border border-bp-border">
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
          )}

          {experiment.initial_plan && (
            <details className="mb-4 rounded-lg border border-bp-border px-3 py-2">
              <summary className="text-sm text-bp-text cursor-pointer">
                当前方案: {experiment.initial_plan.title}
              </summary>
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
          </div>

          {metricsHistory.length > 0 && (
            <div className="mb-4">
              <h5 className="text-sm font-medium text-bp-text mb-2">指标趋势（mock）</h5>
              <div className="space-y-2">
                {metricsHistory.map((m) => (
                  <div key={m.n} className="flex items-center gap-3 text-xs">
                    <span className="w-12 text-bp-muted">#{m.n}</span>
                    <div className="flex-1 h-2 rounded bg-bp-panel overflow-hidden">
                      <div
                        className="h-full bg-bp-cyan"
                        style={{ width: `${Math.round(m.accuracy * 100)}%` }}
                      />
                    </div>
                    <span className="font-mono text-bp-text w-28 text-right">
                      acc {m.accuracy.toFixed(3)} / f1 {m.f1.toFixed(3)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {experiment.iterations.length > 0 && (
            <div className="mb-4">
              <h5 className="text-sm font-medium text-bp-text mb-2">迭代历史</h5>
              <div className="space-y-3">
                {[...experiment.iterations].reverse().map((it) => (
                  <div key={it.iteration_number} className="rounded-lg border border-bp-border p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                      <span className="font-semibold text-bp-text">第 {it.iteration_number} 轮</span>
                      <span className="text-bp-muted">{it.plan.title}</span>
                      <span className={it.status === 'success' ? 'text-bp-green' : 'text-danger-300'}>
                        {it.status === 'success' ? '成功' : '失败'}
                      </span>
                      <span className="text-bp-muted">{it.duration_seconds.toFixed(1)}s</span>
                    </div>
                    <p className="text-xs text-bp-muted mt-1">{it.result.summary}</p>
                    <p className="text-xs text-bp-cyan/80 mt-1">{it.analysis.summary}</p>
                    {it.result.charts && it.result.charts.length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-2">
                        {it.result.charts.map((c) => (
                          <span
                            key={c.name}
                            className="text-[11px] px-2 py-0.5 rounded border border-bp-border text-bp-muted"
                            title={c.note}
                          >
                            📊 {c.name}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="pt-3 border-t border-bp-border">
            <h5 className="text-sm font-medium text-bp-text mb-1">人工反馈</h5>
            <p className="text-xs text-bp-muted mb-2">
              写入后进入下一轮脚本迭代；也可立即「基于反馈重新设计脚本」（对齐 shaxiang 自我纠正）。
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
          {metricsHistory.length > 0 && (
            <div className="space-y-2">
              {metricsHistory.map((m) => (
                <div key={m.n} className="text-xs font-mono text-bp-muted">
                  #{m.n} accuracy={m.accuracy.toFixed(3)} f1={m.f1.toFixed(3)}
                </div>
              ))}
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
