import { useState, useMemo, useEffect, useCallback } from 'react';
import { useParams, Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  HelpCircle,
  BookOpen, Lightbulb, FlaskConical,
  FileText, TrendingUp, Play,
  Loader2, AlertTriangle, CheckCircle2,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { PipelineProgress } from '@/components/PipelineProgress';
import { ResearchQuestionPage } from '@/components/ResearchQuestionPage';
import { LiteratureLibrary } from '@/components/LiteratureLibrary';
import { WorkflowPage } from '@/components/WorkflowPage';
import { HypothesesPage } from '@/components/HypothesesPage';
import { ExperimentDesignPage } from '@/components/ExperimentDesignPage';
import { ReportPage } from '@/components/ReportPage';
import { RunLogsPage } from '@/components/RunLogsPage';
import { DatasetPage } from '@/components/DatasetPage';
import { KnowledgeGraphPage } from '@/components/KnowledgeGraphPage';
import { ResearchClosedLoopOverview } from '@/components/ResearchClosedLoopOverview';
import { PromptManagementPage } from '@/components/PromptManagementPage';
import { projectService } from '@/services/projectService';
import { pipelineService } from '@/services/pipelineService';
import type { ProjectOverview, PipelineRunResult, PipelineRunSummary } from '@/types';
import { VALID_PROJECT_TAB_IDS } from '@/config/projectTabs';
import { researchQuestionKey } from '@/lib/storageKeys';
import { BackToProjectsLink } from '@/components/workspace/BackToProjectsLink';
import { ProjectWorkspaceHeader } from '@/components/workspace/ProjectWorkspaceHeader';
import { ProjectTabNav } from '@/components/workspace/ProjectTabNav';

// ============ localStorage 研究问题读取 ============
/**
 * 从 localStorage 中读取按 projectId 隔离的研究问题草稿。
 * 作为后端 research_question 字段的 fallback。
 */
function getStoredResearchQuestion(projectId: string): string {
  try {
    const raw = localStorage.getItem(researchQuestionKey(projectId));
    if (!raw) return '';
    const parsed = JSON.parse(raw);
    return parsed.researchQuestion || parsed.research_question || '';
  } catch {
    return '';
  }
}

function getStoredResearchDomain(projectId: string): string {
  try {
    const raw = localStorage.getItem(researchQuestionKey(projectId));
    if (!raw) return '';
    const parsed = JSON.parse(raw);
    return parsed.researchDomain || parsed.research_domain || '';
  } catch {
    return '';
  }
}

// ============ Pipeline 阶段中英文映射表 ============
const STAGE_CN_MAP: Record<string, string> = {
  problem_understanding: '问题理解',
  literature_mining: '文献挖掘',
  knowledge_graph: '知识图谱',
  knowledge_gap: '知识缺口',
  hypothesis_generation: '假设生成',
  hypothesis_review: '假设评估',
  experiment_design: '实验设计',
  small_validation: '小样验证',
  report_generation: '报告生成',
};

// ============ 项目概览 ============
function ProjectOverview({ project, stats, pipelineNodes }: {
  project: ProjectOverview;
  stats: { label: string; value: string }[];
  pipelineNodes: { id: string; label: string; status: string }[];
}) {
  const navigate = useNavigate();

  return (
    <div className="space-y-6">
      <Card title="研究数据概览" subtitle="当前项目的关键指标">
        {stats.length === 0 ? (
          <div className="text-center py-8 text-bp-muted">
            <TrendingUp className="w-8 h-8 mx-auto mb-3 opacity-50" />
            <p>暂无统计数据</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {stats.map((stat, idx) => (
              <div key={idx} className="bp-metric-box text-center">
                <div className="max-w-full truncate text-2xl font-bold text-bp-cyan" title={stat.value}>{stat.value}</div>
                <div className="text-sm text-bp-muted mt-1">{stat.label}</div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card title="研究 Pipeline" subtitle="各阶段执行状态">
        <PipelineProgress nodes={pipelineNodes as any} />
        <div className="mt-6 flex justify-end">
          <Button
            icon={<Play className="w-4 h-4" />}
            onClick={() => navigate(`/projects/${project.id}?tab=closed_loop`)}
          >
            查看闭环
          </Button>
        </div>
      </Card>

      </div>
  );
}

// ============ 各 Tab 子组件包装 ============
function QuestionsTab({
  projectId,
  projectMode,
  onSaved,
}: {
  projectId: string;
  projectMode?: string;
  onSaved?: () => void;
}) {
  return <ResearchQuestionPage projectId={projectId} projectMode={projectMode} onSaved={onSaved} />;
}

function LiteratureTab({ projectId }: { projectId: string }) {
  return <LiteratureLibrary projectId={projectId} compact />;
}

function KnowledgeGraphTab({
  projectId,
  projectMode,
  researchQuestion,
  focusNodeId,
}: {
  projectId: string;
  projectMode?: string;
  researchQuestion?: string;
  focusNodeId?: string | null;
}) {
  return (
    <KnowledgeGraphPage
      projectId={projectId}
      projectMode={projectMode}
      researchQuestion={researchQuestion}
      focusNodeId={focusNodeId}
    />
  );
}

function WorkflowTab({ projectId, researchQuestion, questionSource, onPipelineCompleted }: {
  projectId: string;
  researchQuestion: string;
  questionSource?: 'backend' | 'localStorage' | 'none';
  onPipelineCompleted?: (result: PipelineRunResult) => void;
}) {
  return (
    <div className="space-y-4">
      {researchQuestion && questionSource === 'localStorage' && (
        <div className="px-4 py-2 rounded-lg bg-yellow-500/10 border border-yellow-500/20 text-sm text-yellow-300 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          研究问题来自本地草稿，建议保存到后端
        </div>
      )}
      {researchQuestion && questionSource === 'backend' && (
        <div className="px-4 py-2 rounded-lg bg-green-500/10 border border-green-500/20 text-sm text-green-300 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          研究问题已从项目配置读取
        </div>
      )}
      <WorkflowPage projectId={projectId} researchQuestion={researchQuestion} compact onPipelineCompleted={onPipelineCompleted} />
    </div>
  );
}

function HypothesesTab({ projectId, revalidateKey, latestRunId }: {
  projectId: string;
  revalidateKey: number;
  latestRunId: string | null;
}) {
  return <HypothesesPage projectId={projectId} compact revalidateKey={revalidateKey} latestRunId={latestRunId} />;
}

function ExperimentsTab({ projectId, projectMode, revalidateKey, latestRunId, hypothesisId }: {
  projectId: string;
  projectMode?: string;
  revalidateKey: number;
  latestRunId: string | null;
  hypothesisId: string | null;
}) {
  return (
    <ExperimentDesignPage
      projectId={projectId}
      projectMode={projectMode}
      compact
      revalidateKey={revalidateKey}
      latestRunId={latestRunId}
      selectedHypothesisId={hypothesisId}
    />
  );
}

function ReportsTab({ projectId, projectMode, revalidateKey, latestRunId }: {
  projectId: string;
  projectMode?: string;
  revalidateKey: number;
  latestRunId: string | null;
}) {
  return (
    <ReportPage
      projectId={projectId}
      projectMode={projectMode}
      compact
      revalidateKey={revalidateKey}
      latestRunId={latestRunId}
    />
  );
}

function LogsTab({ projectId, revalidateKey, latestRunId }: {
  projectId: string;
  revalidateKey: number;
  latestRunId: string | null;
}) {
  return <RunLogsPage projectId={projectId} compact revalidateKey={revalidateKey} latestRunId={latestRunId} />;
}

// ============ 主组件 ============
export function ProjectWorkspace() {
  const { projectId } = useParams<{ projectId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const id = projectId ?? '1';

  // 从 URL 读取 tab，非法值回退 overview
  const activeTab = useMemo(() => {
    const tabFromUrl = searchParams.get('tab');
    return tabFromUrl && VALID_PROJECT_TAB_IDS.has(tabFromUrl) ? tabFromUrl : 'overview';
  }, [searchParams]);

  // 切换 tab → 更新 URL searchParams
  const handleTabChange = (tabId: string) => {
    setSearchParams({ tab: tabId });
  };

  // --- Pipeline 运行状态 ---
  const [latestRunId, setLatestRunId] = useState<string | null>(null);
  const [revalidateKey, setRevalidateKey] = useState(0);
  const [isPipelineRunning, setIsPipelineRunning] = useState(false);
  const [pipelineRuns, setPipelineRuns] = useState<PipelineRunSummary[]>([]);

  const handlePipelineCompleted = useCallback((_result: PipelineRunResult) => {
    setLatestRunId(_result.run_id);
    setIsPipelineRunning(false);
    setRevalidateKey((k) => k + 1);
  }, []);

  // --- 加载 Pipeline 运行记录 ---
  useEffect(() => {
    if (!id) {
      setPipelineRuns([]);
      return;
    }

    let cancelled = false;

    pipelineService.getRuns(id).then((res) => {
      if (cancelled) return;
      if (res.code === 200 && Array.isArray(res.data)) {
        setPipelineRuns(
          [...res.data].sort(
            (a, b) =>
              new Date(b.created_at || '').getTime() -
              new Date(a.created_at || '').getTime(),
          ),
        );
      }
    }).catch(() => {
      if (!cancelled) setPipelineRuns([]);
    });

    return () => { cancelled = true; };
  }, [id, revalidateKey]);

  // --- 项目数据加载 ---
  const [project, setProject] = useState<ProjectOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadProject() {
      setLoading(true);
      setError(null);

      try {
        const res = await projectService.getProject(id);
        if (cancelled) return;
        if (res.code === 200 && res.data) {
          setProject(res.data);
        } else {
          setError(res.message || '获取项目详情失败');
        }
      } catch (e: unknown) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : '获取项目详情失败，请检查后端服务是否启动');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadProject();
    return () => { cancelled = true; };
  }, [id]);

  // --- 研究领域 ---
  const resolvedProjectMode = project?.project_mode || 'general';
  const projectModeLabel =
    resolvedProjectMode === 'federated_learning'
      ? 'Federated Learning Scientist'
      : 'General AI Scientist';

  const resolvedResearchField = useMemo(() => {
    if (project?.research_field) return project.research_field;
    return getStoredResearchDomain(id || '') || '未知领域';
  }, [project?.research_field, id]);

  // --- 当前阶段 ---
  const resolvedCurrentStage = useMemo(() => {
    if (isPipelineRunning) return '运行中';
    const latestRun = pipelineRuns[0];
    if (!latestRun) return '未开始';
    if (latestRun.status === 'completed') return '已完成';
    if (latestRun.status === 'running') return '运行中';
    if (latestRun.status === 'failed') {
      const failedCn = latestRun.failed_stage
        ? STAGE_CN_MAP[latestRun.failed_stage] || latestRun.failed_stage
        : '';
      return failedCn ? `失败于 ${failedCn}` : '失败';
    }
    return '未开始';
  }, [isPipelineRunning, pipelineRuns]);

  // --- 研究问题汇总（后端优先 → localStorage fallback） ---
  const resolvedResearchQuestion = useMemo(() => {
    if (project?.research_question) return project.research_question;
    return getStoredResearchQuestion(id || '');
  }, [project?.research_question, id]);

  const questionSource = useMemo<'backend' | 'localStorage' | 'none'>(() => {
    if (!resolvedResearchQuestion) return 'none';
    if (project?.research_question) return 'backend';
    return 'localStorage';
  }, [resolvedResearchQuestion, project?.research_question]);

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  // --- 概览统计 ---
  const overviewStats = useMemo(() => {
    const latestRun = pipelineRuns[0];
    return [
      { label: 'Pipeline 运行次数', value: String(pipelineRuns.length) },
      {
        label: '最新运行状态',
        value: latestRun
          ? latestRun.status === 'completed' ? '已完成'
          : latestRun.status === 'failed' ? '失败'
          : latestRun.status === 'running' ? '运行中'
          : latestRun.status
          : '无记录',
      },
      { label: '研究领域', value: resolvedResearchField },
      { label: '当前阶段', value: resolvedCurrentStage },
      {
        label: '项目状态',
        value: project?.status === 'completed' ? '已完成'
          : project?.status === 'running' || project?.status === 'in_progress' ? '运行中'
          : '草稿',
      },
      { label: '创建日期', value: formatDate(project?.created_at) },
    ];
  }, [pipelineRuns, resolvedResearchField, resolvedCurrentStage, project?.status, project?.created_at]);

  // --- Pipeline 节点 ---
  const overviewPipelineNodes = useMemo(() => {
    const latestRun = pipelineRuns[0];
    const stages = [
      { id: 'problem_understanding', label: '问题理解', icon: HelpCircle },
      { id: 'literature_mining', label: '文献挖掘', icon: BookOpen },
      { id: 'knowledge_gap', label: '知识缺口', icon: AlertTriangle },
      { id: 'hypothesis_generation', label: '假设生成', icon: Lightbulb },
      { id: 'hypothesis_review', label: '假设评估', icon: CheckCircle2 },
      { id: 'experiment_design', label: '实验设计', icon: FlaskConical },
      { id: 'small_validation', label: '小样验证', icon: TrendingUp },
      { id: 'report_generation', label: '报告生成', icon: FileText },
    ];

    const runStatus = latestRun?.status;
    const failedStageId = latestRun?.failed_stage;

    return stages.map((stage, idx) => {
      let status: 'pending' | 'running' | 'completed' | 'error';
      if (!runStatus || runStatus === 'pending') {
        status = 'pending';
      } else if (runStatus === 'completed') {
        status = 'completed';
      } else if (runStatus === 'failed') {
        if (failedStageId && stage.id === failedStageId) {
          status = 'error';
        } else if (failedStageId) {
          const failedIdx = stages.findIndex(s => s.id === failedStageId);
          status = failedIdx >= 0 && idx < failedIdx ? 'completed' : 'pending';
        } else {
          status = 'pending';
        }
      } else if (runStatus === 'running') {
        status = 'pending';
      } else {
        status = 'pending';
      }
      return { ...stage, status };
    });
  }, [pipelineRuns]);

  // --- 保存研究问题后刷新项目数据 ---
  const handleResearchSaved = () => {
    if (!id) return;
    projectService.getProject(id).then((res) => {
      if (res.code === 200 && res.data) {
        setProject(res.data);
      }
    });
  };

  // --- 渲染 ---
  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <BackToProjectsLink />
        <div className="flex flex-col items-center justify-center py-20 text-bp-muted">
          <Loader2 className="w-8 h-8 animate-spin mb-3" />
          <span>正在加载项目信息...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <BackToProjectsLink />
        <Card className="border-danger-500/30 bg-danger-500/5">
          <div className="flex flex-col items-center py-8 text-center">
            <AlertTriangle className="w-10 h-10 text-danger-400 mb-3" />
            <h3 className="text-lg font-semibold text-danger-300 mb-2">加载失败</h3>
            <p className="text-bp-muted mb-4 max-w-md">{error}</p>
            <Button onClick={() => window.location.reload()} variant="secondary">
              重新加载
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <BackToProjectsLink />
        <Card>
          <div className="flex flex-col items-center py-8 text-center">
            <h3 className="text-lg font-semibold text-bp-text mb-2">项目不存在</h3>
            <p className="text-bp-muted mb-4">
              未找到项目 {id}，请检查项目 ID 是否正确
            </p>
            <Link to="/">
              <Button variant="primary">返回项目列表</Button>
            </Link>
          </div>
        </Card>
      </div>
    );
  }

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        return <ProjectOverview project={project} stats={overviewStats} pipelineNodes={overviewPipelineNodes} />;
      case 'closed_loop':
        return (
          <ResearchClosedLoopOverview
            projectId={id}
            latestRunId={latestRunId}
            revalidateKey={revalidateKey}
          />
        );
      case 'questions':
        return <QuestionsTab projectId={id} projectMode={resolvedProjectMode} onSaved={handleResearchSaved} />;
      case 'literature':
        return <LiteratureTab projectId={id} />;
      case 'knowledge_graph':
        return (
          <KnowledgeGraphTab
            projectId={id}
            projectMode={resolvedProjectMode}
            researchQuestion={resolvedResearchQuestion}
            focusNodeId={searchParams.get('node_id')}
          />
        );
      case 'datasets':
        return <DatasetPage projectId={id} projectMode={resolvedProjectMode} researchQuestion={resolvedResearchQuestion} />;
      case 'workflow':
        return (
          <WorkflowTab
            projectId={id}
            researchQuestion={resolvedResearchQuestion}
            questionSource={questionSource}
            onPipelineCompleted={handlePipelineCompleted}
          />
        );
      case 'prompts':
        return <PromptManagementPage projectId={id} projectMode={resolvedProjectMode} />;
      case 'hypotheses':
        return <HypothesesTab projectId={id} revalidateKey={revalidateKey} latestRunId={latestRunId} />;
      case 'experiments':
        return (
          <ExperimentsTab
            projectId={id}
            projectMode={resolvedProjectMode}
            revalidateKey={revalidateKey}
            latestRunId={latestRunId}
            hypothesisId={searchParams.get('hypothesis_id')}
          />
        );
      case 'reports':
        return (
          <ReportsTab
            projectId={id}
            projectMode={resolvedProjectMode}
            revalidateKey={revalidateKey}
            latestRunId={latestRunId}
          />
        );
      case 'logs':
        return <LogsTab projectId={id} revalidateKey={revalidateKey} latestRunId={latestRunId} />;
      default:
        return <ProjectOverview project={project} stats={overviewStats} pipelineNodes={overviewPipelineNodes} />;
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <BackToProjectsLink />

      <ProjectWorkspaceHeader
        projectName={project.name}
        status={(project.status as any) || 'draft'}
        researchField={resolvedResearchField}
        projectModeLabel={projectModeLabel}
        currentStage={resolvedCurrentStage}
        description={project.description}
        createdAtLabel={formatDate(project.created_at)}
        onUploadLiterature={() => navigate(`/projects/${project.id}?tab=literature`)}
        onRunPipeline={() => navigate(`/projects/${project.id}?tab=workflow`)}
      />

      <ProjectTabNav activeTab={activeTab} onTabChange={handleTabChange} />

      <div className="animate-fade-in">
        {renderTabContent()}
      </div>
    </div>
  );
}