import { useState } from 'react';
import { X, AlertCircle, BarChart3, Terminal, FileCode } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { RunLog, RunLogStatus } from '@/types';

interface RunLogDetailProps {
  log: RunLog | null;
  onClose: () => void;
}

const statusBadge: Record<RunLogStatus, { label: string; className: string }> = {
  success: { label: '成功', className: 'text-green-400 bg-green-500/10 border-green-500/20' },
  running: { label: '运行中', className: 'text-blue-400 bg-blue-500/10 border-blue-500/20' },
  failed:  { label: '失败', className: 'text-red-400 bg-red-500/10 border-red-500/20' },
  pending: { label: '等待中', className: 'text-gray-400 bg-gray-500/10 border-gray-500/20' },
};

export function RunLogDetail({ log, onClose }: RunLogDetailProps) {
  const [activeTab, setActiveTab] = useState<'input' | 'output' | 'error' | 'params'>('output');

  if (!log) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-gray-500">
        <Terminal className="w-12 h-12 mb-3 opacity-30" />
        <p className="text-sm">选择一条运行记录查看详情</p>
      </div>
    );
  }

  const tabs = [
    { key: 'output' as const, label: '输出快照', icon: Terminal },
    { key: 'input' as const,  label: '输入摘要', icon: FileCode },
    { key: 'params' as const, label: '模型参数', icon: BarChart3 },
    ...(log.errorMessage ? [{ key: 'error' as const, label: '错误信息', icon: AlertCircle }] : []),
  ];

  const sc = statusBadge[log.status];

  return (
    <div className="space-y-4">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold text-white flex items-center gap-2">
            <span className="font-mono text-sm text-primary-400">{log.id}</span>
            <span className={cn('text-[11px] px-2 py-0.5 rounded-full border font-medium', sc.className)}>
              {sc.label}
            </span>
          </h3>
          <p className="text-xs text-gray-500 mt-1">{log.projectName} · {log.stage} · {log.runTime}</p>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg hover:bg-gray-800 text-gray-500 hover:text-gray-300 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* 基础信息 */}
      <div className="grid grid-cols-2 gap-3">
        <InfoItem label="运行时间" value={log.duration} />
        <InfoItem label="使用模型" value={log.model} />
        <InfoItem label="Prompt 版本" value={log.promptVersion} />
        <InfoItem label="开始时间" value={log.timestampStart ? formatTS(log.timestampStart) : '-'} />
        {log.timestampEnd && (
          <InfoItem label="结束时间" value={formatTS(log.timestampEnd)} />
        )}
      </div>

      {/* Tab 切换 */}
      <div className="flex items-center gap-1 p-1 bg-gray-900/70 rounded-lg border border-gray-800">
        {tabs.map((t) => {
          const Icon = t.icon;
          return (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key)}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors',
                activeTab === t.key
                  ? 'bg-gray-700 text-white'
                  : 'text-gray-500 hover:text-gray-300',
              )}
            >
              <Icon className="w-3.5 h-3.5" />
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Tab 内容 */}
      <div className="p-4 rounded-lg bg-gray-950/80 border border-gray-800 font-mono text-xs text-gray-300 max-h-[340px] overflow-auto whitespace-pre-wrap leading-relaxed">
        {activeTab === 'output' && log.outputSnapshot}

        {activeTab === 'input' && log.inputSummary}

        {activeTab === 'error' && (
          <div className="text-red-400">
            <div className="flex items-start gap-2 mb-2">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span className="font-semibold">错误详情</span>
            </div>
            <p className="text-red-300/80">{log.errorMessage}</p>
          </div>
        )}

        {activeTab === 'params' && (
          <div className="space-y-2">
            {log.modelParams && Object.entries(log.modelParams).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between py-1.5 border-b border-gray-800/50 last:border-0">
                <span className="text-gray-400">{k}</span>
                <span className="text-primary-400 font-semibold">{v}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="p-2.5 rounded-lg bg-gray-900/60 border border-gray-800/50">
      <p className="text-[10px] text-gray-500 mb-0.5">{label}</p>
      <p className="text-xs text-gray-200 font-medium">{value}</p>
    </div>
  );
}

function formatTS(iso: string): string {
  try {
    return new Date(iso).toLocaleString('zh-CN', { hour12: false });
  } catch {
    return iso;
  }
}