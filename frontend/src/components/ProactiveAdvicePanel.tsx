import { useState, useEffect, useCallback } from 'react';
import { Brain, AlertTriangle, AlertCircle, Info, Sparkles, Check, X, ChevronDown, ChevronRight, RefreshCw } from 'lucide-react';
import { Card } from '@/components/Card';
import { pipelineService } from '@/services/pipelineService';

export interface ProactiveAdvice {
  id: string;
  project_id: string;
  advice_type: 'readiness' | 'stage_strategy' | 'stall_warning' | 'llm_advice' | 'stage_check';
  stage: string | null;
  severity: 'info' | 'low' | 'medium' | 'high';
  title: string;
  message: string;
  suggestion: string | null;
  extra_data: Record<string, unknown> | null;
  status: 'pending' | 'acknowledged' | 'dismissed';
  source: string;
  created_at: string | null;
  acknowledged_at: string | null;
  dismissed_at: string | null;
}

interface ProactiveAdvicePanelProps {
  projectId: string;
  compact?: boolean;
}

const adviceTypeLabel: Record<string, string> = {
  readiness: '就绪检查',
  stage_strategy: '阶段建议',
  stall_warning: '停滞提醒',
  llm_advice: 'LLM 建议',
  stage_check: '阶段检查',
};

const severityConfig: Record<string, { color: string; bg: string; border: string; icon: React.ReactNode }> = {
  high: {
    color: 'text-red-400',
    bg: 'bg-red-500/10',
    border: 'border-red-500/40',
    icon: <AlertCircle className="w-4 h-4" />,
  },
  medium: {
    color: 'text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/40',
    icon: <AlertTriangle className="w-4 h-4" />,
  },
  low: {
    color: 'text-blue-400',
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/40',
    icon: <Info className="w-4 h-4" />,
  },
  info: {
    color: 'text-green-400',
    bg: 'bg-green-500/10',
    border: 'border-green-500/40',
    icon: <Sparkles className="w-4 h-4" />,
  },
};

const stageLabelMap: Record<string, string> = {
  problem_understanding: '问题理解',
  literature_mining: '文献挖掘',
  knowledge_gap: '知识缺口',
  hypothesis_generation: '假设生成',
  hypothesis_review: '假设评审',
  iterative_experiment: '迭代实验',
  report_generation: '报告生成',
};

export function ProactiveAdvicePanel({ projectId, compact = false }: ProactiveAdvicePanelProps) {
  const [adviceList, setAdviceList] = useState<ProactiveAdvice[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<'all' | 'pending' | 'acknowledged' | 'dismissed'>('pending');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const loadAdvice = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const statusParam = filter === 'all' ? undefined : filter;
      const res = await pipelineService.getCoordinatorAdvice(projectId, statusParam);
      if (res.code === 200 && res.data) {
        setAdviceList((res.data.advice_list || []) as unknown as ProactiveAdvice[]);
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [projectId, filter]);

  useEffect(() => {
    loadAdvice();
  }, [loadAdvice]);

  const handleAck = async (adviceId: string) => {
    try {
      await pipelineService.acknowledgeAdvice(adviceId);
      setAdviceList((prev) =>
        prev.map((a) =>
          a.id === adviceId
            ? { ...a, status: 'acknowledged', acknowledged_at: new Date().toISOString() }
            : a
        )
      );
    } catch {
      // ignore
    }
  };

  const handleDismiss = async (adviceId: string) => {
    try {
      await pipelineService.dismissAdvice(adviceId);
      setAdviceList((prev) =>
        prev.map((a) =>
          a.id === adviceId
            ? { ...a, status: 'dismissed', dismissed_at: new Date().toISOString() }
            : a
        )
      );
    } catch {
      // ignore
    }
  };

  const pendingCount = adviceList.filter((a) => a.status === 'pending').length;

  const renderContent = () => (
    <>
      {/* 过滤器 */}
      <div className="flex gap-1 mb-3">
        {(['pending', 'all', 'acknowledged', 'dismissed'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`text-xs px-2 py-1 rounded transition-colors ${
              filter === f
                ? 'bg-bp-cyan/20 text-bp-cyan'
                : 'text-bp-muted hover:text-bp-text hover:bg-white/5'
            }`}
          >
            {f === 'pending' ? '待处理' : f === 'all' ? '全部' : f === 'acknowledged' ? '已确认' : '已忽略'}
          </button>
        ))}
      </div>

      {loading && adviceList.length === 0 ? (
        <div className="text-center py-4 text-sm text-bp-muted">加载中…</div>
      ) : adviceList.length === 0 ? (
        <div className="text-center py-4">
          <Brain className="w-6 h-6 mx-auto mb-2 opacity-30 text-bp-muted" />
          <p className="text-sm text-bp-muted">暂无主动协调建议</p>
          <p className="text-xs text-bp-muted mt-1">Pipeline 运行后将自动生成建议</p>
        </div>
      ) : (
        <div className="space-y-2">
          {adviceList.map((advice) => {
            const config = severityConfig[advice.severity] || severityConfig.info;
            const isExpanded = expandedId === advice.id;
            const isPending = advice.status === 'pending';

            return (
              <div
                key={advice.id}
                className={`border-l-2 ${config.border} ${config.bg} pl-3 pr-2 py-2 rounded-r ${
                  advice.status === 'dismissed' ? 'opacity-50' : ''
                }`}
              >
                <div className="flex items-center gap-2 text-xs text-bp-muted mb-1">
                  <span>{config.icon}</span>
                  <span className={config.color}>
                    {advice.severity === 'high' ? '高' : advice.severity === 'medium' ? '中' : advice.severity === 'low' ? '低' : '信息'}
                  </span>
                  <span>·</span>
                  <span>{adviceTypeLabel[advice.advice_type] || advice.advice_type}</span>
                  {advice.stage && (
                    <>
                      <span>·</span>
                      <span>{stageLabelMap[advice.stage] || advice.stage}</span>
                    </>
                  )}
                  <span className="ml-auto">
                    {advice.status === 'pending' && advice.advice_type === 'stage_check' && advice.extra_data && (advice.extra_data as Record<string, unknown>).fix_status === 'completed' && (
                      <span className="text-[10px] text-green-400">已自动修复 ✓</span>
                    )}
                    {advice.status === 'pending' && advice.advice_type === 'stage_check' && advice.extra_data && (advice.extra_data as Record<string, unknown>).fix_status === 'failed' && (
                      <span className="text-[10px] text-red-400">修复失败 ✗</span>
                    )}
                    {advice.status === 'pending' && !(advice.advice_type === 'stage_check' && advice.extra_data && ['completed', 'failed'].includes((advice.extra_data as Record<string, unknown>).fix_status as string)) && (
                      <span className="text-[10px] text-amber-400">待处理</span>
                    )}
                    {advice.status === 'acknowledged' && (
                      <span className="text-[10px] text-green-400">已确认</span>
                    )}
                    {advice.status === 'dismissed' && (
                      <span className="text-[10px] text-bp-muted/60">已忽略</span>
                    )}
                  </span>
                </div>

                <div className="flex items-start gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-bp-text">{advice.title}</p>
                    <p className="text-xs text-bp-muted mt-0.5">{advice.message}</p>

                    {advice.extra_data && isExpanded && (
                      <pre className="mt-1 text-[10px] text-bp-muted/60 bg-black/10 rounded p-1 overflow-x-auto max-h-24">
                        {JSON.stringify(advice.extra_data, null, 2)}
                      </pre>
                    )}

                    {advice.created_at && (
                      <p className="text-[10px] text-bp-muted/40 mt-1">
                        {new Date(advice.created_at).toLocaleString('zh-CN')}
                      </p>
                    )}
                  </div>

                  {/* 操作按钮 — 仅对需要用户操作的提示显示 */}
                  {isPending && (() => {
                    // stage_check 类型：检查 extra_data 中的 action.type
                    if (advice.advice_type === 'stage_check') {
                      const ed = advice.extra_data as Record<string, unknown> | null;
                      const action = ed?.action as Record<string, unknown> | undefined;
                      return action?.type === 'hint' || action?.type === 'pass';
                    }
                    // 其他类型：可操作的建议类型显示按钮
                    return advice.advice_type === 'stage_strategy' || advice.advice_type === 'stall_warning' || advice.advice_type === 'llm_advice';
                  })() && (
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={() => handleAck(advice.id)}
                        className="p-1 rounded hover:bg-green-500/10 text-green-400 transition-colors"
                        title="确认"
                      >
                        <Check className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => handleDismiss(advice.id)}
                        className="p-1 rounded hover:bg-red-500/10 text-red-400 transition-colors"
                        title="忽略"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  )}

                  {advice.extra_data && (
                    <button
                      onClick={() => setExpandedId(isExpanded ? null : advice.id)}
                      className="p-1 rounded hover:bg-white/5 text-bp-muted transition-colors shrink-0"
                      title="展开详情"
                    >
                      {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </>
  );

  if (compact) {
    return <div>{renderContent()}</div>;
  }

  return (
    <Card
      title={
        <span className="flex items-center gap-2">
          <Brain className="w-5 h-5 text-bp-cyan" />
          主动协调建议
          {pendingCount > 0 && (
            <span className="text-[10px] text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded-full ml-1">
              {pendingCount} 待处理
            </span>
          )}
          <button
            onClick={loadAdvice}
            disabled={loading}
            className="ml-auto p-1 rounded hover:bg-white/10 text-bp-muted hover:text-bp-text transition-colors"
            title="刷新"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </span>
      }
      subtitle="就绪检查、阶段建议与提醒"
    >
      {renderContent()}
    </Card>
  );
}