import { Play, Pause, RotateCcw } from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import type { AgentNodeData } from '@/types';

interface WorkflowActionBarProps {
  nodes: AgentNodeData[];
  isRunning: boolean;
  isPaused?: boolean;
  pauseRequested?: boolean;
  onRunAll: () => void;
  onPause: () => void;
  onResume?: () => void;
  onReset: () => void;
}

export function WorkflowActionBar({
  nodes,
  isRunning,
  isPaused = false,
  pauseRequested = false,
  onRunAll,
  onPause,
  onResume,
  onReset,
}: WorkflowActionBarProps) {
  const completed = nodes.filter((n) => n.status === 'completed').length;
  const total = nodes.length;
  const running = nodes.filter((n) => n.status === 'running').length;
  const failed = nodes.filter((n) => n.status === 'failed').length;

  return (
    <Card className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
      <div className="flex items-center gap-3">
        <Button
          variant="primary"
          icon={<Play className="w-4 h-4" />}
          onClick={isPaused && onResume ? onResume : onRunAll}
          disabled={isRunning && !isPaused}
        >
          {isPaused ? '继续运行' : isRunning ? '运行中…' : '运行全部流程'}
        </Button>
        <Button
          variant="secondary"
          icon={<Pause className="w-4 h-4" />}
          onClick={onPause}
          disabled={!isRunning || isPaused || pauseRequested}
        >
          {pauseRequested ? '暂停中…' : '暂停'}
        </Button>
        <Button
          variant="secondary"
          icon={<RotateCcw className="w-4 h-4" />}
          onClick={onReset}
          disabled={isRunning && !isPaused}
        >
          重置
        </Button>
      </div>

      <div className="flex items-center gap-4 text-xs">
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-bp-green" />
          <span className="text-bp-muted">已完成</span>
          <span className="text-bp-green font-mono font-bold">{completed}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-bp-cyan animate-pulse" />
          <span className="text-bp-muted">运行中</span>
          <span className="text-bp-cyan font-mono font-bold">{running}</span>
        </div>
        {failed > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-danger-400" />
            <span className="text-bp-muted">失败</span>
            <span className="text-danger-400 font-mono font-bold">{failed}</span>
          </div>
        )}
        <div className="text-bp-muted/70">
          {completed}/{total}
        </div>
      </div>
    </Card>
  );
}
