import { useState, useMemo, useCallback } from 'react';
import { Eye, ChevronDown, Filter } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { RunLog, RunLogStatus, RunLogStage } from '@/types';

interface RunLogTableProps {
  logs: RunLog[];
  selectedId: string | null;
  onSelect: (log: RunLog) => void;
  className?: string;
}

const statusBadge: Record<RunLogStatus, { label: string; className: string }> = {
  success: { label: '成功', className: 'text-green-400 bg-green-500/10 border-green-500/20' },
  running: { label: '运行中', className: 'text-blue-400 bg-blue-500/10 border-blue-500/20 animate-pulse' },
  failed:  { label: '失败', className: 'text-red-400 bg-red-500/10 border-red-500/20' },
  pending: { label: '等待中', className: 'text-gray-400 bg-gray-500/10 border-gray-500/20' },
};

const ALL_STAGES: RunLogStage[] = ['问题理解', '文献挖掘', '假设生成', '实验设计', '实验执行', '报告生成'];
const ALL_STATUSES: RunLogStatus[] = ['success', 'running', 'failed', 'pending'];

export function RunLogTable({ logs, selectedId, onSelect, className }: RunLogTableProps) {
  const [statusFilter, setStatusFilter] = useState<RunLogStatus | 'all'>('all');
  const [stageFilter, setStageFilter] = useState<RunLogStage | 'all'>('all');
  const [projectFilter, setProjectFilter] = useState<string>('all');

  // 提取唯一项目名
  const projects = useMemo(() => {
    const set = new Set(logs.map(l => l.projectName));
    return Array.from(set);
  }, [logs]);

  // 筛选
  const filtered = useMemo(() => {
    return logs.filter(l =>
      (statusFilter === 'all' || l.status === statusFilter) &&
      (stageFilter === 'all' || l.stage === stageFilter) &&
      (projectFilter === 'all' || l.projectName === projectFilter)
    );
  }, [logs, statusFilter, stageFilter, projectFilter]);

  const clearFilters = useCallback(() => {
    setStatusFilter('all');
    setStageFilter('all');
    setProjectFilter('all');
  }, []);

  const hasFilters = statusFilter !== 'all' || stageFilter !== 'all' || projectFilter !== 'all';

  return (
    <div className={cn('space-y-4', className)}>
      {/* 筛选器 */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <Filter className="w-3.5 h-3.5" />
          <span>筛选：</span>
        </div>

        {/* 按状态 */}
        <Dropdown
          label="状态"
          value={statusFilter === 'all' ? '全部状态' : statusBadge[statusFilter].label}
          options={[
            { value: 'all', label: '全部状态' },
            ...ALL_STATUSES.map(s => ({ value: s, label: statusBadge[s].label })),
          ]}
          onChange={(v) => setStatusFilter(v as RunLogStatus | 'all')}
        />

        {/* 按阶段 */}
        <Dropdown
          label="阶段"
          value={stageFilter === 'all' ? '全部阶段' : stageFilter}
          options={[
            { value: 'all', label: '全部阶段' },
            ...ALL_STAGES.map(s => ({ value: s, label: s })),
          ]}
          onChange={(v) => setStageFilter(v as RunLogStage | 'all')}
        />

        {/* 按项目 */}
        <Dropdown
          label="项目"
          value={projectFilter === 'all' ? '全部项目' : projectFilter}
          options={[
            { value: 'all', label: '全部项目' },
            ...projects.map(p => ({ value: p, label: p })),
          ]}
          onChange={setProjectFilter}
        />

        {hasFilters && (
          <button
            onClick={clearFilters}
            className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
          >
            清除筛选
          </button>
        )}

        <span className="text-xs text-gray-600 ml-auto">
          {filtered.length} / {logs.length} 条记录
        </span>
      </div>

      {/* 表格 */}
      <div className="overflow-x-auto rounded-lg border border-gray-800">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="bg-gray-900/60 border-b border-gray-800">
              <Th>Run ID</Th>
              <Th>运行时间</Th>
              <Th>项目名称</Th>
              <Th>执行阶段</Th>
              <Th>使用模型</Th>
              <Th>Prompt 版本</Th>
              <Th>耗时</Th>
              <Th>状态</Th>
              <Th className="w-20">操作</Th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={9} className="py-12 text-center text-gray-500 text-xs">
                  无匹配记录
                </td>
              </tr>
            ) : (
              filtered.map((log) => {
                const sc = statusBadge[log.status];
                const isSelected = log.id === selectedId;
                return (
                  <tr
                    key={log.id}
                    onClick={() => onSelect(log)}
                    className={cn(
                      'border-b border-gray-800/50 last:border-0 cursor-pointer transition-colors',
                      isSelected
                        ? 'bg-primary-500/10'
                        : 'hover:bg-gray-900/40',
                    )}
                  >
                    <td className="py-3 px-4">
                      <span className="font-mono text-xs text-primary-400">{log.id}</span>
                    </td>
                    <td className="py-3 px-4 text-xs text-gray-400 font-mono whitespace-nowrap">{log.runTime}</td>
                    <td className="py-3 px-4 text-xs text-gray-300 whitespace-nowrap">{log.projectName}</td>
                    <td className="py-3 px-4">
                      <span className="text-xs text-gray-300">{log.stage}</span>
                    </td>
                    <td className="py-3 px-4 text-xs text-gray-400 font-mono">{log.model}</td>
                    <td className="py-3 px-4">
                      <span className="text-[11px] font-mono px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">{log.promptVersion}</span>
                    </td>
                    <td className="py-3 px-4 text-xs text-gray-500 font-mono">{log.duration}</td>
                    <td className="py-3 px-4">
                      <span className={cn('text-[11px] px-2 py-0.5 rounded-full border font-medium inline-flex items-center gap-1', sc.className)}>
                        {log.status === 'running' && <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />}
                        {sc.label}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <button
                        onClick={(e) => { e.stopPropagation(); onSelect(log); }}
                        className={cn(
                          'p-1.5 rounded-lg transition-colors',
                          isSelected
                            ? 'bg-primary-500/20 text-primary-400'
                            : 'hover:bg-gray-800 text-gray-500 hover:text-gray-300',
                        )}
                        title="查看详情"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Th({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <th className={cn('py-3 px-4 text-xs text-gray-500 font-medium', className)}>
      {children}
    </th>
  );
}

// ---------- 内联 Dropdown ----------

interface DropdownOption {
  value: string;
  label: string;
}

function Dropdown({ label: _l, value, options, onChange }: {
  label: string;
  value: string;
  options: DropdownOption[];
  onChange: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-gray-900/70 border border-gray-700 text-xs text-gray-300 hover:border-gray-600 transition-colors"
      >
        <span className="max-w-[120px] truncate">{value}</span>
        <ChevronDown className={cn('w-3 h-3 text-gray-500 transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute top-full left-0 mt-1 w-40 bg-gray-800 border border-gray-700 rounded-lg shadow-xl z-20 py-1 max-h-60 overflow-auto">
            {options.map((opt) => (
              <button
                key={opt.value}
                onClick={() => { onChange(opt.value); setOpen(false); }}
                className={cn(
                  'w-full text-left px-3 py-1.5 text-xs transition-colors',
                  opt.value === value
                    ? 'text-primary-400 bg-primary-500/10'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-gray-700',
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}