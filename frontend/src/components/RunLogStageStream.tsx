import { cn } from '@/lib/utils';
import { ListTree } from 'lucide-react';
import { Card } from '@/components/Card';
import { RUN_LOG_STATUS_BADGE } from '@/lib/runLogStatus';
import type { RunLog } from '@/types';

interface RunLogStageStreamProps {
  logs: RunLog[];
  selectedLog: RunLog | null;
  onSelect: (log: RunLog) => void;
}

/** 运行日志右侧：当前 Pipeline 各阶段执行流 */
export function RunLogStageStream({ logs, selectedLog, onSelect }: RunLogStageStreamProps) {
  const runId = selectedLog?.runId;
  const stageLogs = runId
    ? logs.filter((l) => l.runId === runId)
    : [];

  return (
    <Card className="h-full flex flex-col">
      <div className="flex items-center gap-2 mb-4 shrink-0">
        <ListTree className="w-4 h-4 text-bp-cyan" />
        <div>
          <h3 className="text-sm font-semibold text-bp-text">阶段日志流</h3>
          <p className="text-xs text-bp-muted">
            {runId ? `Pipeline ${runId.slice(0, 8)}…` : '选择记录查看阶段流'}
          </p>
        </div>
      </div>

      {!selectedLog || stageLogs.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-bp-muted text-xs text-center py-8">
          暂无阶段日志
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto space-y-1 min-h-0 max-h-[520px]">
          {stageLogs.map((log) => {
            const sc = RUN_LOG_STATUS_BADGE[log.status];
            const isActive = log.id === selectedLog.id;
            return (
              <button
                key={log.id}
                type="button"
                onClick={() => onSelect(log)}
                className={cn(
                  'w-full text-left px-3 py-2.5 rounded-bp border transition-colors',
                  isActive
                    ? 'border-bp-cyan/40 bg-bp-cyan-tint'
                    : 'border-transparent hover:bg-bp-panel/60 hover:border-bp-border',
                )}
              >
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="text-xs font-medium text-bp-text truncate">{log.stage}</span>
                  <span className={cn('text-[10px] px-1.5 py-0.5 rounded-bp border shrink-0', sc.className)}>
                    {sc.label}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-[10px] text-bp-muted font-mono">
                  <span className={cn('w-1.5 h-1.5 rounded-full shrink-0', sc.dotClass)} />
                  <span>{log.duration}</span>
                  <span className="truncate">{log.model}</span>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </Card>
  );
}
