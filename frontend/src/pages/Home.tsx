import { useState, useMemo, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Plus, Search, FlaskConical, Calendar, ArrowRight, FilterX, Trash2,
} from 'lucide-react';
import { projectService } from '@/services';
import { formatDate } from '@/lib/utils';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { StatusBadge } from '@/components/StatusBadge';
import { PageHeader } from '@/components/PageHeader';
import { EmptyState } from '@/components/EmptyState';
import { LoadingState } from '@/components/workspace/LoadingState';
import { ErrorState } from '@/components/workspace/ErrorState';
import { RecentPipelineSection } from '@/components/workspace/RecentPipelineSection';
import { ConfirmDeleteDialog } from '@/components/ConfirmDeleteDialog';
import { useLatestPipelineRuns } from '@/hooks/useLatestPipelineRuns';
import { resolveResearchField } from '@/lib/researchField';
import { statusBadgeLabel } from '@/lib/projectStatus';
import type { ProjectOverview } from '@/types';

const STATUS_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'pending', label: '未开始' },
  { value: 'running', label: '运行中' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '失败' },
] as const;

const selectChevronStyle = {
  backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='%2364748B' viewBox='0 0 16 16'%3E%3Cpath d='M8 11L3 6h10z'/%3E%3C/svg%3E")`,
  backgroundRepeat: 'no-repeat',
  backgroundPosition: 'right 12px center',
  paddingRight: '2.5rem',
} as const;

export function Home() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [projects, setProjects] = useState<ProjectOverview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);
  const [deleteConfirmInput, setDeleteConfirmInput] = useState('');

  const {
    rows: recentPipelineRows,
    loading: pipelineLoading,
    getDisplayStatus,
    pipelineStatusByProjectId,
  } = useLatestPipelineRuns(projects);

  const isApiSuccess = (response: { code?: number; message?: string }) =>
    Number(response?.code) === 200 || Boolean(response?.message?.includes('成功'));

  const hasRunningPipeline = useMemo(() => {
    for (const run of pipelineStatusByProjectId.values()) {
      if (run.status === 'running') return true;
    }
    return false;
  }, [pipelineStatusByProjectId]);

  const pipelineSyncKey = useMemo(
    () => [...pipelineStatusByProjectId.entries()]
      .map(([id, run]) => `${id}:${run.status}:${run.completed_at || run.created_at || ''}`)
      .sort()
      .join('|'),
    [pipelineStatusByProjectId],
  );

  const lastSyncedPipelineKeyRef = useRef('');

  useEffect(() => {
    let cancelled = false;

    async function loadProjects() {
      setLoading(true);
      setError(null);
      try {
        const response = await projectService.getProjects();
        if (cancelled) return;
        if (response.code === 200) {
          const list = (response.data as { list?: ProjectOverview[] })?.list ?? response.data ?? [];
          setProjects(Array.isArray(list) ? list : []);
        } else {
          setError(response.message || '获取项目列表失败');
        }
      } catch (err: unknown) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : '获取项目列表失败，请检查后端服务是否启动');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadProjects();
    return () => { cancelled = true; };
  }, []);

  // Pipeline 回填 research_domain 后，刷新项目列表以同步首页 chip
  useEffect(() => {
    if (pipelineLoading || !pipelineSyncKey) return undefined;
    if (lastSyncedPipelineKeyRef.current === pipelineSyncKey) return undefined;
    lastSyncedPipelineKeyRef.current = pipelineSyncKey;

    let cancelled = false;
    (async () => {
      try {
        const response = await projectService.getProjects();
        if (cancelled || response.code !== 200) return;
        const list = (response.data as { list?: ProjectOverview[] })?.list ?? response.data ?? [];
        if (Array.isArray(list)) setProjects(list);
      } catch {
        /* 静默刷新失败不影响首页主流程 */
      }
    })();

    return () => { cancelled = true; };
  }, [pipelineLoading, pipelineSyncKey]);

  useEffect(() => {
    if (!hasRunningPipeline) return undefined;
    const timer = setInterval(async () => {
      try {
        const response = await projectService.getProjects();
        if (response.code !== 200) return;
        const list = (response.data as { list?: ProjectOverview[] })?.list ?? response.data ?? [];
        if (Array.isArray(list)) setProjects(list);
      } catch {
        /* ignore */
      }
    }, 5000);
    return () => clearInterval(timer);
  }, [hasRunningPipeline]);

  const filtered = useMemo(() => {
    let list = projects;
    if (search.trim()) {
      const kw = search.trim().toLowerCase();
      list = list.filter(
        (p) => {
          const field = resolveResearchField(p, p.id);
          return (
            p.name.toLowerCase().includes(kw)
            || field.toLowerCase().includes(kw)
            || (p.description && p.description.toLowerCase().includes(kw))
          );
        },
      );
    }
    if (statusFilter) {
      list = list.filter((p) => getDisplayStatus(p) === statusFilter);
    }
    return list;
  }, [search, statusFilter, projects, getDisplayStatus]);

  const clearFilters = () => {
    setSearch('');
    setStatusFilter('');
  };

  const openDeleteDialog = (projectId: string, projectName: string) => {
    setDeleteTarget({ id: projectId, name: projectName });
    setDeleteConfirmInput('');
    setDeleteError(null);
  };

  const closeDeleteDialog = () => {
    if (deletingId) return;
    setDeleteTarget(null);
    setDeleteConfirmInput('');
    setDeleteError(null);
  };

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return;
    setDeletingId(deleteTarget.id);
    setDeleteError(null);
    try {
      const response = await projectService.deleteProject(deleteTarget.id);
      if (isApiSuccess(response)) {
        setProjects((prev) => prev.filter((p) => p.id !== deleteTarget.id));
        setDeleteTarget(null);
        setDeleteConfirmInput('');
      } else {
        setDeleteError(response.message || '删除项目失败');
      }
    } catch (err: unknown) {
      setDeleteError(err instanceof Error ? err.message : '删除项目失败');
    } finally {
      setDeletingId(null);
    }
  };

  const hasFilters = search.trim() !== '' || statusFilter !== '';

  const projectCount = projects.length;
  const completedCount = projects.filter((p) => getDisplayStatus(p) === 'completed').length;
  const runningCount = projects.filter((p) => getDisplayStatus(p) === 'running').length;
  const pendingCount = projects.filter((p) => getDisplayStatus(p) === 'pending').length;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <PageHeader
        title="项目工作台"
        subtitle="搜索、浏览和管理您的 AI 科研项目"
        actions={
          <div className="flex flex-wrap gap-2">
            <Link to="/projects/new">
              <Button icon={<Plus className="w-4 h-4" />}>创建新项目</Button>
            </Link>
          </div>
        }
      />

      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-bp-muted pointer-events-none" />
          <input
            type="text"
            placeholder="搜索项目名称、领域或描述..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input-field pl-10 py-2.5"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="input-field py-2.5 appearance-none cursor-pointer w-full sm:w-auto sm:min-w-[140px]"
          style={selectChevronStyle}
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        {hasFilters && (
          <button
            type="button"
            onClick={clearFilters}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-sm text-bp-muted hover:text-bp-text transition-colors"
          >
            <FilterX className="w-4 h-4" />
            清除
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div className="bp-metric-box">
          <div className="text-bp-metric font-bold text-bp-cyan">{projectCount}</div>
          <div className="text-bp-muted text-sm">总项目数</div>
        </div>
        <div className="bp-metric-box">
          <div className="text-bp-metric font-bold text-bp-green">{completedCount}</div>
          <div className="text-bp-muted text-sm">已完成</div>
        </div>
        <div className="bp-metric-box">
          <div className="text-bp-metric font-bold text-bp-cyan">{runningCount}</div>
          <div className="text-bp-muted text-sm">运行中</div>
        </div>
        <div className="bp-metric-box">
          <div className="text-bp-metric font-bold text-bp-muted">{pendingCount}</div>
          <div className="text-bp-muted text-sm">未开始</div>
        </div>
      </div>

      {!loading && !error && projects.length > 0 && (
        <RecentPipelineSection rows={recentPipelineRows} loading={pipelineLoading} />
      )}

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-bp-text">我的项目</h2>
          {!loading && !error && hasFilters && (
            <span className="text-sm text-bp-muted">共 {filtered.length} 个匹配结果</span>
          )}
        </div>

        {deleteError && !deleteTarget && (
          <div className="rounded-bp border border-danger-500/30 bg-danger-500/10 px-4 py-3 text-sm text-danger-400">
            {deleteError}
          </div>
        )}

        {loading ? (
          <Card>
            <LoadingState message="正在加载项目列表..." />
          </Card>
        ) : error ? (
          <Card>
            <ErrorState
              message={error}
              onRetry={() => window.location.reload()}
            />
          </Card>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={hasFilters ? <Search className="w-8 h-8" /> : <FlaskConical className="w-8 h-8" />}
            title={hasFilters ? '未找到匹配的项目' : '暂无项目，请创建新项目。'}
            description={
              hasFilters
                ? '尝试调整搜索条件或清除筛选器'
                : '创建您的第一个 AI 科研项目'
            }
            action={
              hasFilters
                ? { label: '清除筛选', onClick: clearFilters }
                : { label: '创建项目', onClick: () => navigate('/projects/new') }
            }
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((project) => (
              <Card key={project.id} hover className="h-full transition-all duration-200 group-hover:shadow-bp-glow relative">
                <div className="flex items-start justify-between mb-4">
                  <div className="w-10 h-10 bg-bp-cyan-tint border border-bp-cyan/20 rounded-bp flex items-center justify-center">
                    <FlaskConical className="w-5 h-5 text-bp-cyan" />
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusBadge
                      status={getDisplayStatus(project)}
                      label={statusBadgeLabel(
                        getDisplayStatus(project),
                        pipelineStatusByProjectId.get(project.id)?.status,
                        pipelineStatusByProjectId.has(project.id),
                      )}
                    />
                    <button
                      type="button"
                      title="删除项目"
                      disabled={deletingId === project.id}
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        openDeleteDialog(project.id, project.name);
                      }}
                      className="p-1.5 rounded-bp text-bp-muted hover:text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-50"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
                <Link to={`/projects/${project.id}`} className="block group">
                  <h3 className="font-semibold text-bp-text mb-2 group-hover:text-bp-cyan transition-colors">
                    {project.name}
                  </h3>
                  {project.description && (
                    <p className="text-sm text-bp-muted line-clamp-2 mb-3">
                      {project.description}
                    </p>
                  )}
                  <div className="flex items-center gap-2 mb-3">
                    <span className="bp-chip bp-chip-cyan text-xs">
                      {resolveResearchField(project, project.id)}
                    </span>
                  </div>
                  <div className="flex items-center text-bp-muted text-sm">
                    <Calendar className="w-4 h-4 mr-2" />
                    {formatDate(project.created_at)}
                  </div>
                  <div className="mt-4 pt-4 border-t border-bp-cyan-dim flex items-center justify-between">
                    <span className="text-sm text-bp-cyan">进入项目</span>
                    <ArrowRight className="w-4 h-4 text-bp-cyan group-hover:translate-x-1 transition-transform" />
                  </div>
                </Link>
              </Card>
            ))}
          </div>
        )}
      </div>

      <ConfirmDeleteDialog
        open={deleteTarget !== null}
        itemName={deleteTarget?.name ?? ''}
        confirmValue={deleteConfirmInput}
        onConfirmValueChange={setDeleteConfirmInput}
        onConfirm={() => { void handleConfirmDelete(); }}
        onCancel={closeDeleteDialog}
        isLoading={deletingId !== null}
        error={deleteError}
      />

      <footer className="mt-12 pt-6 border-t border-bp-cyan-dim text-center text-bp-muted text-xs">
        [AISci] · Blueprint UI · 多智能体科研工作台
      </footer>
    </div>
  );
}
