import { useState, useCallback, useEffect } from 'react';
import { FlaskConical, Loader2, CheckCircle, AlertCircle, Scale, Brain, MessageSquare, Trash2, Clock, ChevronDown, ChevronRight } from 'lucide-react';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { reportService, type EvaluationRecord } from '@/services/reportService';

// ── 类型定义 ────────────────────────────────────────────────────
interface EvaluationResult {
  mode: string;
  composite: number;
  reason: string;
  error?: string;
  [key: string]: unknown;
}

interface ModeConfig {
  key: 'simple' | 'weighted' | 'scientist';
  label: string;
  description: string;
  icon: React.ReactNode;
  color: string;
}

const MODES: ModeConfig[] = [
  {
    key: 'simple',
    label: '简单提交评估',
    description: '不加额外提示词，直接请求 LLM 客观评估',
    icon: <MessageSquare className="w-4 h-4" />,
    color: 'text-blue-400 border-blue-500/40',
  },
  {
    key: 'weighted',
    label: '客观加权评分',
    description: '按七层 rubric（选题/方法/证据/诚实度等）机械算分，公平可复现',
    icon: <Scale className="w-4 h-4" />,
    color: 'text-emerald-400 border-emerald-500/40',
  },
  {
    key: 'scientist',
    label: '科学家评分',
    description: 'LLM 扮演人类科学家（PI），带学术偏好和"人情味"打分',
    icon: <Brain className="w-4 h-4" />,
    color: 'text-purple-400 border-purple-500/40',
  },
];

const MODE_LABELS: Record<string, string> = {
  simple: '简单提交',
  weighted: '客观加权',
  scientist: '科学家',
};

const MODE_COLORS: Record<string, string> = {
  simple: 'text-blue-400',
  weighted: 'text-emerald-400',
  scientist: 'text-purple-400',
};

const MODE_BORDER_COLORS: Record<string, string> = {
  simple: 'border-blue-500/40',
  weighted: 'border-emerald-500/40',
  scientist: 'border-purple-500/40',
};

// ── 子组件：模式选择 ────────────────────────────────────────────
function ModeSelector({
  modes,
  selected,
  onChange,
  disabled,
}: {
  modes: ModeConfig[];
  selected: string;
  onChange: (key: 'simple' | 'weighted' | 'scientist') => void;
  disabled: boolean;
}) {
  return (
    <div className="space-y-2">
      {modes.map((mode) => {
        const isSelected = selected === mode.key;
        return (
          <button
            key={mode.key}
            disabled={disabled}
            onClick={() => onChange(mode.key)}
            className={`w-full flex items-start gap-3 p-3 rounded-lg border text-left transition-all ${
              isSelected
                ? `${mode.color} bg-opacity-10`
                : 'border-bp-border/30 hover:border-bp-border/60'
            } ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
          >
            <span className={`mt-0.5 shrink-0 ${isSelected ? mode.color : 'text-bp-muted'}`}>
              {mode.icon}
            </span>
            <div className="flex-1 min-w-0">
              <div className={`text-sm font-medium ${isSelected ? 'text-bp-text' : 'text-bp-muted'}`}>
                {mode.label}
              </div>
              <div className="text-xs text-bp-muted/70 mt-0.5">{mode.description}</div>
            </div>
            <div
              className={`shrink-0 w-4 h-4 rounded-full border-2 mt-0.5 ${
                isSelected
                  ? `${mode.color} bg-current`
                  : 'border-bp-muted/40'
              }`}
            />
          </button>
        );
      })}
    </div>
  );
}

// ── 子组件：评分条 ──────────────────────────────────────────────
function ScoreBar({ label, score, maxScore = 100, color }: { label: string; score: number; maxScore?: number; color: string }) {
  const pct = Math.min(100, Math.max(0, (score / maxScore) * 100));
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-20 text-bp-muted shrink-0">{label}</span>
      <div className="flex-1 h-2 bg-bp-border/20 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-500 ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 text-right font-mono text-bp-text">{Math.round(score)}</span>
    </div>
  );
}

function SimpleResult({ result }: { result: EvaluationResult }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-2xl font-bold text-bp-text">{Math.round(result.composite)}</span>
        <span className="text-xs text-bp-muted">/ 100</span>
      </div>
      {result.reason && <p className="text-sm text-bp-text/80">{result.reason}</p>}
    </div>
  );
}

function WeightedResult({ result }: { result: EvaluationResult }) {
  const layers = ['L0', 'L1', 'L2', 'L3', 'L4', 'L5', 'L6'] as const;
  const labels: Record<string, string> = { L0: '类型识别', L1: '形式合规', L2: '选题与问题', L3: '方法学', L4: '证据强度', L5: '诚实度', L6: '可用性' };
  const colors: Record<string, string> = { L0: 'bg-blue-400', L1: 'bg-cyan-400', L2: 'bg-emerald-400', L3: 'bg-green-400', L4: 'bg-amber-400', L5: 'bg-orange-400', L6: 'bg-rose-400' };
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-2xl font-bold text-bp-text">{Math.round(result.composite)}</span>
        <span className="text-xs text-bp-muted">/ 100（综合分）</span>
      </div>
      {layers.map((k) => {
        const v = result[k] as number | undefined;
        if (v == null) return null;
        return <ScoreBar key={k} label={`${k} ${labels[k]}`} score={v} color={colors[k]} />;
      })}
      {result.reason && <p className="text-sm text-bp-text/80 mt-2">{result.reason}</p>}
    </div>
  );
}

function ScientistResult({ result }: { result: EvaluationResult }) {
  const dims = ['选题价值', '方法恰当性', '证据强度', '贡献清晰度', '表达与诚实度'] as const;
  const dimColors: Record<string, string> = { '选题价值': 'bg-purple-400', '方法恰当性': 'bg-violet-400', '证据强度': 'bg-fuchsia-400', '贡献清晰度': 'bg-pink-400', '表达与诚实度': 'bg-rose-400' };
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-2xl font-bold text-bp-text">{Math.round(result.composite)}</span>
        <span className="text-xs text-bp-muted">/ 100（总分）</span>
      </div>
      {dims.map((k) => {
        const v = result[k] as number | undefined;
        if (v == null) return null;
        return <ScoreBar key={k} label={k} score={v} color={dimColors[k]} />;
      })}
      {result['主要扣分点'] ? (
        <div className="mt-2 text-xs text-bp-muted">
          <span className="text-bp-muted/70">主要扣分点：</span>
          {String(result['主要扣分点'])}
        </div>
      ) : null}
      {result.reason && <p className="text-sm text-bp-text/80 mt-2">{result.reason}</p>}
    </div>
  );
}

function renderResultContent(result: EvaluationResult) {
  if (result.error) {
    return (
      <div className="flex items-center gap-2 text-red-400 text-sm">
        <AlertCircle className="w-4 h-4" />
        {result.error}
      </div>
    );
  }
  switch (result.mode) {
    case 'simple': return <SimpleResult result={result} />;
    case 'weighted': return <WeightedResult result={result} />;
    case 'scientist': return <ScientistResult result={result} />;
    default: return <SimpleResult result={result} />;
  }
}

// ── 对战对比 ─────────────────────────────────────────────────────
function BattleComparison({ results }: { results: { mode: string; composite: number }[] }) {
  if (results.length < 2) return null;
  const sorted = [...results].sort((a, b) => b.composite - a.composite);
  const maxDiff = Math.max(...sorted.map((r) => r.composite)) - Math.min(...sorted.map((r) => r.composite));
  return (
    <div className="mt-4 pt-3 border-t border-bp-border/30">
      <div className="text-xs text-bp-muted mb-2">
        模型对战 &middot; 最大分差 <span className="text-bp-text font-mono">{Math.round(maxDiff)}</span> 分
        {maxDiff >= 10 && <span className="text-amber-400 ml-1">（分歧较大，建议重点审阅）</span>}
      </div>
      <div className="space-y-1.5">
        {sorted.map((r) => (
          <div key={r.mode} className="flex items-center gap-2 text-xs">
            <span className={`w-16 shrink-0 ${MODE_COLORS[r.mode] || 'text-bp-muted'}`}>
              {MODE_LABELS[r.mode] || r.mode}
            </span>
            <div className="flex-1 h-1.5 bg-bp-border/20 rounded-full overflow-hidden">
              <div className={`h-full rounded-full ${MODE_COLORS[r.mode] || 'bg-bp-muted'}`} style={{ width: `${Math.min(100, r.composite)}%` }} />
            </div>
            <span className="w-8 text-right font-mono text-bp-text">{Math.round(r.composite)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── 历史记录条目 ────────────────────────────────────────────────
function HistoryItem({
  record,
  onDelete,
}: {
  record: EvaluationRecord;
  onDelete: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const result = record.result as unknown as EvaluationResult;
  const time = record.created_at ? new Date(record.created_at).toLocaleString('zh-CN') : '';

  return (
    <div className={`border-l-2 ${MODE_BORDER_COLORS[record.mode] || 'border-bp-border/30'} pl-3 py-2`}>
      <div className="flex items-center gap-2 mb-1">
        <span className={`text-xs font-medium ${MODE_COLORS[record.mode] || 'text-bp-muted'}`}>
          {MODE_LABELS[record.mode] || record.mode}
        </span>
        <span className="text-[10px] text-bp-muted/60 flex items-center gap-1">
          <Clock className="w-2.5 h-2.5" />
          {time}
        </span>
        <div className="ml-auto flex items-center gap-1">
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-bp-muted/50 hover:text-bp-muted transition-colors"
            title={expanded ? '收起' : '展开详情'}
          >
            {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          </button>
          <button
            onClick={() => onDelete(record.id)}
            className="text-bp-muted/50 hover:text-red-400 transition-colors"
            title="删除此条记录"
          >
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
      </div>
      {expanded && renderResultContent(result)}
      {!expanded && (
        <div className="flex items-center gap-2 text-xs text-bp-text">
          <span className="font-mono">{Math.round(result.composite)}</span>
          <span className="text-bp-muted/60">/ 100</span>
          {result.reason && <span className="text-bp-muted/70 truncate max-w-[200px]">· {result.reason}</span>}
        </div>
      )}
    </div>
  );
}

// ── 主组件 ───────────────────────────────────────────────────────
interface ReportQualityEvaluationCardProps {
  reportId: string;
  projectId: string;
}

export function ReportQualityEvaluationCard({ reportId }: ReportQualityEvaluationCardProps) {
  const [selectedMode, setSelectedMode] = useState<'simple' | 'weighted' | 'scientist'>('simple');
  const [results, setResults] = useState<EvaluationResult[]>([]);
  const [history, setHistory] = useState<EvaluationRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);

  // 加载历史记录
  const loadHistory = useCallback(async () => {
    setLoadingHistory(true);
    try {
      const res = await reportService.getEvaluations(reportId);
      if (res?.code === 200 && res?.data) {
        setHistory(res.data);
      }
    } catch {
      // 静默失败
    } finally {
      setLoadingHistory(false);
    }
  }, [reportId]);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  const handleEvaluate = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await reportService.evaluate(reportId, selectedMode);
      if (res?.code === 200 && res?.data) {
        const newResult = res.data as unknown as EvaluationResult;
        setResults((prev) => [...prev.filter((r) => r.mode !== selectedMode), newResult]);
        // 刷新历史记录
        void loadHistory();
      } else {
        setError(res?.message || '评估失败');
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [reportId, selectedMode, loadHistory]);

  const handleEvaluateAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    for (const mode of ['simple', 'weighted', 'scientist'] as const) {
      try {
        const res = await reportService.evaluate(reportId, mode);
        if (res?.code === 200 && res?.data) {
          setResults((prev) => [...prev.filter((r) => r.mode !== mode), res.data as unknown as EvaluationResult]);
        }
      } catch {
        // 单个模式失败不影响其他
      }
    }
    void loadHistory();
    setLoading(false);
  }, [reportId, loadHistory]);

  const handleDeleteEvaluation = useCallback(async (evalId: string) => {
    try {
      await reportService.deleteEvaluation(reportId, evalId);
      setHistory((prev) => prev.filter((h) => h.id !== evalId));
    } catch {
      // 静默失败
    }
  }, [reportId]);

  return (
    <Card className="mt-4">
      <div className="p-4">
        {/* 标题 */}
        <div className="flex items-center gap-2 mb-3">
          <FlaskConical className="w-4 h-4 text-bp-cyan" />
          <span className="text-sm font-medium text-bp-text">报告质量评估（模型对战）</span>
        </div>

        {/* 模式选择 */}
        <ModeSelector modes={MODES} selected={selectedMode} onChange={setSelectedMode} disabled={loading} />

        {/* 错误提示 */}
        {error && (
          <div className="mt-3 flex items-center gap-2 text-red-400 text-xs bg-red-500/10 px-3 py-2 rounded">
            <AlertCircle className="w-3.5 h-3.5 shrink-0" />
            {error}
          </div>
        )}

        {/* 操作按钮 */}
        <div className="mt-3 flex items-center gap-2">
          <Button
            variant="primary"
            size="sm"
            icon={loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : undefined}
            onClick={handleEvaluate}
            disabled={loading}
          >
            {loading ? '评估中...' : '开始评估'}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            icon={loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FlaskConical className="w-3.5 h-3.5" />}
            onClick={handleEvaluateAll}
            disabled={loading}
          >
            三种模式全部运行
          </Button>
        </div>

        {/* 评估结果 */}
        {results.length > 0 && (
          <div className="mt-4 space-y-3">
            {results.map((result) => (
              <div
                key={result.mode}
                className={`border-l-2 ${MODE_BORDER_COLORS[result.mode] || 'border-bp-border/30'} pl-3 py-2`}
              >
                <div className="flex items-center gap-2 mb-1">
                  {result.error ? (
                    <AlertCircle className="w-3.5 h-3.5 text-red-400" />
                  ) : (
                    <CheckCircle className="w-3.5 h-3.5 text-green-400" />
                  )}
                  <span className="text-xs font-medium text-bp-muted">
                    {MODES.find((m) => m.key === result.mode)?.label || result.mode}
                  </span>
                </div>
                {renderResultContent(result)}
              </div>
            ))}
            <BattleComparison results={results} />
          </div>
        )}

        {/* ── 历史记录 ── */}
        <div className="mt-4 pt-3 border-t border-bp-border/30">
          <button
            onClick={() => setHistoryOpen(!historyOpen)}
            className="flex items-center gap-2 text-xs text-bp-muted hover:text-bp-text transition-colors"
          >
            {historyOpen ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            <Clock className="w-3 h-3" />
            <span>评估历史记录</span>
            {loadingHistory ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <span className="text-bp-muted/60">({history.length})</span>
            )}
          </button>

          {historyOpen && (
            <div className="mt-2 space-y-2">
              {history.length === 0 ? (
                <p className="text-xs text-bp-muted/60 py-2 text-center">暂无评估记录</p>
              ) : (
                history.map((record) => (
                  <HistoryItem key={record.id} record={record} onDelete={handleDeleteEvaluation} />
                ))
              )}
              {/* 历史记录中的对战对比 */}
              {history.length >= 2 && (
                <BattleComparison
                  results={Array.from(
                    // 每种模式取最新一条
                    history
                      .filter((h) => {
                        const r = h.result as unknown as EvaluationResult;
                        return typeof r.composite === 'number';
                      })
                      .reduce<Map<string, { mode: string; composite: number }>>((map, h) => {
                        map.set(h.mode, {
                          mode: h.mode,
                          composite: (h.result as unknown as EvaluationResult).composite || 0,
                        });
                        return map;
                      }, new Map())
                      .values()
                  )}
                />
              )}
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}