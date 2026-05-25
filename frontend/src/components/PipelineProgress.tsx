import { cn } from '@/lib/utils';
import { CheckCircle, Loader2, Clock, XCircle } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

export interface PipelineProgressNode {
  id: string;
  label: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  icon: LucideIcon;
}

interface PipelineProgressProps {
  nodes: PipelineProgressNode[];
  className?: string;
}

const statusLabel: Record<PipelineProgressNode['status'], string> = {
  pending: '未开始',
  running: '运行中',
  completed: '已完成',
  error: '失败',
};

function nodeRingStyle(s: PipelineProgressNode['status']) {
  switch (s) {
    case 'completed': return 'bg-green-500/15 border-green-500 text-green-400';
    case 'running':   return 'bg-blue-500/15 border-blue-500 text-blue-400';
    case 'error':     return 'bg-red-500/15 border-red-500 text-red-400';
    default:          return 'bg-gray-800 border-gray-700 text-gray-500';
  }
}

function statusBadge(s: PipelineProgressNode['status']) {
  switch (s) {
    case 'completed': return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-green-500/20 text-green-400">
        <CheckCircle className="w-3 h-3" />{statusLabel[s]}
      </span>
    );
    case 'running': return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-500/20 text-blue-400">
        <Loader2 className="w-3 h-3 animate-spin" />{statusLabel[s]}
      </span>
    );
    case 'error': return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-red-500/20 text-red-400">
        <XCircle className="w-3 h-3" />{statusLabel[s]}
      </span>
    );
    default: return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-gray-700 text-gray-500">
        <Clock className="w-3 h-3" />{statusLabel[s]}
      </span>
    );
  }
}

function connectorStyle(prev: PipelineProgressNode['status'], next: PipelineProgressNode['status']) {
  if (prev === 'completed' && next === 'completed') return 'bg-green-500';
  if (prev === 'completed' && next === 'running')   return 'bg-gradient-to-r from-green-500 to-blue-500';
  if (prev === 'completed' && next === 'pending')    return 'bg-gradient-to-r from-green-500 to-gray-700';
  if (prev === 'running'   && next === 'pending')    return 'bg-gradient-to-r from-blue-500 to-gray-700';
  return 'bg-gray-700';
}

export function PipelineProgress({ nodes, className }: PipelineProgressProps) {
  return (
    <div className={cn('space-y-4', className)}>
      {/* 横向进度条（桌面端） */}
      <div className="hidden md:block overflow-x-auto">
        <div className="flex items-center min-w-max py-3">
          {nodes.map((node, idx) => {
            const Icon = node.icon;
            const isLast = idx === nodes.length - 1;
            return (
              <div key={node.id} className="flex items-center">
                <div className="flex flex-col items-center gap-1.5 shrink-0 min-w-[80px]">
                  <div className={cn(
                    'w-11 h-11 rounded-full border-2 flex items-center justify-center transition-all duration-300',
                    nodeRingStyle(node.status),
                    node.status === 'running' && 'animate-pulse',
                  )}>
                    {node.status === 'running'
                      ? <Loader2 className="w-5 h-5 animate-spin text-blue-400" />
                      : <Icon className={cn(
                          'w-5 h-5',
                          node.status === 'completed' ? 'text-green-400'
                          : node.status === 'error' ? 'text-red-400'
                          : 'text-gray-600'
                        )} />
                    }
                  </div>
                  <span className={cn(
                    'text-xs font-medium whitespace-nowrap',
                    node.status === 'pending' ? 'text-gray-500' : 'text-gray-200',
                  )}>
                    {node.label}
                  </span>
                  {statusBadge(node.status)}
                </div>
                {!isLast && (
                  <div className="w-8 h-0.5 mx-0.5 shrink-0 rounded-full transition-all duration-500"
                    style={{ minWidth: '24px' }}
                  >
                    <div className={cn('h-full rounded-full', connectorStyle(node.status, nodes[idx + 1].status))} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* 纵向时间线（移动端） */}
      <div className="md:hidden space-y-0">
        {nodes.map((node, idx) => {
          const Icon = node.icon;
          const isLast = idx === nodes.length - 1;
          return (
            <div key={node.id} className="flex gap-3">
              <div className="flex flex-col items-center">
                <div className={cn(
                  'w-9 h-9 rounded-full border-2 flex items-center justify-center transition-all duration-300 shrink-0',
                  nodeRingStyle(node.status),
                )}>
                  {node.status === 'running'
                    ? <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
                    : <Icon className={cn('w-4 h-4',
                        node.status === 'completed' ? 'text-green-400'
                        : node.status === 'error' ? 'text-red-400'
                        : 'text-gray-600'
                      )} />
                  }
                </div>
                {!isLast && (
                  <div className={cn('w-0.5 flex-1 min-h-[24px] rounded-full transition-all',
                    connectorStyle(node.status, nodes[idx + 1].status),
                  )} />
                )}
              </div>
              <div className="pb-4">
                <span className={cn('text-sm font-medium',
                  node.status === 'pending' ? 'text-gray-500' : 'text-gray-200',
                )}>{node.label}</span>
                <div className="mt-1">{statusBadge(node.status)}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}