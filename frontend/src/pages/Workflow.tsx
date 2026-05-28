import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ChevronDown, Loader2, AlertTriangle, ArrowRight } from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { PageHeader } from '@/components/PageHeader';
import { WorkflowPage } from '@/components/WorkflowPage';
import { projectService } from '@/services/projectService';
import { formatDate } from '@/lib/utils';
import type { ProjectOverview } from '@/types';

export function Workflow() {
  const [projects, setProjects] = useState<ProjectOverview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedProject, setSelectedProject] = useState<ProjectOverview | null>(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadProjects() {
      setLoading(true);
      setError(null);
      try {
        const res = await projectService.getProjects();
        if (cancelled) return;
        if (res.code === 200 && res.data) {
          const list = (res.data as any)?.list ?? res.data;
          setProjects(Array.isArray(list) ? list : []);
        } else {
          setError(res.message || '获取项目列表失败');
        }
      } catch (e: unknown) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : '获取项目列表失败，请检查后端服务是否启动');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadProjects();
    return () => { cancelled = true; };
  }, []);

  const handleSelectProject = (project: ProjectOverview) => {
    setSelectedProject(project);
    setDropdownOpen(false);
  };

  const handleChangeProject = () => {
    setSelectedProject(null);
    setDropdownOpen(false);
  };

  if (!selectedProject) {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <PageHeader
          title="智能体工作流"
          subtitle="选择项目后查看和运行 AI 科研智能体 Pipeline"
        />

        {loading && (
          <Card className="mb-6">
            <div className="flex items-center gap-3 text-gray-400">
              <Loader2 className="w-5 h-5 animate-spin" />
              <span className="text-sm">正在加载项目列表...</span>
            </div>
          </Card>
        )}

        {error && !loading && (
          <Card className="mb-6">
            <div className="flex items-start gap-3 text-red-400">
              <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium">加载失败</p>
                <p className="text-xs text-red-400/70 mt-0.5">{error}</p>
              </div>
            </div>
          </Card>
        )}

        {!loading && !error && (
          <>
            {projects.length === 0 ? (
              <Card className="mb-6">
                <div className="text-center py-6">
                  <p className="text-sm text-gray-400 mb-3">暂无项目，请先创建项目</p>
                  <Link to="/projects/new">
                    <Button icon={<ArrowRight className="w-4 h-4" />}>创建新项目</Button>
                  </Link>
                </div>
              </Card>
            ) : (
              <Card className="mb-6">
                <p className="text-sm text-gray-300 mb-4">请选择一个项目以启动智能体工作流：</p>
                <div className="relative">
                  <button
                    onClick={() => setDropdownOpen(!dropdownOpen)}
                    className="w-full flex items-center justify-between bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-sm text-white hover:border-gray-500 transition-colors"
                  >
                    <span className="text-gray-400">点击选择项目...</span>
                    <ChevronDown className={`w-4 h-4 text-gray-500 transition-transform ${dropdownOpen ? 'rotate-180' : ''}`} />
                  </button>

                  {dropdownOpen && (
                    <div className="absolute z-10 mt-1 w-full bg-gray-800 border border-gray-700 rounded-lg shadow-xl max-h-64 overflow-y-auto">
                      {projects.map((p) => (
                        <button
                          key={p.id}
                          onClick={() => handleSelectProject(p)}
                          className="w-full text-left px-4 py-3 hover:bg-gray-700/50 transition-colors border-b border-gray-700/50 last:border-0"
                        >
                          <div className="text-sm text-white font-medium truncate">{p.name}</div>
                          <div className="text-xs text-gray-500 mt-0.5">
                            {p.research_field} · {formatDate(p.created_at)}
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {dropdownOpen && (
                  <div className="fixed inset-0 z-0" onClick={() => setDropdownOpen(false)} />
                )}
              </Card>
            )}
          </>
        )}
      </div>
    );
  }

  return (
    <div className="px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-white mb-1">智能体工作流</h1>
          <p className="text-sm text-gray-400">
            项目：<span className="text-gray-300">{selectedProject.name}</span>
            {selectedProject.research_question && (
              <span className="ml-3 text-gray-500">
                研究问题：{selectedProject.research_question}
              </span>
            )}
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={handleChangeProject}
        >
          切换项目
        </Button>
      </div>

      <WorkflowPage
        projectId={selectedProject.id}
        researchQuestion={selectedProject.research_question}
      />
    </div>
  );
}