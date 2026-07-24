import { cn } from '@/lib/utils';
import {
  CheckCircle, Loader2, Clock, XCircle,
  AlertTriangle, ChevronRight, Circle,
} from 'lucide-react';
import type { AgentNodeData, AgentStatus } from '@/types';
import { extractLiteratureStats, formatLiteratureStatsSummary } from '@/lib/literatureStats';

// ============ 状态配置 ============
const statusConfig: Record<AgentStatus, {
  label: string;
  ringClass: string;
  dotClass: string;
  cardBg: string;
  cardBorder: string;
  cardBorderLeft: string;
  textClass: string;
}> = {
  completed: {
    label: '已完成',
    ringClass: 'border-bp-green bg-bp-green/10',
    dotClass: 'bg-bp-green',
    cardBg: 'bg-bp-green/5',
    cardBorder: 'border-bp-green/20',
    cardBorderLeft: 'border-l-bp-green',
    textClass: 'text-bp-green',
  },
  running: {
    label: '运行中',
    ringClass: 'border-bp-cyan bg-bp-cyan-tint animate-pulse',
    dotClass: 'bg-bp-cyan',
    cardBg: 'bg-bp-cyan-tint',
    cardBorder: 'border-bp-cyan/20',
    cardBorderLeft: 'border-l-bp-cyan',
    textClass: 'text-bp-cyan',
  },
  pending: {
    label: '未开始',
    ringClass: 'border-bp-border bg-bp-panel/60',
    dotClass: 'bg-bp-muted',
    cardBg: 'bg-bp-panel/20',
    cardBorder: 'border-bp-border/50',
    cardBorderLeft: 'border-l-bp-border',
    textClass: 'text-bp-muted',
  },
  failed: {
    label: '失败',
    ringClass: 'border-danger-500 bg-danger-500/10',
    dotClass: 'bg-danger-400',
    cardBg: 'bg-danger-500/5',
    cardBorder: 'border-danger-500/30',
    cardBorderLeft: 'border-l-danger-500',
    textClass: 'text-danger-400',
  },
  human_review: {
    label: '待人工复核',
    ringClass: 'border-bp-yellow bg-bp-yellow/10',
    dotClass: 'bg-bp-yellow',
    cardBg: 'bg-bp-yellow/5',
    cardBorder: 'border-bp-yellow/20',
    cardBorderLeft: 'border-l-bp-yellow',
    textClass: 'text-bp-yellow',
  },
  human_review_required: {
    label: '待人工复核',
    ringClass: 'border-bp-yellow bg-bp-yellow/10',
    dotClass: 'bg-bp-yellow',
    cardBg: 'bg-bp-yellow/5',
    cardBorder: 'border-bp-yellow/20',
    cardBorderLeft: 'border-l-bp-yellow',
    textClass: 'text-bp-yellow',
  },
};

function StatusIcon({ status, className }: { status: AgentStatus; className?: string }) {
  const cls = cn('w-4 h-4 shrink-0', className);
  switch (status) {
    case 'completed':             return <CheckCircle className={cn(cls, 'text-bp-green')} />;
    case 'running':               return <Loader2 className={cn(cls, 'text-bp-cyan animate-spin')} />;
    case 'pending':               return <Clock className={cn(cls, 'text-bp-muted')} />;
    case 'failed':                return <XCircle className={cn(cls, 'text-danger-400')} />;
    case 'human_review':
    case 'human_review_required': return <AlertTriangle className={cn(cls, 'text-bp-yellow')} />;
  }
}

function formatDuration(ms: number | null): string {
  if (ms === null) return '—';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

interface AgentNodeProps {
  node: AgentNodeData;
  isSelected: boolean;
  isLast: boolean;
  stepNumber: number;
  onClick: () => void;
  /** 迭代实验节点：当前项目下的实验组数量 */
  experimentGroupCount?: number | null;
  /** 迭代实验节点：如「1 已完成 · 1 待审阅」 */
  experimentGroupHint?: string | null;
}

export function AgentNode({
  node,
  isSelected,
  isLast,
  stepNumber,
  onClick,
  experimentGroupCount = null,
  experimentGroupHint = null,
}: AgentNodeProps) {
  const Icon = node.icon;
  const isFailed = node.status === 'failed';
  const isRunning = node.status === 'running';
  const isCompleted = node.status === 'completed';
  const isReview =
    node.status === 'human_review' || node.status === 'human_review_required';
  const isExperimentNode = node.id === 'experiment';
  const hasExperimentCount = isExperimentNode && experimentGroupCount != null;
  const hasExperiments = isExperimentNode && (experimentGroupCount ?? 0) > 0;
  // 有实验组时按「已完成」绿色样式展示（失败/运行中仍保留原语义色）
  const showAsCompleted = isCompleted || (hasExperiments && !isFailed && !isRunning);
  const isPending = node.status === 'pending' && !showAsCompleted;
  const visualStatus: AgentStatus = isFailed
    ? 'failed'
    : isRunning
      ? 'running'
      : showAsCompleted
        ? 'completed'
        : isReview
          ? node.status
          : 'pending';
  const sc = statusConfig[visualStatus];
  const hasError = isFailed && !!node.error_message;
  const statusLabel = (() => {
    if (node.human_edited && isCompleted) return '已修订';
    if (hasExperimentCount && (isPending || showAsCompleted) && !isRunning && !isFailed) {
      return `${experimentGroupCount} 组实验`;
    }
    return statusConfig[node.status].label;
  })();
  const literatureStats = node.id === 'literature'
    ? extractLiteratureStats(node.output_data)
    : null;
  const literatureSummary = literatureStats ? formatLiteratureStatsSummary(literatureStats) : null;

  return (
    <div className="flex">
      {/* 左侧：时间线 */}
      <div className="flex flex-col items-center mr-3 w-8 shrink-0">
        <div className={cn(
          'w-8 h-8 rounded-full border-2 flex items-center justify-center transition-all duration-300',
          sc.ringClass,
          isRunning && 'shadow-lg shadow-bp-cyan/30',
          isFailed && 'shadow-lg shadow-danger-500/30',
          isSelected && 'ring-2 ring-bp-cyan/50 ring-offset-1 ring-offset-bp-base',
        )}>
          <Icon className={cn(
            'w-3.5 h-3.5',
            showAsCompleted ? 'text-bp-green'
            : isRunning ? 'text-bp-cyan'
            : isFailed ? 'text-danger-400'
            : isReview ? 'text-bp-yellow'
            : 'text-bp-muted',
          )} />
        </div>
        {!isLast && (
          <div className={cn(
            'w-0.5 flex-1 min-h-[8px] rounded-full transition-all duration-300',
            showAsCompleted ? 'bg-bp-green/40'
            : isRunning ? 'bg-bp-cyan/40 animate-pulse'
            : isFailed ? 'bg-danger-500/40'
            : 'bg-bp-border',
          )} />
        )}
      </div>

      {/* 右侧：节点卡片 */}
      <div className={cn(
        'flex-1 min-w-0 -mt-0.5',
        !isLast && 'pb-1',
      )}>
        <button
          onClick={onClick}
          className={cn(
            'w-full text-left p-3 rounded-lg transition-all duration-300',
            sc.cardBg,
            !isSelected && sc.cardBorder,
            !isSelected && 'border-l-2',
            !isSelected && sc.cardBorderLeft,
            isSelected
              ? 'border border-bp-cyan bg-bp-cyan-tint shadow-lg shadow-bp-cyan/5 border-l-2 border-l-bp-cyan'
              : 'border border-transparent hover:shadow-md',
            isFailed && !isSelected && 'hover:bg-danger-500/10 hover-accent-left-danger',
            isPending && !isSelected && 'hover:bg-bp-panel/40 hover-accent-left-muted',
            isRunning && !isSelected && 'hover:bg-bp-cyan-tint hover-accent-left',
            showAsCompleted && !isSelected && 'hover:bg-bp-green/10 hover-accent-left-green',
          )}
        >
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              {/* 节点头部 */}
              <div className="flex items-center gap-2">
                <span className="text-xs text-bp-muted font-mono w-4 shrink-0">
                  {stepNumber}
                </span>
                <span className={cn(
                  'text-sm font-medium truncate',
                  isSelected ? 'text-bp-cyan'
                  : isFailed ? 'text-danger-300'
                  : showAsCompleted ? 'text-bp-green'
                  : isRunning ? 'text-bp-cyan'
                  : 'text-bp-muted',
                )}>
                  {node.name}
                </span>
                {/* 状态角标 */}
                <span className={cn(
                  'shrink-0 inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium',
                  showAsCompleted && 'bg-bp-green/15 text-bp-green border border-bp-green/30',
                  isRunning && 'bg-bp-cyan-tint text-bp-cyan border border-bp-cyan/30',
                  isPending && 'bg-bp-surface/50 text-bp-muted border border-bp-border',
                  isFailed && 'bg-danger-500/15 text-danger-400 border border-danger-500/30',
                  isReview && !showAsCompleted && 'bg-bp-yellow/15 text-bp-yellow border border-bp-yellow/30',
                )}>
                  <StatusIcon status={visualStatus} className="w-3 h-3" />
                  {statusLabel}
                </span>
              </div>

              {/* 描述 */}
              <p className={cn(
                'text-xs mt-1 ml-6 line-clamp-1',
                isFailed ? 'text-danger-400/70' : isPending ? 'text-bp-muted' : 'text-bp-muted',
              )}>
                {node.shortDesc}
              </p>

              {/* 文献挖掘：检索 / 入库统计 */}
              {literatureSummary && (isCompleted || isRunning) && (
                <div className="ml-6 mt-1.5">
                  <span className="inline-flex items-center gap-1.5 text-xs px-2 py-0.5 rounded bg-bp-cyan-tint text-bp-cyan border border-bp-cyan/20">
                    {literatureSummary}
                  </span>
                </div>
              )}

              {/* 迭代实验：实验组数量 */}
              {hasExperimentCount && (
                <div className="ml-6 mt-1.5 flex flex-wrap items-center gap-1.5">
                  <span className={cn(
                    'inline-flex items-center gap-1.5 text-xs px-2 py-0.5 rounded border',
                    hasExperiments
                      ? 'bg-bp-green/15 text-bp-green border-bp-green/30'
                      : 'bg-bp-cyan-tint text-bp-cyan border-bp-cyan/20',
                  )}>
                    当前共 {experimentGroupCount} 组实验
                  </span>
                  {experimentGroupHint ? (
                    <span className="text-xs text-bp-muted line-clamp-1">{experimentGroupHint}</span>
                  ) : null}
                </div>
              )}

              {/* 耗时 */}
              {node.duration !== null && (
                <div className="ml-6 mt-1">
                  <span className="text-xs text-bp-muted">
                    耗时 {formatDuration(node.duration)}
                  </span>
                </div>
              )}

              {/* 失败错误信息 */}
              {hasError && (
                <div className="relative group ml-6 mt-2">
                  <div className="flex items-start gap-1.5 px-2 py-1.5 rounded bg-danger-500/10 border border-danger-500/20">
                    <XCircle className="w-3 h-3 text-danger-400 shrink-0 mt-0.5" />
                    <p className="text-xs text-danger-400/80 leading-relaxed line-clamp-2">
                      {node.error_message}
                    </p>
                  </div>
                  {/* Tooltip */}
                  <div className={cn(
                    'absolute left-0 bottom-full mb-2 w-64 p-3 rounded-lg',
                    'bg-bp-base border border-danger-500/30 shadow-xl shadow-danger-500/10',
                    'opacity-0 invisible group-hover:opacity-100 group-hover:visible',
                    'transition-all duration-200 z-50',
                  )}>
                    <div className="flex items-center gap-1.5 mb-1.5">
                      <AlertTriangle className="w-3.5 h-3.5 text-danger-400" />
                      <span className="text-xs font-semibold text-danger-300">错误详情</span>
                    </div>
                    <p className="text-xs text-danger-400/90 leading-relaxed whitespace-pre-wrap break-words">
                      {node.error_message}
                    </p>
                    {/* Tooltip arrow */}
                    <div className="absolute left-4 top-full -mt-px w-3 h-3 bg-bp-base border-r border-b border-danger-500/30 rotate-45" />
                  </div>
                </div>
              )}

              {/* 待处理提示（迭代实验改显示组数，不再显示「等待执行」） */}
              {isPending && !hasExperimentCount && (
                <div className="flex items-center gap-1.5 ml-6 mt-2">
                  <Circle className="w-2.5 h-2.5 text-bp-muted fill-bp-muted" />
                  <span className="text-xs text-bp-muted">等待执行</span>
                </div>
              )}
              {isPending && hasExperimentCount && experimentGroupCount === 0 && (
                <div className="flex items-center gap-1.5 ml-6 mt-2">
                  <Circle className="w-2.5 h-2.5 text-bp-muted fill-bp-muted" />
                  <span className="text-xs text-bp-muted">暂无实验组</span>
                </div>
              )}

              {/* 运行中动画占位 */}
              {isRunning && (
                <div className="flex items-center gap-1.5 ml-6 mt-2">
                  <span className="flex gap-0.5">
                    <span className="w-1 h-1 rounded-full bg-bp-cyan/60 animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-1 h-1 rounded-full bg-bp-cyan/60 animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-1 h-1 rounded-full bg-bp-cyan/60 animate-bounce" style={{ animationDelay: '300ms' }} />
                  </span>
                  <span className="text-xs text-bp-cyan/70">执行中…</span>
                </div>
              )}
            </div>

            <ChevronRight className={cn(
              'w-4 h-4 shrink-0 mt-1 transition-colors',
              isSelected ? 'text-bp-cyan'
              : isFailed ? 'text-danger-500/50'
              : showAsCompleted ? 'text-bp-green/50'
              : 'text-bp-border',
            )} />
          </div>
        </button>
      </div>
    </div>
  );
}