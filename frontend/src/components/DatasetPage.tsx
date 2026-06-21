import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Upload, Database, Table2, Image, FileJson, FileText,
  Loader2, AlertCircle, Trash2, RefreshCw,
  ChevronDown, ChevronUp, Eye, EyeOff, BarChart3, CheckCircle2,
  XCircle, Clock, Sparkles, Target, ListFilter, TrendingUp,
  Activity, Network,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { DataFinderPanel } from '@/components/DataFinderPanel';
import datasetService, { type DataContext, type ModelingResult } from '@/services/datasetService';
import type { BackendDataset, DatasetSummary } from '@/types';

interface DatasetPageProps {
  projectId: string;
  projectMode?: string;
}

const DATA_TYPE_CONFIG: Record<string, { icon: typeof Database; label: string; color: string }> = {
  tabular: { icon: Table2, label: '表格', color: 'text-blue-400' },
  image: { icon: Image, label: '图像', color: 'text-purple-400' },
  time_series: { icon: BarChart3, label: '时间序列', color: 'text-green-400' },
  json: { icon: FileJson, label: 'JSON', color: 'text-yellow-400' },
  pdf: { icon: FileText, label: 'PDF', color: 'text-red-400' },
  unknown: { icon: FileText, label: '未知', color: 'text-gray-400' },
};

const MODALITY_LABELS: Record<string, string> = {
  tabular: '表格',
  image: '图像',
  time_series: '时间序列',
  json: 'JSON',
  pdf: 'PDF',
  unknown: '未知',
};

const STATUS_CONFIG: Record<string, { icon: typeof CheckCircle2; label: string; cls: string }> = {
  completed: { icon: CheckCircle2, label: '已完成', cls: 'text-green-400 bg-green-500/10' },
  processing: { icon: RefreshCw, label: '预处理中', cls: 'text-blue-400 bg-blue-500/10' },
  pending: { icon: Clock, label: '待处理', cls: 'text-gray-400 bg-gray-500/10' },
  failed: { icon: XCircle, label: '失败', cls: 'text-red-400 bg-red-500/10' },
};

const SUPPORTED_FORMATS =
  'CSV (.csv)、Excel (.xlsx, .xls)、JSON (.json, .jsonl)、文本 (.txt)、图像 (.png, .jpg, .tiff)、时间序列 (.npy, .npz, .wav)';
const BYTES_KB = 1024;
const BYTES_MB = 1024 * 1024;

function parseJsonSafe(raw: string | undefined): unknown {
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

function toSummary(ds: BackendDataset): DatasetSummary {
  return {
    id: ds.id,
    filename: ds.filename,
    dataType: ds.data_type,
    nRows: ds.n_rows,
    nColumns: ds.n_columns,
    columns: (parseJsonSafe(ds.columns_json) as string[]) || [],
    dtypes: (parseJsonSafe(ds.dtypes_json) as Record<string, string>) || {},
    missingCount: ds.missing_count,
    missingRate: ds.missing_rate,
    statistics: (parseJsonSafe(ds.statistics_json) as Record<string, unknown>) || {},
    preview: (parseJsonSafe(ds.preview_json) as Record<string, unknown>[]) || [],
    preprocessingStatus: ds.preprocessing_status,
    useForHypothesis: ds.use_for_hypothesis,
    fileSize: ds.file_size,
    createdAt: ds.created_at,
  };
}

function formatSize(bytes?: number): string {
  if (!bytes) return '-';
  if (bytes >= BYTES_MB) return `${(bytes / BYTES_MB).toFixed(1)} MB`;
  return `${(bytes / BYTES_KB).toFixed(1)} KB`;
}

function formatQualityScore(score: number | null | undefined): { label: string; cls: string } {
  if (score == null) return { label: '-', cls: 'text-gray-500' };
  if (score >= 0.8) return { label: score.toFixed(2), cls: 'text-green-400' };
  if (score >= 0.5) return { label: score.toFixed(2), cls: 'text-yellow-400' };
  return { label: score.toFixed(2), cls: 'text-red-400' };
}

export function DatasetPage({ projectId, projectMode }: DatasetPageProps) {
  const [pageTab, setPageTab] = useState<'datasets' | 'data-finder'>('datasets');
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [dataContext, setDataContext] = useState<DataContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [alertMsg, setAlertMsg] = useState<string | null>(null);
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);
  const [modelingDatasetId, setModelingDatasetId] = useState<string>('');
  const [targetColumn, setTargetColumn] = useState<string>('');
  const [researchTask, setResearchTask] = useState<string>('');
  const [modelingLoading, setModelingLoading] = useState(false);
  const [modelingResult, setModelingResult] = useState<ModelingResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const tabularDatasets = datasets.filter((ds) => ds.dataType === 'tabular');

  const showAlert = useCallback((msg: string) => {
    setAlertMsg(msg);
    setTimeout(() => setAlertMsg(null), 3000);
  }, []);

  const loadDataContext = useCallback(() => {
    datasetService.getDataContext(projectId).then((res) => {
      if (res.code === 200 && res.data) {
        setDataContext(res.data);
      }
    }).catch(() => {/* ignore */});
  }, [projectId]);

  useEffect(() => {
    if (tabularDatasets.length > 0 && !modelingDatasetId) {
      setModelingDatasetId(tabularDatasets[0].id);
    }
  }, [tabularDatasets, modelingDatasetId]);

  useEffect(() => {
    if (!modelingDatasetId) return;
    const ds = tabularDatasets.find((d) => d.id === modelingDatasetId);
    if (!ds) return;
    const tcKeywords = ['label', 'target', 'class', 'y', 'score', 'result', 'outcome', '标签', '目标', '类别'];
    const candidates = (ds.columns || []).filter((col) =>
      tcKeywords.some((k) => col.toLowerCase().includes(k))
    );
    if (candidates.length > 0) {
      setTargetColumn(candidates[0]);
    } else {
      const cols = ds.columns || [];
      if (cols.length > 0) {
        setTargetColumn(cols[cols.length - 1]);
      }
    }
    datasetService.getModelingResult(modelingDatasetId)
      .then((res) => {
        if (res.code === 200 && res.data) setModelingResult(res.data);
      })
      .catch(() => setModelingResult(null));
  }, [modelingDatasetId, tabularDatasets]);

  const handleRunModeling = useCallback(async () => {
    if (!modelingDatasetId) {
      showAlert('请先选择表格数据集');
      return;
    }
    if (!targetColumn.trim()) {
      showAlert('请选择或输入目标变量');
      return;
    }
    setModelingLoading(true);
    try {
      const res = await datasetService.runModeling(modelingDatasetId, {
        target_column: targetColumn.trim(),
        research_task: researchTask.trim() || undefined,
      });
      if (res.code === 200 && res.data) {
        setModelingResult(res.data);
        showAlert('自动建模完成');
      } else {
        showAlert(res.message || '建模失败');
      }
    } catch (e) {
      showAlert(e instanceof Error ? e.message : '建模失败');
    } finally {
      setModelingLoading(false);
    }
  }, [modelingDatasetId, targetColumn, researchTask, showAlert]);

  const loadDatasets = useCallback(() => {
    setLoading(true);
    setError(null);
    datasetService.getProjectDatasets(projectId)
      .then((res) => {
        if (res.code === 200 && Array.isArray(res.data)) {
          setDatasets(res.data.map(toSummary));
        } else {
          setError(res.message || '获取数据集列表失败');
        }
      })
      .catch((err) => setError(err?.message || '获取数据集列表失败'))
      .finally(() => setLoading(false));
  }, [projectId]);

  const refreshAll = useCallback(() => {
    loadDatasets();
    loadDataContext();
  }, [loadDatasets, loadDataContext]);

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  const handleUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const res = await datasetService.uploadDataset(projectId, file);
      if (res.code === 200 && res.data) {
        setDatasets((prev) => [toSummary(res.data!), ...prev]);
        showAlert(`上传成功: ${file.name}，已完成初步分析`);
        loadDataContext();
      } else {
        setError(res.message || '上传失败');
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '上传失败');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }, [projectId, showAlert, loadDataContext]);

  const handlePreprocess = useCallback(async (dsId: string) => {
    try {
      const res = await datasetService.preprocessDataset(dsId);
      if (res.code === 200 && res.data) {
        setDatasets((prev) => prev.map((d) => (d.id === dsId ? toSummary(res.data!) : d)));
        showAlert('预处理完成');
        loadDataContext();
      }
    } catch {
      showAlert('预处理失败');
    }
  }, [showAlert, loadDataContext]);

  const handleQualityAnalysis = useCallback(async (dsId: string) => {
    setAnalyzingId(dsId);
    try {
      const res = await datasetService.runQualityAnalysis(dsId);
      if (res.code === 200 && res.data?.success) {
        showAlert('质量分析完成');
        loadDatasets();
        loadDataContext();
      } else {
        showAlert(res.data?.error || '质量分析失败');
      }
    } catch {
      showAlert('质量分析失败');
    } finally {
      setAnalyzingId(null);
    }
  }, [showAlert, loadDatasets, loadDataContext]);

  const handleToggleHypothesis = useCallback(async (dsId: string) => {
    try {
      const res = await datasetService.toggleHypothesisUse(dsId);
      if (res.code === 200 && res.data) {
        setDatasets((prev) => prev.map((d) => (d.id === dsId ? toSummary(res.data!) : d)));
        showAlert(res.data.use_for_hypothesis ? '已启用用于假设生成' : '已禁用用于假设生成');
        loadDataContext();
      }
    } catch {
      showAlert('操作失败');
    }
  }, [showAlert, loadDataContext]);

  const handleDelete = useCallback(async (dsId: string) => {
    if (!confirm('确认删除该数据集？此操作不可撤销。')) return;
    try {
      const res = await datasetService.deleteDataset(dsId);
      if (res.code === 200) {
        setDatasets((prev) => prev.filter((d) => d.id !== dsId));
        setExpandedId((prev) => (prev === dsId ? null : prev));
        showAlert('已删除');
        loadDataContext();
      }
    } catch {
      showAlert('删除失败');
    }
  }, [showAlert, loadDataContext]);

  return (
    <div className="max-w-7xl mx-auto">
      <div className="flex gap-2 mb-4 border-b border-dark-700">
        <button
          type="button"
          onClick={() => setPageTab('datasets')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            pageTab === 'datasets'
              ? 'border-primary-500 text-primary-300'
              : 'border-transparent text-gray-500 hover:text-gray-300'
          }`}
        >
          项目数据集
        </button>
        <button
          type="button"
          onClick={() => setPageTab('data-finder')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            pageTab === 'data-finder'
              ? 'border-primary-500 text-primary-300'
              : 'border-transparent text-gray-500 hover:text-gray-300'
          }`}
        >
          多源数据查找与整合
        </button>
      </div>

      {pageTab === 'data-finder' ? (
        <DataFinderPanel
          projectId={projectId}
          projectMode={projectMode}
          onImported={() => {
            refreshAll();
            setPageTab('datasets');
            showAlert('已加入项目数据集');
          }}
        />
      ) : (
        <>
      {/* 头部控制区 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">数据集管理</h1>
          <p className="text-gray-400 text-sm">
            上传观测数据、实验数据、临床数据等多模态数据集，用于假设生成和实验设计。支持格式: {SUPPORTED_FORMATS}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            icon={<RefreshCw className="w-4 h-4" />}
            onClick={refreshAll}
            disabled={loading}
          >
            刷新
          </Button>
          <label>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.xlsx,.xls,.json,.jsonl,.txt,.png,.jpg,.jpeg,.tiff,.npy,.npz,.wav"
              className="hidden"
              onChange={handleUpload}
              disabled={uploading}
            />
            <Button
              variant="primary"
              size="sm"
              icon={uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
            >
              {uploading ? '上传中...' : '上传数据集'}
            </Button>
          </label>
        </div>
      </div>

      {/* 项目模式 / 联邦数据识别 */}
      {(projectMode === 'federated_learning' || dataContext?.project_mode === 'federated_learning') && (
        <Card className="p-4 mb-6 border-cyan-500/20 bg-cyan-500/5">
          <div className="flex items-center gap-2 mb-3">
            <Network className="w-4 h-4 text-cyan-400" />
            <h3 className="text-sm font-semibold text-cyan-300">联邦学习数据识别</h3>
            <span className="text-[10px] px-1.5 py-0.5 rounded border border-cyan-500/30 text-cyan-400">
              Federated Learning Scientist
            </span>
          </div>
          {dataContext?.fl_context ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 text-xs">
              <div>
                <span className="text-gray-500">FL 类型</span>
                <p className="text-white font-mono mt-0.5">{dataContext.fl_context.fl_setting || 'unknown'}</p>
              </div>
              <div>
                <span className="text-gray-500">检测字段</span>
                <p className="text-gray-300 mt-0.5">
                  {(dataContext.fl_context.detected_fields || []).join(', ') || '暂无'}
                </p>
              </div>
              <div>
                <span className="text-gray-500">指标字段</span>
                <p className="text-gray-300 mt-0.5">
                  {(dataContext.fl_context.metrics_fields || []).join(', ') || '暂无'}
                </p>
              </div>
              <div>
                <span className="text-gray-500">客户端字段</span>
                <p className="text-gray-300 mt-0.5">
                  {(dataContext.fl_context.client_fields || []).join(', ') || '暂无'}
                </p>
              </div>
              <div>
                <span className="text-gray-500">参与方字段</span>
                <p className="text-gray-300 mt-0.5">
                  {(dataContext.fl_context.party_fields || []).join(', ') || '暂无'}
                </p>
              </div>
              <div>
                <span className="text-gray-500">目标候选</span>
                <p className="text-gray-300 mt-0.5">
                  {(dataContext.fl_context.target_candidates || dataContext.target_candidates || []).join(', ') || '暂无'}
                </p>
              </div>
            </div>
          ) : (
            <p className="text-xs text-gray-500">
              请上传含 method、non_iid_degree、global_accuracy、f1_score、communication_cost_mb、client_drift 等列的 CSV
            </p>
          )}
        </Card>
      )}

      {/* 数据上下文摘要 */}
      {dataContext && dataContext.dataset_count > 0 && (
        <Card className="p-4 mb-6">
          <div className="flex items-center gap-6 flex-wrap">
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4 text-primary-400" />
              <span className="text-sm text-gray-300">
                <strong className="text-white">{dataContext.dataset_count}</strong> 个数据集
              </span>
            </div>
            {dataContext.available_modalities.length > 0 && (
              <div className="flex items-center gap-2">
                <ListFilter className="w-4 h-4 text-purple-400" />
                <span className="text-sm text-gray-400">
                  模态: {dataContext.available_modalities.map((m) => MODALITY_LABELS[m] || m).join('、')}
                </span>
              </div>
            )}
            {dataContext.field_candidates.length > 0 && (
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-green-400" />
                <span className="text-sm text-gray-400">
                  <strong className="text-white">{dataContext.field_candidates.length}</strong> 个可用字段
                </span>
              </div>
            )}
            {dataContext.target_candidates.length > 0 && (
              <div className="flex items-center gap-2">
                <Target className="w-4 h-4 text-yellow-400" />
                <span className="text-sm text-gray-400">
                  <strong className="text-white">{dataContext.target_candidates.length}</strong> 个目标候选
                </span>
              </div>
            )}
            {dataContext.quality_summary && typeof dataContext.quality_summary === 'object' && (
              <div className="flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-blue-400" />
                {formatQualityScore((dataContext.quality_summary as Record<string, unknown>)?.overall_score as number | null).label !== '-' ? (
                  <span className={`text-sm ${formatQualityScore((dataContext.quality_summary as Record<string, unknown>)?.overall_score as number | null).cls}`}>
                    综合质量: {formatQualityScore((dataContext.quality_summary as Record<string, unknown>)?.overall_score as number | null).label}
                  </span>
                ) : (
                  <span className="text-sm text-gray-500">质量: 待分析</span>
                )}
              </div>
            )}
          </div>
          {dataContext.warnings.length > 0 && (
            <div className="mt-3 pt-3 border-t border-gray-800">
              {dataContext.warnings.map((w, i) => (
                <div key={i} className="text-xs text-yellow-400/80 flex items-center gap-1">
                  <AlertCircle className="w-3 h-3" />
                  {w}
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* 数据建模与自校正 */}
      {!loading && tabularDatasets.length > 0 && (
        <Card className="p-5 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-5 h-5 text-primary-400" />
            <h3 className="text-base font-semibold text-white">数据建模与自校正</h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">数据集</label>
              <select
                value={modelingDatasetId}
                onChange={(e) => {
                  setModelingDatasetId(e.target.value);
                  setTargetColumn('');
                  setModelingResult(null);
                }}
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200"
              >
                {tabularDatasets.map((ds) => (
                  <option key={ds.id} value={ds.id}>{ds.filename}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">目标变量</label>
              <select
                value={targetColumn}
                onChange={(e) => setTargetColumn(e.target.value)}
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200"
              >
                <option value="">请选择目标列</option>
                {(tabularDatasets.find((d) => d.id === modelingDatasetId)?.columns || []).map((col) => (
                  <option key={col} value={col}>{col}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="mb-4">
            <label className="text-xs text-gray-500 mb-1 block">研究任务（可选）</label>
            <input
              value={researchTask}
              onChange={(e) => setResearchTask(e.target.value)}
              placeholder="例如：预测疾病分类 / 估计指标回归"
              className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200"
            />
          </div>

          <Button
            variant="primary"
            size="sm"
            icon={modelingLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            onClick={handleRunModeling}
            disabled={modelingLoading}
          >
            {modelingLoading ? '建模中...' : '运行自动建模'}
          </Button>

          {modelingResult?.success && (
            <div className="mt-5 space-y-4 border-t border-gray-800 pt-4">
              {modelingResult.is_pilot_validation && (
                <div className="text-xs text-yellow-400 bg-yellow-500/10 border border-yellow-500/20 rounded-lg px-3 py-2">
                  Pilot Validation：样本量较小，结果仅用于可行性验证，不得夸大为最终结论。
                </div>
              )}

              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                <div className="bg-gray-900/70 rounded-lg p-2">
                  <div className="text-gray-500 text-xs">任务类型</div>
                  <div className="text-white font-medium">{modelingResult.task_type}</div>
                </div>
                <div className="bg-gray-900/70 rounded-lg p-2">
                  <div className="text-gray-500 text-xs">目标变量</div>
                  <div className="text-white font-medium">{modelingResult.target_column}</div>
                </div>
                <div className="bg-gray-900/70 rounded-lg p-2">
                  <div className="text-gray-500 text-xs">最佳模型</div>
                  <div className="text-primary-300 font-medium">{modelingResult.best_model}</div>
                </div>
                <div className="bg-gray-900/70 rounded-lg p-2">
                  <div className="text-gray-500 text-xs">样本规模</div>
                  <div className="text-white font-medium">
                    {String((modelingResult.profile as { n_rows?: number })?.n_rows ?? '-')}
                  </div>
                </div>
              </div>

              {modelingResult.profile && (
                <div>
                  <div className="text-xs text-gray-500 mb-2">数据概览</div>
                  <div className="text-xs text-gray-400 grid grid-cols-2 md:grid-cols-4 gap-2">
                    <span>字段数: {String((modelingResult.profile as { n_columns?: number }).n_columns ?? '-')}</span>
                    <span>缺失率: {(((modelingResult.profile as { missing_rate?: number }).missing_rate ?? 0) * 100).toFixed(1)}%</span>
                    <span>目标候选: {((modelingResult.profile as { target_candidates?: string[] }).target_candidates || []).length}</span>
                    <span>异常提示: {((modelingResult.profile as { outlier_hints?: string[] }).outlier_hints || []).length}</span>
                  </div>
                </div>
              )}

              {modelingResult.models?.length > 0 && (
                <div>
                  <div className="text-xs text-gray-500 mb-2">模型指标</div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-gray-500 border-b border-gray-800">
                          <th className="text-left py-1 pr-2">模型</th>
                          <th className="text-right py-1 px-1">accuracy</th>
                          <th className="text-right py-1 px-1">f1</th>
                          <th className="text-right py-1 px-1">r2</th>
                          <th className="text-right py-1 px-1">rmse</th>
                        </tr>
                      </thead>
                      <tbody>
                        {modelingResult.models.map((m) => (
                          <tr key={m.model_name} className={`border-b border-gray-800/50 ${m.model_name === modelingResult.best_model ? 'text-primary-300' : 'text-gray-300'}`}>
                            <td className="py-1 pr-2 font-mono">{m.model_name}</td>
                            <td className="text-right py-1 px-1">{m.metrics.accuracy ?? '-'}</td>
                            <td className="text-right py-1 px-1">{m.metrics.f1 ?? '-'}</td>
                            <td className="text-right py-1 px-1">{m.metrics.r2 ?? '-'}</td>
                            <td className="text-right py-1 px-1">{m.metrics.rmse ?? '-'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {modelingResult.self_correction_suggestions?.length > 0 && (
                <div>
                  <div className="text-xs text-gray-500 mb-2">自校正建议</div>
                  <div className="space-y-2">
                    {modelingResult.self_correction_suggestions.map((item, idx) => (
                      <div key={idx} className="text-xs bg-gray-900/60 border border-gray-800 rounded-lg p-2">
                        <div className="text-yellow-300">{item.reason}</div>
                        <div className="text-gray-300 mt-1">{item.suggestion}</div>
                        <div className="text-gray-500 mt-1">下一步: {item.next_action}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {modelingResult.charts?.length > 0 && (
                <div>
                  <div className="text-xs text-gray-500 mb-2">图表</div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {modelingResult.charts.map((chart) => (
                      chart.base64 ? (
                        <div key={chart.plot_id} className="bg-gray-900/60 rounded-lg p-2">
                          <div className="text-xs text-gray-400 mb-2">{chart.title}</div>
                          <img
                            src={`data:image/png;base64,${chart.base64}`}
                            alt={chart.title}
                            className="w-full rounded border border-gray-800"
                          />
                        </div>
                      ) : null
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </Card>
      )}

      {alertMsg && (
        <div className="mb-4 px-4 py-2.5 rounded-lg bg-primary-500/10 border border-primary-500/20 text-sm text-primary-300">
          {alertMsg}
        </div>
      )}

      {loading && (
        <div className="flex flex-col items-center justify-center py-20 text-gray-400">
          <Loader2 className="w-8 h-8 animate-spin mb-3 text-primary-400" />
          <p className="text-sm">加载数据集...</p>
        </div>
      )}

      {!loading && error && (
        <div className="flex flex-col items-center justify-center py-20 text-gray-400">
          <AlertCircle className="w-8 h-8 mb-3 text-red-400" />
          <p className="text-sm text-red-400 mb-2">{error}</p>
        </div>
      )}

      {/* 空状态 */}
      {!loading && !error && datasets.length === 0 && (
        <Card className="p-12">
          <div className="flex flex-col items-center justify-center text-center">
            <Database className="w-14 h-14 text-gray-600 mb-5" />
            <h3 className="text-lg font-semibold text-gray-300 mb-3">暂无数据集</h3>
            <p className="text-sm text-gray-500 max-w-lg mb-4">
              请上传 CSV、Excel、JSON、图像或时间序列数据，以增强假设生成的可验证性。
            </p>
            <p className="text-xs text-gray-600 mb-5">支持格式: {SUPPORTED_FORMATS}</p>
            <label>
              <input
                type="file"
                accept=".csv,.xlsx,.xls,.json,.jsonl,.txt,.png,.jpg,.jpeg,.tiff,.npy,.npz,.wav"
                className="hidden"
                onChange={handleUpload}
                disabled={uploading}
              />
              <Button
                variant="primary"
                size="md"
                icon={uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
              >
                {uploading ? '上传中...' : '上传数据集'}
              </Button>
            </label>
          </div>
        </Card>
      )}

      {/* 数据集卡片列表 */}
      {!loading && !error && datasets.length > 0 && (
        <div className="grid gap-4 grid-cols-1 lg:grid-cols-2">
          {datasets.map((ds) => {
            const dtConfig = DATA_TYPE_CONFIG[ds.dataType] || DATA_TYPE_CONFIG.unknown;
            const stConfig = STATUS_CONFIG[ds.preprocessingStatus] || STATUS_CONFIG.pending;
            const isExpanded = expandedId === ds.id;
            const StatusIcon = stConfig.icon;
            const TypeIcon = dtConfig.icon;
            const qScore = formatQualityScore(ds.missingRate != null ? 1 - ds.missingRate : null);

            return (
              <Card key={ds.id}>
                {/* 头部：文件名、类型、状态 */}
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className={`w-9 h-9 rounded-lg flex items-center justify-center bg-gray-800 border border-gray-700 ${dtConfig.color}`}>
                      <TypeIcon className="w-4 h-4" />
                    </div>
                    <div className="min-w-0">
                      <h3 className="text-sm font-semibold text-white truncate">{ds.filename}</h3>
                      <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                        <span className="text-[11px] text-gray-500">{dtConfig.label}</span>
                        <span className={`text-[11px] px-1.5 py-0.5 rounded flex items-center gap-1 ${stConfig.cls}`}>
                          <StatusIcon className="w-3 h-3" />
                          {stConfig.label}
                        </span>
                        {ds.useForHypothesis ? (
                          <span className="text-[11px] text-green-400 bg-green-500/10 px-1.5 py-0.5 rounded flex items-center gap-1">
                            <Eye className="w-3 h-3" />
                            用于假设
                          </span>
                        ) : (
                          <span className="text-[11px] text-gray-500 bg-gray-700/50 px-1.5 py-0.5 rounded flex items-center gap-1">
                            <EyeOff className="w-3 h-3" />
                            已排除
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <span className="text-[11px] text-gray-600 shrink-0">{formatSize(ds.fileSize)}</span>
                </div>

                {/* 核心指标 */}
                <div className="grid grid-cols-4 gap-2 mb-2">
                  <div className="text-center p-1.5 rounded bg-gray-800/50">
                    <div className="text-lg font-bold font-mono text-white">{ds.nRows ?? '-'}</div>
                    <div className="text-[10px] text-gray-500">样本数</div>
                  </div>
                  <div className="text-center p-1.5 rounded bg-gray-800/50">
                    <div className="text-lg font-bold font-mono text-white">{ds.nColumns ?? '-'}</div>
                    <div className="text-[10px] text-gray-500">字段数</div>
                  </div>
                  <div className="text-center p-1.5 rounded bg-gray-800/50">
                    <div className="text-lg font-bold font-mono text-white">
                      {ds.missingRate != null ? `${(ds.missingRate * 100).toFixed(1)}%` : '-'}
                    </div>
                    <div className="text-[10px] text-gray-500">缺失率</div>
                  </div>
                  <div className="text-center p-1.5 rounded bg-gray-800/50">
                    <div className={`text-lg font-bold font-mono ${qScore.cls}`}>
                      {qScore.label}
                    </div>
                    <div className="text-[10px] text-gray-500">质量分</div>
                  </div>
                </div>

                {/* 展开详情 */}
                {isExpanded && (
                  <div className="mt-2 pt-3 border-t border-gray-800 space-y-3 animate-fade-in">
                    {/* 字段列表 */}
                    {ds.columns && ds.columns.length > 0 && (
                      <div>
                        <div className="text-xs text-gray-500 mb-1.5 flex items-center gap-1">
                          <ListFilter className="w-3 h-3" />
                          字段列表 ({ds.columns.length})
                        </div>
                        <div className="flex flex-wrap gap-1">
                          {ds.columns.map((col) => (
                            <span key={col} className="text-[10px] font-mono bg-gray-800 text-gray-300 px-1.5 py-0.5 rounded">
                              {col}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 目标变量候选 */}
                    {(() => {
                      const targetCandidates: Set<string> = new Set();
                      const tcKeywords = ['label', 'target', 'class', 'y', 'accuracy', 'score', 'result', 'outcome', '行为', '类别', '标签', '准确率', '评分', '目标', '结果', '分类', 'diagnosis', 'prognosis', 'response', 'status', 'flag'];
                      (ds.columns || []).forEach((col) => {
                        const colL = col.toLowerCase();
                        if (tcKeywords.some((k) => colL.includes(k))) {
                          targetCandidates.add(col);
                        }
                      });
                      if (targetCandidates.size === 0) return null;
                      return (
                        <div>
                          <div className="text-xs text-gray-500 mb-1.5 flex items-center gap-1">
                            <Target className="w-3 h-3 text-yellow-400" />
                            目标变量候选 ({targetCandidates.size})
                          </div>
                          <div className="flex flex-wrap gap-1">
                            {Array.from(targetCandidates).map((col) => (
                              <span key={col} className="text-[10px] font-mono bg-yellow-500/10 text-yellow-300 border border-yellow-500/20 px-1.5 py-0.5 rounded">
                                {col}
                              </span>
                            ))}
                          </div>
                        </div>
                      );
                    })()}

                    {/* 数值字段候选 */}
                    {(() => {
                      const numCols = (ds.columns || []).filter((col) => {
                        const dt = ds.dtypes?.[col];
                        return dt && /int|float|num|real|double/i.test(String(dt));
                      });
                      if (numCols.length === 0) return null;
                      return (
                        <div>
                          <div className="text-xs text-gray-500 mb-1.5 flex items-center gap-1">
                            <BarChart3 className="w-3 h-3 text-blue-400" />
                            数值字段 ({numCols.length})
                          </div>
                          <div className="flex flex-wrap gap-1">
                            {numCols.map((col) => (
                              <span key={col} className="text-[10px] bg-blue-500/10 text-blue-300 px-1.5 py-0.5 rounded">
                                {col}
                              </span>
                            ))}
                          </div>
                        </div>
                      );
                    })()}

                    {/* 数据类型映射 */}
                    {ds.dtypes && Object.keys(ds.dtypes).length > 0 && (
                      <div>
                        <div className="text-xs text-gray-500 mb-1.5">字段类型</div>
                        <div className="flex flex-wrap gap-1">
                          {Object.entries(ds.dtypes).map(([col, dt]) => (
                            <span key={col} className="text-[10px] bg-blue-500/10 text-blue-300 px-1.5 py-0.5 rounded">
                              {col}: {dt}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 统计信息 */}
                    {ds.statistics && Object.keys(ds.statistics as object).length > 0 && (
                      <div>
                        <div className="text-xs text-gray-500 mb-1.5">数值列统计</div>
                        <div className="overflow-x-auto">
                          <table className="w-full text-[11px]">
                            <thead>
                              <tr className="text-gray-500">
                                <th className="text-left font-normal px-1">列名</th>
                                <th className="text-right font-normal px-1">均值</th>
                                <th className="text-right font-normal px-1">标准差</th>
                                <th className="text-right font-normal px-1">最小</th>
                                <th className="text-right font-normal px-1">最大</th>
                                <th className="text-right font-normal px-1">缺失</th>
                              </tr>
                            </thead>
                            <tbody>
                              {(Object.entries(ds.statistics as Record<string, Record<string, unknown>>)).slice(0, 6).map(([col, stats]) => (
                                <tr key={col} className="border-t border-gray-800">
                                  <td className="px-1 py-0.5 font-mono text-gray-300">{col}</td>
                                  <td className="px-1 py-0.5 text-right text-gray-400">{stats.mean != null ? String(stats.mean).slice(0, 8) : '-'}</td>
                                  <td className="px-1 py-0.5 text-right text-gray-400">{stats.std != null ? String(stats.std).slice(0, 8) : '-'}</td>
                                  <td className="px-1 py-0.5 text-right text-gray-400">{stats.min != null ? String(stats.min).slice(0, 8) : '-'}</td>
                                  <td className="px-1 py-0.5 text-right text-gray-400">{stats.max != null ? String(stats.max).slice(0, 8) : '-'}</td>
                                  <td className="px-1 py-0.5 text-right text-gray-400">{String(stats.missing ?? '-')}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* 数据预览 */}
                    {ds.preview && ds.preview.length > 0 && (
                      <div>
                        <div className="text-xs text-gray-500 mb-1.5">数据预览（前 {Math.min(ds.preview.length, 5)} 行）</div>
                        <div className="overflow-x-auto max-h-32">
                          <pre className="text-[10px] font-mono text-gray-400 bg-gray-800/50 p-2 rounded whitespace-pre-wrap">
                            {JSON.stringify(ds.preview.slice(0, 5), null, 2)}
                          </pre>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* 操作按钮 */}
                <div className="flex items-center gap-2 pt-2 border-t border-gray-800 flex-wrap">
                  <button
                    onClick={() => setExpandedId(isExpanded ? null : ds.id)}
                    className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300 transition-colors"
                  >
                    {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    {isExpanded ? '收起详情' : '展开详情'}
                  </button>
                  <span className="flex-1" />
                  {ds.preprocessingStatus !== 'completed' && ds.preprocessingStatus !== 'processing' && (
                    <Button variant="secondary" size="sm" icon={<RefreshCw className="w-3.5 h-3.5" />}
                      onClick={() => handlePreprocess(ds.id)}>
                      预处理
                    </Button>
                  )}
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={analyzingId === ds.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                    onClick={() => handleQualityAnalysis(ds.id)}
                    disabled={analyzingId === ds.id}
                  >
                    质量分析
                  </Button>
                  <Button variant="secondary" size="sm"
                    icon={ds.useForHypothesis ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                    onClick={() => handleToggleHypothesis(ds.id)}>
                    {ds.useForHypothesis ? '排除' : '用于假设'}
                  </Button>
                  <Button variant="secondary" size="sm" icon={<Trash2 className="w-3.5 h-3.5 text-red-400" />}
                    onClick={() => handleDelete(ds.id)}>
                    删除
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      )}
        </>
      )}
    </div>
  );
}