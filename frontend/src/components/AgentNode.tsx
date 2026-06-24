import { cn } from '@/lib/utils';
import {
  CheckCircle, Loader2, Clock, XCircle,
  AlertTriangle, ChevronRight, Circle,
} from 'lucide-react';
import type { AgentNodeData, AgentStatus } from '@/types';

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
    ringClass: 'border-green-500 bg-green-500/10',
    dotClass: 'bg-green-400',
    cardBg: 'bg-green-500/5',
    cardBorder: 'border-green-500/20',
    cardBorderLeft: 'border-l-green-500',
    textClass: 'text-green-400',
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
    ringClass: 'border-red-500 bg-red-500/10',
    dotClass: 'bg-red-400',
    cardBg: 'bg-red-500/5',
    cardBorder: 'border-red-500/30',
    cardBorderLeft: 'border-l-red-500',
    textClass: 'text-red-400',
  },
  human_review: {
    label: '需人工确认',
    ringClass: 'border-amber-500 bg-amber-500/10',
    dotClass: 'bg-amber-400',
    cardBg: 'bg-amber-500/5',
    cardBorder: 'border-amber-500/20',
    cardBorderLeft: 'border-l-amber-500',
    textClass: 'text-amber-400',
  },
  human_review_required: {
    label: '需人工确认',
    ringClass: 'border-amber-500 bg-amber-500/10',
    dotClass: 'bg-amber-400',
    cardBg: 'bg-amber-500/5',
    cardBorder: 'border-amber-500/20',
    cardBorderLeft: 'border-l-amber-500',
    textClass: 'text-amber-400',
  },
};

function StatusIcon({ status, className }: { status: AgentStatus; className?: string }) {
  const cls = cn('w-4 h-4 shrink-0', className);
  switch (status) {
    case 'completed':             return <CheckCircle className={cn(cls, 'text-green-400')} />;
    case 'running':               return <Loader2 className={cn(cls, 'text-bp-cyan animate-spin')} />;
    case 'pending':               return <Clock className={cn(cls, 'text-bp-muted')} />;
    case 'failed':                return <XCircle className={cn(cls, 'text-red-400')} />;
    case 'human_review':
    case 'human_review_required': return <AlertTriangle className={cn(cls, 'text-amber-400')} />;
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
}

export function AgentNode({ node, isSelected, isLast, stepNumber, onClick }: AgentNodeProps) {
  const Icon = node.icon;
  const sc = statusConfig[node.status];
  const isFailed = node.status === 'failed';
  const isPending = node.status === 'pending';
  const isRunning = node.status === 'running';
  const isCompleted = node.status === 'completed';
  const hasError = isFailed && !!node.error_message;

  return (
    <div className="flex">
      {/* 左侧：时间线 */}
      <div className="flex flex-col items-center mr-3 w-8 shrink-0">
        <div className={cn(
          'w-8 h-8 rounded-full border-2 flex items-center justify-center transition-all duration-300',
          sc.ringClass,
          isRunning && 'shadow-lg shadow-bp-cyan/30',
          isFailed && 'shadow-lg shadow-red-500/30',
          isSelected && 'ring-2 ring-bp-cyan/50 ring-offset-1 ring-offset-bp-base',
        )}>
          <Icon className={cn(
            'w-3.5 h-3.5',
            isCompleted ? 'text-green-400'
            : isRunning ? 'text-bp-cyan'
            : isFailed ? 'text-red-400'
            : node.status === 'human_review' || node.status === 'human_review_required' ? 'text-amber-400'
            : 'text-gray-600',
          )} />
        </div>
        {!isLast && (
          <div className={cn(
            'w-0.5 flex-1 min-h-[8px] rounded-full transition-all duration-300',
            isCompleted ? 'bg-green-500/40'
            : isRunning ? 'bg-bp-cyan/40 animate-pulse'
            : isFailed ? 'bg-red-500/40'
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
            isFailed && !isSelected && 'hover:bg-red-500/10 hover:border-red-500/40',
            isPending && !isSelected && 'hover:bg-bp-panel/40 hover:border-bp-border/50',
            isRunning && !isSelected && 'hover:bg-bp-cyan-tint hover:border-bp-cyan/30',
            isCompleted && !isSelected && 'hover:bg-green-500/10 hover:border-green-500/30',
          )}
        >
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              {/* 节点头部 */}
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-bp-muted font-mono w-4 shrink-0">
                  {stepNumber}
                </span>
                <span className={cn(
                  'text-sm font-medium truncate',
                  isSelected ? 'text-bp-cyan'
                  : isFailed ? 'text-red-300'
                  : isCompleted ? 'text-green-300'
                  : isRunning ? 'text-bp-cyan'
                  : 'text-bp-muted',
                )}>
                  {node.name}
                </span>
                {/* 状态角标 */}
                <span className={cn(
                  'shrink-0 inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium',
                  isCompleted && 'bg-green-500/15 text-green-400 border border-green-500/30',
                  isRunning && 'bg-bp-cyan-tint text-bp-cyan border border-bp-cyan/30',
                  isPending && 'bg-bp-surface/50 text-bp-muted border border-bp-border',
                  isFailed && 'bg-red-500/15 text-red-400 border border-red-500/30',
                  (node.status === 'human_review' || node.status === 'human_review_required') && 'bg-amber-500/15 text-amber-400 border border-amber-500/30',
                )}>
                  <StatusIcon status={node.status} className="w-3 h-3" />
                  {sc.label}
                </span>
              </div>

              {/* 描述 */}
              <p className={cn(
                'text-xs mt-1 ml-6 line-clamp-1',
                isFailed ? 'text-red-400/70' : isPending ? 'text-bp-muted' : 'text-bp-muted',
              )}>
                {node.shortDesc}
              </p>

              {/* 耗时 */}
              {node.duration !== null && (
                <div className="ml-6 mt-1">
                  <span className="text-[11px] text-bp-muted">
                    耗时 {formatDuration(node.duration)}
                  </span>
                </div>
              )}

              {/* 失败错误信息 */}
              {hasError && (
                <div className="relative group ml-6 mt-2">
                  <div className="flex items-start gap-1.5 px-2 py-1.5 rounded bg-red-500/10 border border-red-500/20">
                    <XCircle className="w-3 h-3 text-red-400 shrink-0 mt-0.5" />
                    <p className="text-[11px] text-red-400/80 leading-relaxed line-clamp-2">
                      {node.error_message}
                    </p>
                  </div>
                  {/* Tooltip */}
                  <div className={cn(
                    'absolute left-0 bottom-full mb-2 w-64 p-3 rounded-lg',
                    'bg-bp-base border border-red-500/30 shadow-xl shadow-red-500/10',
                    'opacity-0 invisible group-hover:opacity-100 group-hover:visible',
                    'transition-all duration-200 z-50',
                  )}>
                    <div className="flex items-center gap-1.5 mb-1.5">
                      <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
                      <span className="text-[11px] font-semibold text-red-300">错误详情</span>
                    </div>
                    <p className="text-[11px] text-red-400/90 leading-relaxed whitespace-pre-wrap break-words">
                      {node.error_message}
                    </p>
                    {/* Tooltip arrow */}
                    <div className="absolute left-4 top-full -mt-px w-3 h-3 bg-bp-base border-r border-b border-red-500/30 rotate-45" />
                  </div>
                </div>
              )}

              {/* 待处理提示 */}
              {isPending && (
                <div className="flex items-center gap-1.5 ml-6 mt-2">
                  <Circle className="w-2.5 h-2.5 text-bp-muted fill-bp-muted" />
                  <span className="text-[11px] text-bp-muted">等待执行</span>
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
                  <span className="text-[11px] text-bp-cyan/70">执行中…</span>
                </div>
              )}
            </div>

            <ChevronRight className={cn(
              'w-4 h-4 shrink-0 mt-1 transition-colors',
              isSelected ? 'text-bp-cyan'
              : isFailed ? 'text-red-500/50'
              : isCompleted ? 'text-green-500/50'
              : 'text-bp-border',
            )} />
          </div>
        </button>
      </div>
    </div>
  );
}