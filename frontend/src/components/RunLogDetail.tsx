import { useState } from 'react';
import { X, AlertCircle, BarChart3, Terminal, FileCode } from 'lucide-react';
import { cn } from '@/lib/utils';
import { RUN_LOG_STATUS_BADGE } from '@/lib/runLogStatus';
import type { RunLog } from '@/types';

interface RunLogDetailProps {
  log: RunLog | null;
  onClose?: () => void;
  showClose?: boolean;
}

const DETAIL_TABS = [
  { key: 'output' as const, label: '输出快照', icon: Terminal },
  { key: 'input' as const, label: '输入摘要', icon: FileCode },
  { key: 'params' as const, label: '模型参数', icon: BarChart3 },
];

export function RunLogDetail({ log, onClose, showClose = false }: RunLogDetailProps) {
  const [activeTab, setActiveTab] = useState<'input' | 'output' | 'error' | 'params'>('output');

  if (!log) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-bp-muted">
        <Terminal className="w-12 h-12 mb-3 opacity-30" />
        <p className="text-sm">选择一条运行记录查看详情</p>
      </div>
    );
  }

  const tabs = [
    ...DETAIL_TABS,
    ...(log.errorMessage ? [{ key: 'error' as const, label: '错误信息', icon: AlertCircle }] : []),
  ];

  const sc = RUN_LOG_STATUS_BADGE[log.status];

  return (
    <div className="space-y-4 h-full flex flex-col">
      <div className="flex items-start justify-between gap-3 shrink-0">
        <div className="min-w-0">
          <h3 className="text-base font-semibold text-bp-text flex items-center gap-2 flex-wrap">
            <span className="font-mono text-sm text-bp-cyan truncate">{log.id}</span>
            <span className={cn('text-xs px-2 py-0.5 rounded-bp border font-medium shrink-0', sc.className)}>
              {sc.label}
            </span>
          </h3>
          <p className="text-xs text-bp-muted mt-1 truncate">
            {log.projectName} · {log.stage} · {log.runTime}
          </p>
        </div>
        {showClose && onClose && (
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-bp hover:bg-bp-panel text-bp-muted hover:text-bp-text transition-colors shrink-0"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 shrink-0">
        <InfoItem label="运行时间" value={log.duration} />
        <InfoItem label="使用模型" value={log.model} />
        <InfoItem label="Prompt 版本" value={log.promptVersion} />
        <InfoItem label="开始时间" value={log.timestampStart ? formatTS(log.timestampStart) : '-'} />
        {log.timestampEnd && (
          <InfoItem label="结束时间" value={formatTS(log.timestampEnd)} className="col-span-2" />
        )}
      </div>

      <div className="bp-tab-nav shrink-0">
        <nav className="flex gap-1 overflow-x-auto -mb-px">
          {tabs.map((t) => {
            const Icon = t.icon;
            const isActive = activeTab === t.key;
            return (
              <button
                key={t.key}
                type="button"
                onClick={() => setActiveTab(t.key)}
                className={cn('bp-tab text-xs', isActive && 'bp-tab-active')}
              >
                <Icon className="w-3.5 h-3.5 shrink-0" />
                {t.label}
              </button>
            );
          })}
        </nav>
      </div>

      <div className="flex-1 min-h-[240px] p-4 rounded-bp bg-bp-base border border-bp-border font-mono text-xs text-bp-text overflow-auto whitespace-pre-wrap leading-relaxed">
        {activeTab === 'output' && (log.outputSnapshot || '—')}

        {activeTab === 'input' && (log.inputSummary || '—')}

        {activeTab === 'error' && (
          <div className="text-danger-400">
            <div className="flex items-start gap-2 mb-2">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span className="font-semibold">错误详情</span>
            </div>
            <p className="text-danger-300/80">{log.errorMessage}</p>
          </div>
        )}

        {activeTab === 'params' && (
          <div className="space-y-2">
            {log.modelParams && Object.keys(log.modelParams).length > 0 ? (
              Object.entries(log.modelParams).map(([k, v]) => (
                <div key={k} className="flex items-center justify-between py-1.5 border-b border-bp-border/50 last:border-0">
                  <span className="text-bp-muted">{k}</span>
                  <span className="text-bp-cyan font-semibold">{v}</span>
                </div>
              ))
            ) : (
              <span className="text-bp-muted">无模型参数记录</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function InfoItem({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div className={cn('p-2.5 rounded-bp bg-bp-panel/50 border border-bp-border', className)}>
      <div className="text-xs text-bp-muted uppercase tracking-wide mb-0.5">{label}</div>
      <div className="text-xs text-bp-text font-mono truncate" title={value}>{value}</div>
    </div>
  );
}

function formatTS(iso: string): string {
  try {
    return new Date(iso).toLocaleString('zh-CN');
  } catch {
    return iso;
  }
}
