import { useState, useMemo, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Plus, Search, FlaskConical, Calendar, ArrowRight, FilterX, AlertTriangle,
} from 'lucide-react';
import { projectService } from '@/services';
import { formatDate } from '@/lib/utils';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { StatusBadge } from '@/components/StatusBadge';
import type { StatusType } from '@/components/StatusBadge';
import { PageHeader } from '@/components/PageHeader';
import { EmptyState } from '@/components/EmptyState';
import type { ProjectOverview } from '@/types';

const STATUS_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'draft', label: '草稿' },
  { value: 'running', label: '运行中' },
  { value: 'completed', label: '已完成' },
] as const;

export function Home() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [projects, setProjects] = useState<ProjectOverview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  const filtered = useMemo(() => {
    let list = projects;
    if (search.trim()) {
      const kw = search.trim().toLowerCase();
      list = list.filter(
        (p) =>
          p.name.toLowerCase().includes(kw) ||
          (p.research_field && p.research_field.toLowerCase().includes(kw)) ||
          (p.description && p.description.toLowerCase().includes(kw)),
      );
    }
    if (statusFilter) {
      list = list.filter((p) => p.status === statusFilter);
    }
    return list;
  }, [search, statusFilter, projects]);

  const clearFilters = () => {
    setSearch('');
    setStatusFilter('');
  };

  const hasFilters = search.trim() !== '' || statusFilter !== '';

  const projectCount = projects.length;
  const completedCount = projects.filter((p) => p.status === 'completed').length;
  const runningCount = projects.filter((p) => p.status === 'running').length;
  const draftCount = projects.filter((p) => p.status === 'draft').length;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <PageHeader
        title="项目工作台"
        subtitle="搜索、浏览和管理您的 AI 科研项目"
        actions={
          <Link to="/projects/new">
            <Button icon={<Plus className="w-4 h-4" />}>创建新项目</Button>
          </Link>
        }
      />

      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            type="text"
            placeholder="搜索项目名称、领域或描述..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-gray-900 border border-gray-700 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-primary-500 transition-colors"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-4 py-2.5 bg-gray-900 border border-gray-700 rounded-lg text-sm text-white focus:outline-none focus:border-primary-500 transition-colors appearance-none cursor-pointer"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='%236b7280' viewBox='0 0 16 16'%3E%3Cpath d='M8 11L3 6h10z'/%3E%3C/svg%3E")`,
            backgroundRepeat: 'no-repeat',
            backgroundPosition: 'right 12px center',
            paddingRight: '2.5rem',
          }}
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        {hasFilters && (
          <button
            onClick={clearFilters}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-sm text-gray-400 hover:text-gray-200 transition-colors"
          >
            <FilterX className="w-4 h-4" />
            清除
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <Card className="text-center">
          <div className="text-2xl font-bold text-primary-400">{projectCount}</div>
          <div className="text-gray-400 text-sm mt-1">总项目数</div>
        </Card>
        <Card className="text-center">
          <div className="text-2xl font-bold text-green-400">{completedCount}</div>
          <div className="text-gray-400 text-sm mt-1">已完成</div>
        </Card>
        <Card className="text-center">
          <div className="text-2xl font-bold text-blue-400">{runningCount}</div>
          <div className="text-gray-400 text-sm mt-1">运行中</div>
        </Card>
        <Card className="text-center">
          <div className="text-2xl font-bold text-gray-400">{draftCount}</div>
          <div className="text-gray-400 text-sm mt-1">草稿</div>
        </Card>
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-white">我的项目</h2>
          {!loading && !error && hasFilters && (
            <span className="text-sm text-gray-500">共 {filtered.length} 个匹配结果</span>
          )}
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => (
              <Card key={i} className="animate-pulse">
                <div className="h-4 bg-dark-700 rounded w-3/4 mb-2" />
                <div className="h-3 bg-dark-700 rounded w-1/2" />
                <div className="h-3 bg-dark-700 rounded w-1/4 mt-4" />
              </Card>
            ))}
          </div>
        ) : error ? (
          <Card className="border-red-800/30 bg-red-950/20">
            <div className="text-center py-8">
              <AlertTriangle className="w-10 h-10 text-red-400 mx-auto mb-3" />
              <p className="text-red-400 mb-2">加载失败</p>
              <p className="text-gray-400 text-sm mb-4">{error}</p>
              <Button onClick={() => window.location.reload()} variant="secondary">重试</Button>
            </div>
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
              <Link
                key={project.id}
                to={`/projects/${project.id}`}
                className="block group"
              >
                <Card className="h-full hover:border-primary-600/50 transition-all duration-200 group-hover:shadow-xl group-hover:shadow-primary-900/10">
                  <div className="flex items-start justify-between mb-4">
                    <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-primary-700 rounded-lg flex items-center justify-center">
                      <FlaskConical className="w-5 h-5 text-white" />
                    </div>
                    <StatusBadge
                      status={(project.status as StatusType) || 'draft'}
                    />
                  </div>
                  <h3 className="font-semibold text-white mb-2 group-hover:text-primary-400 transition-colors">
                    {project.name}
                  </h3>
                  {project.description && (
                    <p className="text-sm text-gray-400 line-clamp-2 mb-3">
                      {project.description}
                    </p>
                  )}
                  <div className="flex items-center gap-2 mb-3">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] bg-primary-500/10 text-primary-400 border border-primary-500/20">
                      {project.research_field || '未知领域'}
                    </span>
                  </div>
                  <div className="flex items-center text-gray-500 text-sm">
                    <Calendar className="w-4 h-4 mr-2" />
                    {formatDate(project.created_at)}
                  </div>
                  <div className="mt-4 pt-4 border-t border-dark-700 flex items-center justify-between">
                    <span className="text-sm text-primary-400">进入项目</span>
                    <ArrowRight className="w-4 h-4 text-primary-400 group-hover:translate-x-1 transition-transform" />
                  </div>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
