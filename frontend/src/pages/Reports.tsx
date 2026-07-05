import { useState, useEffect, useMemo, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  FileText, Clock, ArrowRight, FlaskConical, Search, FilterX, ChevronLeft, ChevronRight, Trash2,
} from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { LoadingState } from '@/components/workspace/LoadingState';
import { ErrorState } from '@/components/workspace/ErrorState';
import { EmptyState } from '@/components/EmptyState';
import { ConfirmDeleteDialog } from '@/components/ConfirmDeleteDialog';
import { reportService, type ReportBrowseItem } from '@/services/reportService';
import { formatDate } from '@/lib/utils';
import { cn } from '@/lib/utils';

const PAGE_SIZE = 10;

const MODE_OPTIONS = [
  { value: '', label: '全部类型' },
  { value: 'general', label: '通用科学问题' },
  { value: 'federated_learning', label: '联邦学习问题' },
] as const;

const TIME_PRESETS = [
  { value: '', label: '全部时间' },
  { value: '7', label: '近 7 天' },
  { value: '30', label: '近 30 天' },
  { value: '90', label: '近 90 天' },
] as const;

const MODE_LABEL: Record<string, string> = {
  general: '通用科学问题',
  federated_learning: '联邦学习问题',
};

function resolveDateRange(
  preset: string,
  customFrom: string,
  customTo: string,
): { date_from?: string; date_to?: string } {
  if (customFrom || customTo) {
    return {
      date_from: customFrom || undefined,
      date_to: customTo || undefined,
    };
  }
  if (!preset) return {};
  const days = Number(preset);
  if (!Number.isFinite(days) || days <= 0) return {};
  const from = new Date();
  from.setDate(from.getDate() - days);
  return { date_from: from.toISOString().slice(0, 10) };
}

const selectChevronStyle = {
  backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='%2364748B' viewBox='0 0 16 16'%3E%3Cpath d='M8 11L3 6h10z'/%3E%3C/svg%3E")`,
  backgroundRepeat: 'no-repeat',
  backgroundPosition: 'right 12px center',
  paddingRight: '2.5rem',
} as const;

export function Reports() {
  const navigate = useNavigate();
  const [reports, setReports] = useState<ReportBrowseItem[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [reloadTick, setReloadTick] = useState(0);

  const [modeFilter, setModeFilter] = useState('');
  const [timePreset, setTimePreset] = useState('');
  const [customDateFrom, setCustomDateFrom] = useState('');
  const [customDateTo, setCustomDateTo] = useState('');
  const [keywordInput, setKeywordInput] = useState('');
  const [appliedKeyword, setAppliedKeyword] = useState('');

  const [deleteTarget, setDeleteTarget] = useState<ReportBrowseItem | null>(null);
  const [deleteConfirmValue, setDeleteConfirmValue] = useState('');
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const dateRange = useMemo(
    () => resolveDateRange(timePreset, customDateFrom, customDateTo),
    [timePreset, customDateFrom, customDateTo],
  );

  const hasFilters = Boolean(
    modeFilter || timePreset || customDateFrom || customDateTo || appliedKeyword,
  );

  useEffect(() => {
    setPage(1);
  }, [modeFilter, timePreset, customDateFrom, customDateTo, appliedKeyword]);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      setIsLoading(true);
      setErrorMsg(null);
      try {
        const res = await reportService.browse({
          page,
          page_size: PAGE_SIZE,
          project_mode: modeFilter || undefined,
          date_from: dateRange.date_from,
          date_to: dateRange.date_to,
          keyword: appliedKeyword || undefined,
        });

        if (cancelled) return;

        if (res.code !== 200 || !res.data) {
          setReports([]);
          setTotal(0);
          setTotalPages(0);
          setErrorMsg(res.message || '加载报告列表失败');
          return;
        }

        setReports(res.data.list ?? []);
        setTotal(res.data.pagination?.total ?? 0);
        setTotalPages(res.data.pagination?.total_pages ?? 0);
      } catch (e) {
        if (!cancelled) {
          setErrorMsg(e instanceof Error ? e.message : '加载失败');
          setReports([]);
          setTotal(0);
          setTotalPages(0);
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [page, modeFilter, dateRange, appliedKeyword, reloadTick]);

  const clearFilters = () => {
    setModeFilter('');
    setTimePreset('');
    setCustomDateFrom('');
    setCustomDateTo('');
    setKeywordInput('');
    setAppliedKeyword('');
  };

  const applyKeyword = () => {
    setAppliedKeyword(keywordInput.trim());
  };

  const openDeleteDialog = useCallback((entry: ReportBrowseItem) => {
    setDeleteTarget(entry);
    setDeleteConfirmValue('');
    setDeleteError(null);
  }, []);

  const closeDeleteDialog = useCallback(() => {
    if (isDeleting) return;
    setDeleteTarget(null);
    setDeleteConfirmValue('');
    setDeleteError(null);
  }, [isDeleting]);

  const handleDeleteReport = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    setDeletingId(deleteTarget.id);
    setDeleteError(null);
    try {
      const res = await reportService.delete(deleteTarget.id);
      if (res.code !== 200 || !res.data) {
        throw new Error(res.message || '删除失败');
      }
      closeDeleteDialog();
      setReloadTick((t) => t + 1);
      if (reports.length === 1 && page > 1) {
        setPage((p) => Math.max(1, p - 1));
      }
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : '删除失败');
    } finally {
      setIsDeleting(false);
      setDeletingId(null);
    }
  };

  const shell = (subtitle: string, children: React.ReactNode) => (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <PageHeader title="报告中心" subtitle={subtitle} />
      {children}
    </div>
  );

  const filterBar = (
    <Card className="mb-6">
      <div className="flex flex-col gap-4">
        <div className="flex flex-col lg:flex-row gap-3">
          <div className="relative flex-1 min-w-0">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-bp-muted pointer-events-none" />
            <input
              type="text"
              placeholder="搜索报告标题、项目名称或研究问题..."
              value={keywordInput}
              onChange={(e) => setKeywordInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && applyKeyword()}
              className="input-field pl-10 py-2.5 w-full"
            />
          </div>
          <Button variant="secondary" onClick={applyKeyword}>
            搜索
          </Button>
        </div>

        <div className="flex flex-col sm:flex-row flex-wrap gap-3">
          <select
            value={modeFilter}
            onChange={(e) => setModeFilter(e.target.value)}
            className="input-field py-2.5 appearance-none cursor-pointer w-full sm:w-auto sm:min-w-[160px]"
            style={selectChevronStyle}
          >
            {MODE_OPTIONS.map((opt) => (
              <option key={opt.value || 'all'} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>

          <select
            value={timePreset}
            onChange={(e) => {
              setTimePreset(e.target.value);
              setCustomDateFrom('');
              setCustomDateTo('');
            }}
            className="input-field py-2.5 appearance-none cursor-pointer w-full sm:w-auto sm:min-w-[140px]"
            style={selectChevronStyle}
          >
            {TIME_PRESETS.map((opt) => (
              <option key={opt.value || 'all'} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>

          <input
            type="date"
            value={customDateFrom}
            onChange={(e) => {
              setCustomDateFrom(e.target.value);
              setTimePreset('');
            }}
            className="input-field py-2.5 w-full sm:w-auto"
            title="开始日期"
          />
          <span className="hidden sm:flex items-center text-bp-muted text-sm">至</span>
          <input
            type="date"
            value={customDateTo}
            onChange={(e) => {
              setCustomDateTo(e.target.value);
              setTimePreset('');
            }}
            className="input-field py-2.5 w-full sm:w-auto"
            title="结束日期"
          />

          {hasFilters && (
            <button
              type="button"
              onClick={clearFilters}
              className="inline-flex items-center gap-1.5 px-3 py-2 text-sm text-bp-muted hover:text-bp-text transition-colors"
            >
              <FilterX className="w-4 h-4" />
              清除筛选
            </button>
          )}
        </div>
      </div>
    </Card>
  );

  const subtitleText = `共 ${total} 份研究报告${hasFilters ? '（已筛选）' : ''}`;

  if (isLoading && reports.length === 0) {
    return shell(
      '正在加载...',
      <>
        {filterBar}
        <Card>
          <LoadingState message="正在加载报告..." />
        </Card>
      </>,
    );
  }

  if (errorMsg && reports.length === 0) {
    return shell(
      subtitleText,
      <>
        {filterBar}
        <Card>
          <ErrorState
            message={errorMsg}
            onRetry={() => setReloadTick((t) => t + 1)}
          />
        </Card>
      </>,
    );
  }

  return shell(
    subtitleText,
    <>

      {reports.length === 0 ? (
        <Card>
          <EmptyState
            icon={<FileText className="w-8 h-8" />}
            title={hasFilters ? '没有匹配的报告' : '暂无研究报告'}
            description={
              hasFilters
                ? '尝试调整筛选条件或清除筛选器'
                : '请先创建项目并通过工作流生成研究报告'
            }
            action={
              hasFilters
                ? { label: '清除筛选', onClick: clearFilters }
                : { label: '前往项目列表', onClick: () => navigate('/') }
            }
          />
        </Card>
      ) : (
        <>
          <Card noPadding className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-bp-cyan-dim bg-bp-panel/50">
                    <th className="py-3 px-4 text-xs text-bp-muted font-medium">报告标题</th>
                    <th className="py-3 px-4 text-xs text-bp-muted font-medium hidden md:table-cell">项目</th>
                    <th className="py-3 px-4 text-xs text-bp-muted font-medium hidden lg:table-cell">问题类型</th>
                    <th className="py-3 px-4 text-xs text-bp-muted font-medium">生成时间</th>
                    <th className="py-3 px-4 text-xs text-bp-muted font-medium w-28">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {reports.map((entry) => (
                    <tr
                      key={entry.id}
                      className="border-b border-bp-border/50 last:border-0 hover:bg-bp-cyan-tint/20 transition-colors"
                    >
                      <td className="py-3 px-4 min-w-[200px]">
                        <div className="flex items-start gap-3">
                          <div className="w-8 h-8 rounded-bp bg-bp-cyan-tint border border-bp-cyan/20 flex items-center justify-center shrink-0 mt-0.5">
                            <FileText className="w-4 h-4 text-bp-cyan" />
                          </div>
                          <div className="min-w-0">
                            <p className="font-medium text-bp-text line-clamp-2" title={entry.title}>
                              {entry.title}
                            </p>
                            {entry.research_question && (
                              <p className="text-xs text-bp-muted mt-1 line-clamp-1" title={entry.research_question}>
                                {entry.research_question}
                              </p>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-4 hidden md:table-cell">
                        <span className="inline-flex items-center gap-1 text-bp-muted text-xs">
                          <FlaskConical className="w-3.5 h-3.5 shrink-0" />
                          <span className="truncate max-w-[180px]" title={entry.project_name}>
                            {entry.project_name}
                          </span>
                        </span>
                      </td>
                      <td className="py-3 px-4 hidden lg:table-cell">
                        <span
                          className={cn(
                            'bp-chip text-xs',
                            entry.project_mode === 'federated_learning'
                              ? 'bp-chip-cyan'
                              : 'text-bp-muted border border-bp-border',
                          )}
                        >
                          {MODE_LABEL[entry.project_mode] ?? '通用科学问题'}
                        </span>
                      </td>
                      <td className="py-3 px-4 whitespace-nowrap">
                        <span className="inline-flex items-center gap-1 text-xs text-bp-muted">
                          <Clock className="w-3.5 h-3.5" />
                          {formatDate(entry.created_at)}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <Link
                            to={`/projects/${entry.project_id}?tab=reports`}
                            className="inline-flex items-center gap-1 text-xs text-bp-cyan hover:text-bp-text transition-colors"
                          >
                            查看
                            <ArrowRight className="w-3.5 h-3.5" />
                          </Link>
                          <button
                            type="button"
                            title="删除报告"
                            disabled={deletingId === entry.id}
                            onClick={() => openDeleteDialog(entry)}
                            className="p-1.5 rounded-bp text-bp-muted hover:text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-50"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4 px-1">
              <span className="text-sm text-bp-muted">
                第 {page} / {totalPages} 页，共 {total} 条
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page <= 1 || isLoading}
                  icon={<ChevronLeft className="w-4 h-4" />}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  上一页
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page >= totalPages || isLoading}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                >
                  下一页
                  <ChevronRight className="w-4 h-4 ml-1" />
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      <ConfirmDeleteDialog
        open={Boolean(deleteTarget)}
        title="删除报告"
        itemName={deleteTarget?.title ?? ''}
        description="此操作不可撤销，将永久删除该研究报告及其 PDF/LaTeX 导出文件。"
        confirmValue={deleteConfirmValue}
        onConfirmValueChange={setDeleteConfirmValue}
        onConfirm={handleDeleteReport}
        onCancel={closeDeleteDialog}
        isLoading={isDeleting}
        error={deleteError}
      />
    </>,
  );
}