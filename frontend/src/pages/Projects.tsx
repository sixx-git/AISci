import { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Search, FlaskConical, Calendar, ArrowRight, FilterX } from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { StatusBadge } from '@/components/StatusBadge';
import { MOCK_PROJECT_OVERVIEW } from '@/data/mockData';
import { formatDate } from '@/lib/utils';

const PROJECTS = Object.values(MOCK_PROJECT_OVERVIEW);

const STATUS_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'draft', label: '草稿' },
  { value: 'running', label: '运行中' },
  { value: 'completed', label: '已完成' },
] as const;

export function Projects() {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const filtered = useMemo(() => {
    let list = PROJECTS;
    if (search.trim()) {
      const kw = search.trim().toLowerCase();
      list = list.filter(
        (p) =>
          p.name.toLowerCase().includes(kw) ||
          p.research_field.toLowerCase().includes(kw) ||
          (p.description && p.description.toLowerCase().includes(kw)),
      );
    }
    if (statusFilter) {
      list = list.filter((p) => p.status === statusFilter);
    }
    return list;
  }, [search, statusFilter]);

  const clearFilters = () => {
    setSearch('');
    setStatusFilter('');
  };

  const hasFilters = search.trim() !== '' || statusFilter !== '';

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">项目管理</h1>
          <p className="text-gray-400">浏览、搜索和管理您的 AI 科研项目</p>
        </div>
        <Link to="/projects/new">
          <Button icon={<Plus className="w-4 h-4" />}>创建新项目</Button>
        </Link>
      </div>

      {/* 搜索 & 筛选栏 */}
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

      {/* 统计卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Card className="text-center">
          <div className="text-2xl font-bold text-primary-400">{PROJECTS.length}</div>
          <div className="text-gray-400 text-sm mt-1">总项目数</div>
        </Card>
        <Card className="text-center">
          <div className="text-2xl font-bold text-green-400">
            {PROJECTS.filter((p) => p.status === 'completed').length}
          </div>
          <div className="text-gray-400 text-sm mt-1">已完成</div>
        </Card>
        <Card className="text-center">
          <div className="text-2xl font-bold text-blue-400">
            {PROJECTS.filter((p) => p.status === 'running').length}
          </div>
          <div className="text-gray-400 text-sm mt-1">运行中</div>
        </Card>
        <Card className="text-center">
          <div className="text-2xl font-bold text-gray-400">
            {PROJECTS.filter((p) => p.status === 'draft').length}
          </div>
          <div className="text-gray-400 text-sm mt-1">草稿</div>
        </Card>
      </div>

      {/* 项目列表 */}
      {filtered.length === 0 ? (
        <Card className="text-center py-16">
          <Search className="w-16 h-16 text-gray-600 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-300 mb-2">未找到匹配的项目</h3>
          <p className="text-gray-500 mb-4">
            {hasFilters ? '尝试调整搜索条件或清除筛选器' : '还没有项目，点击上方按钮创建一个'}
          </p>
          {hasFilters ? (
            <Button variant="secondary" onClick={clearFilters} icon={<FilterX className="w-4 h-4" />}>
              清除筛选
            </Button>
          ) : (
            <Link to="/projects/new">
              <Button icon={<Plus className="w-4 h-4" />}>创建项目</Button>
            </Link>
          )}
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((project) => (
            <Link
              key={project.id}
              to={`/projects/${project.id}`}
              className="block group"
            >
              <Card className="h-full hover:border-primary-600/50 transition-all duration-200 group-hover:shadow-xl group-hover:shadow-primary-900/10">
                {/* 项目图标 + 状态 */}
                <div className="flex items-start justify-between mb-4">
                  <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-primary-700 rounded-lg flex items-center justify-center">
                    <FlaskConical className="w-5 h-5 text-white" />
                  </div>
                  <StatusBadge status={(project.status as any) || 'draft'} />
                </div>

                {/* 项目名 */}
                <h3 className="font-semibold text-white mb-2 group-hover:text-primary-400 transition-colors">
                  {project.name}
                </h3>

                {/* 描述 */}
                {project.description && (
                  <p className="text-sm text-gray-400 line-clamp-2 mb-3">
                    {project.description}
                  </p>
                )}

                {/* 研究领域标签 */}
                <div className="flex items-center gap-2 mb-3">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] bg-primary-500/10 text-primary-400 border border-primary-500/20">
                    {project.research_field}
                  </span>
                </div>

                {/* 日期 */}
                <div className="flex items-center text-gray-500 text-sm">
                  <Calendar className="w-4 h-4 mr-2" />
                  {formatDate(project.created_at)}
                </div>

                {/* 底部操作 */}
                <div className="mt-4 pt-4 border-t border-dark-700 flex items-center justify-between">
                  <span className="text-sm text-primary-400">查看详情</span>
                  <ArrowRight className="w-4 h-4 text-primary-400 group-hover:translate-x-1 transition-transform" />
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}