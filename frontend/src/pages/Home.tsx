import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Plus, FlaskConical, Calendar, ArrowRight } from 'lucide-react';
import { projectService } from '@/services';
import { formatDate } from '@/lib/utils';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { StatusBadge } from '@/components/StatusBadge';
import { PageHeader } from '@/components/PageHeader';
import { EmptyState } from '@/components/EmptyState';
import type { Project } from '@/types';

// 后端无数据时的模拟数据
const MOCK_PROJECTS: Project[] = [
  {
    id: '1',
    name: '深度学习优化研究',
    description: '研究如何优化深度学习模型的训练效率',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    status: 'completed',
  },
  {
    id: '2',
    name: '自然语言处理应用',
    description: '探索 NLP 在实际问题中的应用',
    created_at: new Date(Date.now() - 86400000).toISOString(),
    updated_at: new Date().toISOString(),
    status: 'running',
  },
  {
    id: '3',
    name: '计算机视觉研究',
    description: '研究 CV 领域的新算法和应用',
    created_at: new Date(Date.now() - 172800000).toISOString(),
    updated_at: new Date().toISOString(),
    status: 'draft',
  },
];

export function Home() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async () => {
    try {
      const response = await projectService.getProjects();
      if (response.code === 200) {
        const data = response.data || [];
        // 后端无数据时显示模拟数据
        setProjects(data.length > 0 ? data : MOCK_PROJECTS);
      }
    } catch (error) {
      console.error('加载项目失败:', error);
      setProjects(MOCK_PROJECTS);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <PageHeader
        title="项目工作台"
        subtitle="管理您的 AI 科研项目"
        actions={
          <Link to="/projects/new">
            <Button icon={<Plus className="w-4 h-4" />}>创建新项目</Button>
          </Link>
        }
      />

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <Card className="text-center">
          <div className="text-3xl font-bold text-primary-400 mb-2">
            {projects.length}
          </div>
          <div className="text-gray-400">总项目数</div>
        </Card>
        <Card className="text-center">
          <div className="text-3xl font-bold text-green-400 mb-2">
            {projects.filter(p => p.status === 'completed').length}
          </div>
          <div className="text-gray-400">已完成</div>
        </Card>
        <Card className="text-center">
          <div className="text-3xl font-bold text-yellow-400 mb-2">
            {projects.filter(p => p.status === 'running').length}
          </div>
          <div className="text-gray-400">运行中</div>
        </Card>
      </div>

      {/* Project List */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-white">我的项目</h2>
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
        ) : projects.length === 0 ? (
          <EmptyState
            icon={<FlaskConical className="w-8 h-8" />}
            title="还没有项目"
            description="创建您的第一个 AI 科研项目"
            action={{
              label: '创建项目',
              onClick: () => navigate('/projects/new'),
            }}
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((project) => (
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
                      status={(project.status as any) || 'draft'}
                    />
                  </div>
                  <h3 className="font-semibold text-white mb-2 group-hover:text-primary-400 transition-colors">
                    {project.name}
                  </h3>
                  {project.description && (
                    <p className="text-sm text-gray-400 line-clamp-2 mb-4">
                      {project.description}
                    </p>
                  )}
                  <div className="flex items-center text-gray-500 text-sm">
                    <Calendar className="w-4 h-4 mr-2" />
                    {formatDate(project.created_at)}
                  </div>
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
    </div>
  );
}
