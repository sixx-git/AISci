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
  /** 点击阶段节点时回调（传入则节点可点击） */
  onNodeClick?: (node: PipelineProgressNode) => void;
}

const statusLabel: Record<PipelineProgressNode['status'], string> = {
  pending: '未开始',
  running: '运行中',
  completed: '已完成',
  error: '失败',
};

function nodeRingStyle(s: PipelineProgressNode['status']) {
  switch (s) {
    case 'completed': return 'bg-bp-green/15 border-bp-green text-bp-green';
    case 'running':   return 'bg-bp-cyan-tint border-bp-cyan text-bp-cyan';
    case 'error':     return 'bg-danger-500/15 border-danger-500 text-danger-400';
    default:          return 'bg-bp-panel border-bp-border text-bp-muted';
  }
}

function statusBadge(s: PipelineProgressNode['status']) {
  switch (s) {
    case 'completed': return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-bp text-xs font-medium bg-bp-green/20 text-bp-green">
        <CheckCircle className="w-3 h-3" />{statusLabel[s]}
      </span>
    );
    case 'running': return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-bp text-xs font-medium bg-bp-cyan-tint text-bp-cyan">
        <Loader2 className="w-3 h-3 animate-spin" />{statusLabel[s]}
      </span>
    );
    case 'error': return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-bp text-xs font-medium bg-danger-500/20 text-danger-400">
        <XCircle className="w-3 h-3" />{statusLabel[s]}
      </span>
    );
    default: return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-bp text-xs font-medium bg-bp-surface text-bp-muted">
        <Clock className="w-3 h-3" />{statusLabel[s]}
      </span>
    );
  }
}

function connectorStyle(prev: PipelineProgressNode['status'], next: PipelineProgressNode['status']) {
  if (prev === 'completed' && next === 'completed') return 'bg-bp-green';
  if (prev === 'completed' && next === 'running')   return 'bg-gradient-to-r from-bp-green to-bp-cyan';
  if (prev === 'completed' && next === 'pending')    return 'bg-gradient-to-r from-bp-green to-bp-border';
  if (prev === 'running'   && next === 'pending')    return 'bg-gradient-to-r from-bp-cyan to-bp-border';
  return 'bg-bp-border';
}

export function PipelineProgress({ nodes, className, onNodeClick }: PipelineProgressProps) {
  const clickable = Boolean(onNodeClick);

  const renderNodeBody = (node: PipelineProgressNode, compact = false) => {
    const Icon = node.icon;
    const ringSize = compact ? 'w-9 h-9' : 'w-11 h-11';
    const iconSize = compact ? 'w-4 h-4' : 'w-5 h-5';

    const body = (
      <>
        <div className={cn(
          ringSize,
          'rounded-full border-2 flex items-center justify-center transition-all duration-300',
          nodeRingStyle(node.status),
          node.status === 'running' && 'animate-pulse',
          clickable && 'group-hover:border-bp-cyan/50 group-hover:shadow-bp-glow',
        )}>
          {node.status === 'running'
            ? <Loader2 className={cn(iconSize, 'animate-spin text-bp-cyan')} />
            : <Icon className={cn(
                iconSize,
                node.status === 'completed' ? 'text-bp-green'
                : node.status === 'error' ? 'text-danger-400'
                : 'text-bp-muted',
                clickable && 'group-hover:text-bp-cyan',
              )} />
          }
        </div>
        <span className={cn(
          compact ? 'text-sm' : 'text-xs',
          'font-medium whitespace-nowrap',
          node.status === 'pending' ? 'text-bp-muted' : 'text-bp-text',
          clickable && 'group-hover:text-bp-cyan',
        )}>
          {node.label}
        </span>
        {statusBadge(node.status)}
      </>
    );

    if (!clickable) {
      return (
        <div className={cn('flex flex-col items-center gap-1.5 shrink-0', compact ? '' : 'min-w-[80px]')}>
          {body}
        </div>
      );
    }

    return (
      <button
        type="button"
        onClick={() => onNodeClick?.(node)}
        className={cn(
          'group flex flex-col items-center gap-1.5 shrink-0 rounded-bp p-1 -m-1',
          'cursor-pointer transition-colors hover:bg-bp-panel/40',
          compact ? '' : 'min-w-[80px]',
        )}
        title={`前往${node.label}`}
      >
        {body}
      </button>
    );
  };

  return (
    <div className={cn('space-y-4', className)}>
      <div className="hidden md:block overflow-x-auto">
        <div className="flex items-center min-w-max py-3">
          {nodes.map((node, idx) => {
            const isLast = idx === nodes.length - 1;
            return (
              <div key={node.id} className="flex items-center">
                {renderNodeBody(node)}
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

      <div className="md:hidden space-y-0">
        {nodes.map((node, idx) => {
          const isLast = idx === nodes.length - 1;
          return (
            <div key={node.id} className="flex gap-3">
              <div className="flex flex-col items-center">
                {clickable ? (
                  <button
                    type="button"
                    onClick={() => onNodeClick?.(node)}
                    className="group shrink-0 rounded-full"
                    title={`前往${node.label}`}
                  >
                    <div className={cn(
                      'w-9 h-9 rounded-full border-2 flex items-center justify-center transition-all duration-300',
                      nodeRingStyle(node.status),
                      'group-hover:border-bp-cyan/50',
                    )}>
                      {node.status === 'running'
                        ? <Loader2 className="w-4 h-4 animate-spin text-bp-cyan" />
                        : (() => {
                          const Icon = node.icon;
                          return <Icon className={cn('w-4 h-4',
                            node.status === 'completed' ? 'text-bp-green'
                            : node.status === 'error' ? 'text-danger-400'
                            : 'text-bp-muted',
                            'group-hover:text-bp-cyan',
                          )} />;
                        })()
                      }
                    </div>
                  </button>
                ) : (
                  <div className={cn(
                    'w-9 h-9 rounded-full border-2 flex items-center justify-center transition-all duration-300 shrink-0',
                    nodeRingStyle(node.status),
                  )}>
                    {node.status === 'running'
                      ? <Loader2 className="w-4 h-4 animate-spin text-bp-cyan" />
                      : (() => {
                        const Icon = node.icon;
                        return <Icon className={cn('w-4 h-4',
                          node.status === 'completed' ? 'text-bp-green'
                          : node.status === 'error' ? 'text-danger-400'
                          : 'text-bp-muted',
                        )} />;
                      })()
                    }
                  </div>
                )}
                {!isLast && (
                  <div className={cn('w-0.5 flex-1 min-h-[24px] rounded-full transition-all',
                    connectorStyle(node.status, nodes[idx + 1].status),
                  )} />
                )}
              </div>
              <div className="pb-4">
                {clickable ? (
                  <button
                    type="button"
                    onClick={() => onNodeClick?.(node)}
                    className="text-left group"
                    title={`前往${node.label}`}
                  >
                    <span className={cn('text-sm font-medium group-hover:text-bp-cyan',
                      node.status === 'pending' ? 'text-bp-muted' : 'text-bp-text',
                    )}>{node.label}</span>
                    <div className="mt-1">{statusBadge(node.status)}</div>
                  </button>
                ) : (
                  <>
                    <span className={cn('text-sm font-medium',
                      node.status === 'pending' ? 'text-bp-muted' : 'text-bp-text',
                    )}>{node.label}</span>
                    <div className="mt-1">{statusBadge(node.status)}</div>
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
