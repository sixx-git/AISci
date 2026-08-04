import { Brain, AlertTriangle, AlertCircle, Info, Sparkles, RotateCcw, Eye } from 'lucide-react';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';

export interface CoordinatorHint {
  id: string;
  stage: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  message: string;
  remediation: string | null;
  action: {
    type: 'hint' | 'auto';
    suggestion: string;
    description: string;
  };
  source: string;
  patternId?: string;
  timestamp: string;
}

interface CoordinatorHintsProps {
  hints: CoordinatorHint[];
  onRerunStage?: (stage: string) => void;
  onViewDetail?: (hint: CoordinatorHint) => void;
  compact?: boolean;
}

const severityConfig: Record<string, { color: string; bg: string; border: string; icon: React.ReactNode; label: string }> = {
  critical: {
    color: 'text-red-400',
    bg: 'bg-red-500/10',
    border: 'border-red-500/40',
    icon: <AlertCircle className="w-4 h-4" />,
    label: '严重',
  },
  high: {
    color: 'text-orange-400',
    bg: 'bg-orange-500/10',
    border: 'border-orange-500/40',
    icon: <AlertTriangle className="w-4 h-4" />,
    label: '高',
  },
  medium: {
    color: 'text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/40',
    icon: <AlertTriangle className="w-4 h-4" />,
    label: '中',
  },
  low: {
    color: 'text-blue-400',
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/40',
    icon: <Info className="w-4 h-4" />,
    label: '低',
  },
  info: {
    color: 'text-green-400',
    bg: 'bg-green-500/10',
    border: 'border-green-500/40',
    icon: <Sparkles className="w-4 h-4" />,
    label: '信息',
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

export function CoordinatorHints({
  hints,
  onRerunStage,
  onViewDetail,
  compact = false,
}: CoordinatorHintsProps) {
  const pendingHints = hints.filter((h) => h.action?.type !== 'auto');
  const autoHints = hints.filter((h) => h.action?.type === 'auto');

  return (
    <Card
      title={
        <span className="flex items-center gap-2">
          <Brain className="w-5 h-5 text-bp-cyan" />
          大家长 Agent
        </span>
      }
      subtitle="阶段检查与补救建议"
    >
      {hints.length === 0 ? (
        <div className="text-center py-4">
          <Brain className="w-6 h-6 mx-auto mb-2 opacity-30 text-bp-muted" />
          <p className="text-sm text-bp-muted">暂无待处理提示</p>
          <p className="text-xs text-bp-muted mt-1">Pipeline 运行后将自动显示检查结果</p>
        </div>
      ) : (
        <div className="space-y-3">
          {autoHints.length > 0 && (
            <div className="mb-3">
              <div className="text-xs text-bp-muted mb-2">⚡ 自动执行</div>
              <div className="space-y-2">
                {autoHints.map((hint) => {
                  const config = severityConfig[hint.severity] || severityConfig.info;
                  return (
                    <div
                      key={hint.id}
                      className={`border-l-2 ${config.border} ${config.bg} pl-3 pr-2 py-2 rounded-r`}
                    >
                      <div className="flex items-center gap-2 text-xs text-bp-muted mb-1">
                        <span>{config.icon}</span>
                        <span className={config.color}>{config.label}</span>
                        <span>·</span>
                        <span>{stageLabelMap[hint.stage] || hint.stage}</span>
                      </div>
                      <p className="text-sm text-bp-text">{hint.message}</p>
                      <p className="text-xs text-bp-cyan mt-1">⟳ {hint.action.description}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {pendingHints.length > 0 && (
            <div>
              <div className="text-xs text-bp-muted mb-2">💡 待处理提示</div>
              <div className="space-y-2">
                {pendingHints.map((hint) => {
                  const config = severityConfig[hint.severity] || severityConfig.info;
                  return (
                    <div
                      key={hint.id}
                      className={`border-l-2 ${config.border} ${config.bg} pl-3 pr-2 py-2 rounded-r`}
                    >
                      <div className="flex items-center gap-2 text-xs text-bp-muted mb-1">
                        <span>{config.icon}</span>
                        <span className={config.color}>{config.label}</span>
                        <span>·</span>
                        <span>{stageLabelMap[hint.stage] || hint.stage}</span>
                      </div>
                      <p className="text-sm text-bp-text">{hint.message}</p>
                      {!compact && (
                        <div className="flex items-center gap-2 mt-2">
                          {hint.action.suggestion === 'rerun_stage' && onRerunStage && (
                            <Button
                              variant="primary"
                              size="sm"
                              icon={<RotateCcw className="w-3 h-3" />}
                              onClick={() => onRerunStage(hint.stage)}
                            >
                              重跑 {stageLabelMap[hint.stage] || hint.stage}
                            </Button>
                          )}
                          {hint.action.suggestion === 'revise_report' && onViewDetail && (
                            <Button
                              variant="secondary"
                              size="sm"
                              icon={<Eye className="w-3 h-3" />}
                              onClick={() => onViewDetail(hint)}
                            >
                              查看详情
                            </Button>
                          )}
                          {hint.action.suggestion !== 'rerun_stage' &&
                            hint.action.suggestion !== 'revise_report' && (
                              <Button
                                variant="secondary"
                                size="sm"
                                onClick={() => onViewDetail && onViewDetail(hint)}
                              >
                                {hint.action.description}
                              </Button>
                            )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
