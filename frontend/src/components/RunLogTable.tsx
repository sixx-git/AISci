import { useState, useMemo, useCallback, useEffect } from 'react';
import { ChevronDown, Filter, ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { RUN_LOG_STATUS_BADGE } from '@/lib/runLogStatus';
import { Button } from '@/components/Button';
import type { RunLog, RunLogStatus } from '@/types';

interface RunLogTableProps {
  logs: RunLog[];
  selectedId: string | null;
  onSelect: (log: RunLog) => void;
  className?: string;
}

const PAGE_SIZE = 10;

const statusBadge = RUN_LOG_STATUS_BADGE;

const ALL_STATUSES: RunLogStatus[] = ['success', 'running', 'failed', 'pending'];

function formatRunId(log: RunLog): string {
  const id = log.runId || log.id;
  return id.length > 12 ? `${id.slice(0, 8)}…` : id;
}

export function RunLogTable({ logs, selectedId, onSelect, className }: RunLogTableProps) {
  const [statusFilter, setStatusFilter] = useState<RunLogStatus | 'all'>('all');
  const [stageFilter, setStageFilter] = useState<string>('all');
  const [page, setPage] = useState(1);

  const stages = useMemo(() => {
    const set = new Set(logs.map((l) => l.stage));
    return Array.from(set);
  }, [logs]);

  const filtered = useMemo(() => {
    return logs.filter(
      (l) =>
        (statusFilter === 'all' || l.status === statusFilter) &&
        (stageFilter === 'all' || l.stage === stageFilter),
    );
  }, [logs, statusFilter, stageFilter]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));

  useEffect(() => {
    setPage(1);
  }, [statusFilter, stageFilter, logs.length]);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  const paged = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return filtered.slice(start, start + PAGE_SIZE);
  }, [filtered, page]);

  const clearFilters = useCallback(() => {
    setStatusFilter('all');
    setStageFilter('all');
  }, []);

  const hasFilters = statusFilter !== 'all' || stageFilter !== 'all';

  return (
    <div className={cn('space-y-4', className)}>
      {/* 筛选器 */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 text-xs text-bp-muted">
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
            ...stages.map((s) => ({ value: s, label: s })),
          ]}
          onChange={setStageFilter}
        />

        {hasFilters && (
          <button
            onClick={clearFilters}
            className="text-xs text-bp-muted hover:text-bp-text transition-colors"
          >
            清除筛选
          </button>
        )}

        <span className="text-xs text-bp-muted ml-auto">
          {filtered.length} / {logs.length} 条记录
        </span>
      </div>

      {/* 表格 */}
      <div className="rounded-lg border border-bp-border overflow-hidden">
        <table className="w-full table-fixed text-left text-sm">
          <thead>
            <tr className="bg-bp-base/60 border-b border-bp-border">
              <Th className="w-[11%]">Run ID</Th>
              <Th className="w-[18%]">运行时间</Th>
              <Th className="w-[12%]">执行阶段</Th>
              <Th className="w-[14%]">使用模型</Th>
              <Th className="w-[18%]">Prompt 版本</Th>
              <Th className="w-[9%]">耗时</Th>
              <Th className="w-[10%]">状态</Th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-12 text-center text-bp-muted text-xs">
                  无匹配记录
                </td>
              </tr>
            ) : (
              paged.map((log) => {
                const sc = statusBadge[log.status];
                const isSelected = log.id === selectedId;
                const runIdLabel = formatRunId(log);
                return (
                  <tr
                    key={log.id}
                    onClick={() => onSelect(log)}
                    className={cn(
                      'border-b border-bp-border/50 last:border-0 cursor-pointer transition-colors',
                      isSelected
                        ? 'bg-bp-cyan-tint'
                        : 'hover:bg-bp-base/40',
                    )}
                  >
                    <td className="py-3 px-3">
                      <span
                        className="font-mono text-xs text-bp-cyan truncate block"
                        title={log.runId || log.id}
                      >
                        {runIdLabel}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-xs text-bp-muted font-mono truncate" title={log.runTime}>
                      {log.runTime}
                    </td>
                    <td className="py-3 px-3">
                      <span className="text-xs text-bp-text truncate block">{log.stage}</span>
                    </td>
                    <td className="py-3 px-3 text-xs text-bp-muted font-mono truncate" title={log.model}>
                      {log.model}
                    </td>
                    <td className="py-3 px-3">
                      <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-bp-panel text-bp-muted truncate block" title={log.promptVersion}>
                        {log.promptVersion}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-xs text-bp-muted font-mono whitespace-nowrap">{log.duration}</td>
                    <td className="py-3 px-3">
                      <span className={cn('text-xs px-2 py-0.5 rounded-full border font-medium inline-flex items-center gap-1 whitespace-nowrap', sc.className)}>
                        {log.status === 'running' && <span className={cn('w-1.5 h-1.5 rounded-full animate-pulse', sc.dotClass)} />}
                        {sc.label}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {filtered.length > 0 && (
        <div className="flex items-center justify-between gap-2 pt-1">
          <span className="text-xs text-bp-muted">
            第 {page} / {totalPages} 页
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={page <= 1}
              icon={<ChevronLeft className="w-4 h-4" />}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              上一页
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              下一页
              <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function Th({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <th className={cn('py-3 px-3 text-xs text-bp-muted font-medium', className)}>
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
        className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-bp-base/70 border border-bp-border text-xs text-bp-text hover-accent-left transition-colors"
      >
        <span className="max-w-[120px] truncate">{value}</span>
        <ChevronDown className={cn('w-3 h-3 text-bp-muted transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute top-full left-0 mt-1 w-40 bg-bp-panel border border-bp-border rounded-lg shadow-xl z-20 py-1 max-h-60 overflow-auto">
            {options.map((opt) => (
              <button
                key={opt.value}
                onClick={() => { onChange(opt.value); setOpen(false); }}
                className={cn(
                  'w-full text-left px-3 py-1.5 text-xs transition-colors',
                  opt.value === value
                    ? 'text-bp-cyan bg-bp-cyan-tint'
                    : 'text-bp-muted hover:text-bp-text hover:bg-bp-surface',
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