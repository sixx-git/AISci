import { cn } from '@/lib/utils';
import {
  CheckCircle, Loader2, Clock, XCircle,
  AlertTriangle, ChevronRight,
} from 'lucide-react';
import type { AgentNodeData, AgentStatus } from '@/types';

// ============ 状态配置 ============
const statusConfig: Record<AgentStatus, { label: string; ringClass: string; dotClass: string }> = {
  completed:             { label: '已完成',     ringClass: 'border-green-500 bg-green-500/10', dotClass: 'bg-green-400' },
  running:               { label: '运行中',     ringClass: 'border-blue-500 bg-blue-500/10',  dotClass: 'bg-blue-400' },
  pending:               { label: '未开始',     ringClass: 'border-gray-600 bg-gray-800/50',  dotClass: 'bg-gray-600' },
  failed:                { label: '失败',       ringClass: 'border-red-500 bg-red-500/10',    dotClass: 'bg-red-400' },
  human_review:          { label: '需人工确认', ringClass: 'border-amber-500 bg-amber-500/10', dotClass: 'bg-amber-400' },
  human_review_required: { label: '需人工确认', ringClass: 'border-amber-500 bg-amber-500/10', dotClass: 'bg-amber-400' },
};

function StatusIcon({ status }: { status: AgentStatus }) {
  switch (status) {
    case 'completed':             return <CheckCircle className="w-4 h-4 text-green-400" />;
    case 'running':               return <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />;
    case 'pending':               return <Clock className="w-4 h-4 text-gray-500" />;
    case 'failed':                return <XCircle className="w-4 h-4 text-red-400" />;
    case 'human_review':
    case 'human_review_required': return <AlertTriangle className="w-4 h-4 text-amber-400" />;
  }
}

// ============ 格式化耗时 ============
function formatDuration(ms: number | null): string {
  if (ms === null) return '—';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

// ============ Props ============
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

  return (
    <div className="flex">
      {/* 左侧：时间线 */}
      <div className="flex flex-col items-center mr-3 w-8 shrink-0">
        <div className={cn(
          'w-8 h-8 rounded-full border-2 flex items-center justify-center transition-all',
          sc.ringClass,
          isSelected && 'ring-2 ring-primary-500/50',
        )}>
          <Icon className={cn(
            'w-3.5 h-3.5',
            node.status === 'completed' ? 'text-green-400'
            : node.status === 'running' ? 'text-blue-400'
            : node.status === 'failed' ? 'text-red-400'
            : node.status === 'human_review' || node.status === 'human_review_required' ? 'text-amber-400'
            : 'text-gray-500'
          )} />
        </div>
        {!isLast && (
          <div className={cn(
            'w-0.5 flex-1 min-h-[8px] rounded-full transition-all',
            node.status === 'completed' ? 'bg-green-500/40'
            : node.status === 'running' ? 'bg-blue-500/40'
            : 'bg-gray-700',
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
            'w-full text-left p-3 rounded-lg border transition-all duration-200',
            isSelected
              ? 'border-primary-500 bg-primary-500/10 shadow-lg shadow-primary-500/5'
              : 'border-transparent hover:border-gray-600 hover:bg-gray-800/40 bg-gray-800/20',
          )}
        >
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-gray-600 font-mono w-4">
                  {stepNumber}
                </span>
                <span className={cn(
                  'text-sm font-medium truncate',
                  isSelected ? 'text-primary-300' : 'text-gray-200',
                )}>
                  {node.name}
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-1 ml-6 line-clamp-1">
                {node.shortDesc}
              </p>
              <div className="flex items-center gap-3 mt-2 ml-6">
                <span className={cn(
                  'inline-flex items-center gap-1 text-[11px] font-medium',
                  sc.dotClass,
                )}>
                  <StatusIcon status={node.status} />
                  {sc.label}
                </span>
                {node.duration !== null && (
                  <span className="text-[11px] text-gray-600">
                    耗时 {formatDuration(node.duration)}
                  </span>
                )}
              </div>
            </div>
            <ChevronRight className={cn(
              'w-4 h-4 shrink-0 mt-1 transition-colors',
              isSelected ? 'text-primary-400' : 'text-gray-700',
            )} />
          </div>
        </button>
      </div>
    </div>
  );
}