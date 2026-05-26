import { useState, useMemo } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Calendar, LayoutDashboard, HelpCircle,
  BookOpen, GitBranch, Lightbulb, FlaskConical,
  FileText, ScrollText, Tag, TrendingUp, Play,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { StatusBadge } from '@/components/StatusBadge';
import { StatCard } from '@/components/StatCard';
import { PipelineProgress } from '@/components/PipelineProgress';
import { ResearchQuestionPage } from '@/components/ResearchQuestionPage';
import { LiteratureLibrary } from '@/components/LiteratureLibrary';
import { WorkflowPage } from '@/components/WorkflowPage';
import { HypothesesPage } from '@/components/HypothesesPage';
import { ExperimentDesignPage } from '@/components/ExperimentDesignPage';
import { ReportPage } from '@/components/ReportPage';
import { RunLogsPage } from '@/components/RunLogsPage';
import {
  MOCK_PROJECT_OVERVIEW, MOCK_STATS, DEFAULT_STATS,
  MOCK_PIPELINE_NODES, DEFAULT_PIPELINE_NODES,
} from '@/data/mockData';
import type { ProjectOverview, StatItem, PipelineNodeData } from '@/types';
import { cn } from '@/lib/utils';

// ============ 标签页定义 ============
interface TabItem {
  id: string;
  label: string;
  icon: React.FC<{ className?: string }>;
}

const TABS: TabItem[] = [
  { id: 'overview', label: '项目概览', icon: LayoutDashboard },
  { id: 'questions', label: '研究问题', icon: HelpCircle },
  { id: 'literature', label: '文献库', icon: BookOpen },
  { id: 'workflow', label: '智能体工作流', icon: GitBranch },
  { id: 'hypotheses', label: '候选假设', icon: Lightbulb },
  { id: 'experiments', label: '实验设计', icon: FlaskConical },
  { id: 'reports', label: '研究报告', icon: FileText },
  { id: 'logs', label: '运行日志', icon: ScrollText },
];

// ============ 项目概览 ============
function ProjectOverview({ project, stats, pipelineNodes }: {
  project: ProjectOverview;
  stats: StatItem[];
  pipelineNodes: PipelineNodeData[];
}) {
  const navigate = useNavigate();

  return (
    <div className="space-y-6">
      {/* 统计卡片 */}
      <Card title="研究数据概览" subtitle="当前项目的关键指标">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {stats.map((stat) => (
            <StatCard
              key={stat.id}
              label={stat.label}
              value={stat.value}
              icon={<stat.icon className="w-5 h-5" />}
              colorClass={stat.color}
            />
          ))}
        </div>
      </Card>

      {/* Pipeline 进度 */}
      <Card title="研究 Pipeline" subtitle="各阶段执行状态">
        <PipelineProgress nodes={pipelineNodes} />
        <div className="mt-6 flex justify-end">
          <Button
            icon={<Play className="w-4 h-4" />}
            onClick={() => navigate(`/projects/${project.id}?tab=workflow`)}
          >
            继续工作
          </Button>
        </div>
      </Card>

      {/* 快捷操作 */}
      <Card title="快捷操作">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: '上传文献', icon: BookOpen },
            { label: '添加问题', icon: HelpCircle },
            { label: '生成假设', icon: Lightbulb },
            { label: '查看报告', icon: FileText },
          ].map((action) => {
            const Icon = action.icon;
            return (
              <button
                key={action.label}
                className="flex flex-col items-center gap-2 p-4 rounded-lg border border-dark-700 bg-dark-800/50 hover:border-primary-500/50 hover:bg-dark-800 transition-all"
              >
                <Icon className="w-6 h-6 text-primary-400" />
                <span className="text-sm text-[#F8FAFC]">{action.label}</span>
              </button>
            );
          })}
        </div>
      </Card>
    </div>
  );
}

// ============ 研究问题 ============
function QuestionsTab({ projectId }: { projectId: string }) {
  return <ResearchQuestionPage projectId={projectId} />;
}

// ============ 文献库 ============
function LiteratureTab({ projectId }: { projectId: string }) {
  return <LiteratureLibrary projectId={projectId} compact />;
}

// ============ 智能体工作流 ============
function WorkflowTab({ projectId, researchQuestion }: { projectId: string; researchQuestion: string }) {
  return <WorkflowPage projectId={projectId} researchQuestion={researchQuestion} compact />;
}

// ============ 候选假设 ============
function HypothesesTab({ projectId }: { projectId: string }) {
  return <HypothesesPage projectId={projectId} compact />;
}

// ============ 实验设计 ============
function ExperimentsTab({ projectId }: { projectId: string }) {
  return <ExperimentDesignPage projectId={projectId} compact />;
}

// ============ 研究报告 ============
function ReportsTab({ projectId }: { projectId: string }) {
  return <ReportPage projectId={projectId} compact />;
}

// ============ 运行日志 ============
function LogsTab({ projectId }: { projectId: string }) {
  return <RunLogsPage projectId={projectId} compact />;
}

// ============ 主组件 ============
export function ProjectWorkspace() {
  const { projectId } = useParams<{ projectId: string }>();
  const [activeTab, setActiveTab] = useState<string>('overview');

  // 项目信息
  const project: ProjectOverview = useMemo(() => {
    const id = projectId ?? '1';
    return MOCK_PROJECT_OVERVIEW[id] ?? {
      id,
      name: id === '1' ? '深度学习优化研究' : `项目 #${id}`,
      research_field: '人工智能',
      description: '这是一个 AI 科研项目。',
      current_stage: '未开始',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      status: 'draft',
    };
  }, [projectId]);

  // 统计数据
  const stats = useMemo(() => {
    const id = projectId ?? '1';
    return MOCK_STATS[id] ?? DEFAULT_STATS;
  }, [projectId]);

  // Pipeline 节点
  const pipelineNodes = useMemo(() => {
    const id = projectId ?? '1';
    return MOCK_PIPELINE_NODES[id] ?? DEFAULT_PIPELINE_NODES;
  }, [projectId]);

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        return <ProjectOverview project={project} stats={stats} pipelineNodes={pipelineNodes} />;
      case 'questions':
        return <QuestionsTab projectId={projectId ?? '1'} />;
      case 'literature':
        return <LiteratureTab projectId={projectId ?? '1'} />;
      case 'workflow':
        return <WorkflowTab projectId={projectId ?? '1'} researchQuestion={project.research_question ?? ''} />;
      case 'hypotheses':
        return <HypothesesTab projectId={projectId ?? '1'} />;
      case 'experiments':
        return <ExperimentsTab projectId={projectId ?? '1'} />;
      case 'reports':
        return <ReportsTab projectId={projectId ?? '1'} />;
      case 'logs':
        return <LogsTab projectId={projectId ?? '1'} />;
      default:
        return <ProjectOverview project={project} stats={stats} pipelineNodes={pipelineNodes} />;
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* ========== 项目头部 ========== */}
      <div className="mb-8">
        <Link to="/" className="inline-flex items-center text-[#94A3B8] hover:text-[#F8FAFC] mb-4 transition-colors">
          <ArrowLeft className="w-4 h-4 mr-2" />
          <span className="text-sm">返回项目列表</span>
        </Link>

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-3xl font-bold text-white truncate">
                {project.name}
              </h1>
              <StatusBadge status={(project.status as any) || 'draft'} />
            </div>

            {/* 研究领域 + 当前阶段 */}
            <div className="flex flex-wrap items-center gap-3 mb-2 text-sm">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-primary-500/10 border border-primary-500/20 text-primary-400">
                <Tag className="w-3.5 h-3.5" />
                {project.research_field}
              </span>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
                <TrendingUp className="w-3.5 h-3.5" />
                当前阶段：{project.current_stage}
              </span>
            </div>

            {project.description && (
              <p className="text-[#94A3B8] max-w-2xl">{project.description}</p>
            )}
            <div className="flex items-center gap-2 mt-3 text-sm text-[#94A3B8]">
              <Calendar className="w-4 h-4" />
              <span>创建于 {formatDate(project.created_at)}</span>
            </div>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <Button variant="secondary" icon={<BookOpen className="w-4 h-4" />}>
              上传文献
            </Button>
            <Button variant="primary" icon={<Play className="w-4 h-4" />}>
              运行 Pipeline
            </Button>
          </div>
        </div>
      </div>

      {/* ========== 二级 Tab 导航 ========== */}
      <div className="border-b border-dark-700 mb-6">
        <nav className="flex gap-1 overflow-x-auto -mb-px">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'flex items-center gap-2 px-4 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition-all duration-200',
                  isActive
                    ? 'border-primary-500 text-primary-400'
                    : 'border-transparent text-[#94A3B8] hover:text-[#F8FAFC] hover:border-dark-700',
                )}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* ========== Tab 内容区 ========== */}
      <div className="animate-fade-in">
        {renderTabContent()}
      </div>
    </div>
  );
}