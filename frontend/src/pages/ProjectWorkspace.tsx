import { useState, useMemo, useEffect, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import {
  HelpCircle,
  BookOpen, Lightbulb, FlaskConical,
  FileText, TrendingUp, Play,
  AlertTriangle, CheckCircle2, Database,
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
import { DataUploadGateFloating } from '@/components/DataUploadGateFloating';
import { useDataUploadGate } from '@/hooks/useDataUploadGate';
import { buildProjectTabUrl } from '@/lib/projectNavigation';
import { getPipelineStageTab } from '@/config/pipelineStageNavigation';
import { PromptManagementPage } from '@/components/PromptManagementPage';
import { projectService } from '@/services/projectService';
import { pipelineService } from '@/services/pipelineService';
import { buildPipelineProgressNodes, resolveCurrentPipelineStageLabel } from '@/lib/pipelineProgressNodes';
import {
  resolveProjectDisplayStatus,
} from '@/lib/projectStatus';
import type { ProjectOverview, PipelineRunResult, PipelineRunSummary } from '@/types';
import { VALID_PROJECT_TAB_IDS } from '@/config/projectTabs';
import { researchQuestionKey } from '@/lib/storageKeys';
import { resolveResearchField } from '@/lib/researchField';
import { BackToProjectsLink } from '@/components/workspace/BackToProjectsLink';
import { ProjectWorkspaceHeader } from '@/components/workspace/ProjectWorkspaceHeader';
import { ProjectTabNav } from '@/components/workspace/ProjectTabNav';
import { LoadingState } from '@/components/workspace/LoadingState';
import { ErrorState } from '@/components/workspace/ErrorState';
import { EmptyState } from '@/components/EmptyState';

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

// ============ Pipeline 阶段中英文映射表 ============
const STAGE_CN_MAP: Record<string, string> = {
  problem_understanding: '问题理解',
  literature_mining: '文献挖掘',
  data_acquisition: '数据采集',
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
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {stats.map((stat, idx) => (
              <div key={idx} className="bp-metric-box text-center">
                <div className="max-w-full truncate text-2xl font-bold text-bp-cyan" title={stat.value}>{stat.value}</div>
                <div className="text-sm text-bp-muted mt-1">{stat.label}</div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card title="研究 Pipeline" subtitle="各阶段执行状态 · 点击阶段可跳转">
        <PipelineProgress
          nodes={pipelineNodes as any}
          onNodeClick={(node) => {
            const tab = getPipelineStageTab(node.id);
            if (tab) {
              navigate(buildProjectTabUrl(project.id, tab));
            } else {
              navigate(buildProjectTabUrl(project.id, 'workflow'));
            }
          }}
        />
        <div className="mt-6 flex justify-end">
          <Button
            icon={<Play className="w-4 h-4" />}
            onClick={() => navigate(`/projects/${project.id}?tab=workflow`)}
          >
            进入智能体工作流 →
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
  pollWhileRunning,
  revalidateKey,
}: {
  projectId: string;
  projectMode?: string;
  onSaved?: () => void;
  pollWhileRunning?: boolean;
  revalidateKey?: number;
}) {
  return (
    <ResearchQuestionPage
      projectId={projectId}
      projectMode={projectMode}
      onSaved={onSaved}
      pollWhileRunning={pollWhileRunning}
      revalidateKey={revalidateKey}
    />
  );
}

function LiteratureTab({ projectId }: { projectId: string }) {
  return <LiteratureLibrary projectId={projectId} compact />;
}

function WorkflowTab({ projectId, researchQuestion, questionSource, onPipelineCompleted, onPipelineStarted }: {
  projectId: string;
  researchQuestion: string;
  questionSource?: 'backend' | 'localStorage' | 'none';
  onPipelineCompleted?: (result: PipelineRunResult) => void;
  onPipelineStarted?: (runId: string) => void;
}) {
  return (
    <div className="space-y-4">
      {researchQuestion && questionSource === 'localStorage' && (
        <div className="px-4 py-2 rounded-bp bg-bp-yellow/10 border border-bp-yellow/20 text-sm text-bp-yellow flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          研究问题来自本地草稿，建议保存到后端
        </div>
      )}
      {researchQuestion && questionSource === 'backend' && (
        <div className="px-4 py-2 rounded-bp bg-bp-green/10 border border-bp-green/20 text-sm text-bp-green flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          研究问题已从项目配置读取
        </div>
      )}
      <WorkflowPage
        projectId={projectId}
        researchQuestion={researchQuestion}
        compact
        onPipelineCompleted={onPipelineCompleted}
        onPipelineStarted={onPipelineStarted}
      />
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
  const [latestRunStages, setLatestRunStages] = useState<
    Array<{ stage?: string; status?: string; output_data?: unknown }>
  >([]);
  const [project, setProject] = useState<ProjectOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadTick, setReloadTick] = useState(0);

  const handlePipelineCompleted = useCallback((_result: PipelineRunResult) => {
    setLatestRunId(_result.run_id);
    setIsPipelineRunning(false);
    setRevalidateKey((k) => k + 1);
  }, []);

  const handlePipelineStarted = useCallback((runId: string) => {
    setLatestRunId(runId);
    setIsPipelineRunning(true);
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

  const latestRun = pipelineRuns[0];

  useEffect(() => {
    if (latestRun?.run_id) {
      setLatestRunId(latestRun.run_id);
    }
  }, [latestRun?.run_id]);

  useEffect(() => {
    const terminal = latestRun?.status === 'failed' || latestRun?.status === 'completed';
    if (terminal) {
      setIsPipelineRunning(false);
    }
  }, [latestRun?.status]);

  const isRunActive = isPipelineRunning || latestRun?.status === 'running';

  // 拉取 / 轮询最新运行的阶段状态（与顶部「运行中」徽章同步）
  useEffect(() => {
    const runId = latestRun?.run_id;
    if (!runId) {
      setLatestRunStages([]);
      return undefined;
    }

    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;

    const sortRuns = (runs: PipelineRunSummary[]) =>
      [...runs].sort(
        (a, b) =>
          new Date(b.created_at || '').getTime() - new Date(a.created_at || '').getTime(),
      );

    async function refreshRunDetail() {
      try {
        const detailRes = await pipelineService.getRunDetail(runId!);
        if (cancelled) return;
        if (detailRes.code === 200 && Array.isArray(detailRes.data?.stages)) {
          setLatestRunStages(detailRes.data.stages);
        }

        const [runsRes, projRes] = await Promise.all([
          pipelineService.getRuns(id),
          projectService.getProject(id),
        ]);
        if (cancelled) return;
        if (runsRes.code === 200 && Array.isArray(runsRes.data)) {
          setPipelineRuns(sortRuns(runsRes.data));
        }
        if (projRes.code === 200 && projRes.data) {
          setProject(projRes.data);
        }
      } catch {
        /* 轮询失败时保留上次阶段快照 */
      }
    }

    refreshRunDetail();
    if (isRunActive) {
      timer = setInterval(refreshRunDetail, 2000);
    }

    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, [id, latestRun?.run_id, isRunActive, revalidateKey]);

  const dataUploadGate = useDataUploadGate(id, latestRunId ?? pipelineRuns[0]?.run_id ?? null);
  const [dataGateDismissed, setDataGateDismissed] = useState(false);

  const onRequiredDatasetsTab =
    activeTab === 'datasets' && searchParams.get('subtab') === 'required-datasets';

  // --- 项目数据加载 ---
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
  }, [id, reloadTick]);

  // --- 研究领域 ---
  const resolvedProjectMode = project?.project_mode || 'general';
  const projectModeLabel =
    resolvedProjectMode === 'federated_learning'
      ? 'Federated Learning Scientist'
      : 'General AISci';

  const resolvedResearchField = useMemo(
    () => resolveResearchField(project, id, latestRunStages),
    [project, id, latestRunStages],
  );

  const resolvedCurrentStage = useMemo(
    () => resolveCurrentPipelineStageLabel(
      latestRun,
      latestRunStages,
      STAGE_CN_MAP,
      { isPipelineStarting: isPipelineRunning && !latestRun },
    ),
    [latestRun, latestRunStages, isPipelineRunning],
  );

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
    return [
      { label: 'Pipeline 运行次数', value: String(pipelineRuns.length) },
      { label: '研究领域', value: resolvedResearchField },
      { label: '当前阶段', value: resolvedCurrentStage },
    ];
  }, [pipelineRuns.length, resolvedResearchField, resolvedCurrentStage]);

  // --- Pipeline 节点（与阶段执行记录对齐） ---
  const pipelineStageDefs = useMemo(
    () => [
      { id: 'problem_understanding', label: '问题理解', icon: HelpCircle },
      { id: 'literature_mining', label: '文献挖掘', icon: BookOpen },
      { id: 'data_acquisition', label: '数据采集', icon: Database },
      { id: 'knowledge_gap', label: '知识缺口', icon: AlertTriangle },
      { id: 'hypothesis_generation', label: '假设生成', icon: Lightbulb },
      { id: 'hypothesis_review', label: '假设评估', icon: CheckCircle2 },
      { id: 'experiment_design', label: '实验设计', icon: FlaskConical },
      { id: 'small_validation', label: '小样验证', icon: TrendingUp },
      { id: 'report_generation', label: '报告生成', icon: FileText },
    ],
    [],
  );

  const overviewPipelineNodes = useMemo(
    () => buildPipelineProgressNodes(
      pipelineStageDefs,
      latestRunStages,
      latestRun?.status,
      latestRun?.failed_stage,
    ),
    [pipelineStageDefs, latestRunStages, latestRun?.status, latestRun?.failed_stage],
  );

  const headerDisplayStatus = resolveProjectDisplayStatus(
    project?.status,
    latestRun?.status,
  );

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
        <Card>
          <LoadingState message="正在加载项目信息..." />
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <BackToProjectsLink />
        <Card className="border-danger-500/30 bg-danger-500/5">
          <ErrorState
            title="加载失败"
            message={error}
            onRetry={() => setReloadTick((t) => t + 1)}
          />
        </Card>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <BackToProjectsLink />
        <Card>
          <EmptyState
            title="项目不存在"
            description={`未找到项目 ${id}，请检查项目 ID 是否正确`}
            action={{ label: '返回项目列表', onClick: () => navigate('/') }}
          />
        </Card>
      </div>
    );
  }

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        return <ProjectOverview project={project} stats={overviewStats} pipelineNodes={overviewPipelineNodes} />;
      case 'questions':
        return (
          <QuestionsTab
            projectId={id}
            projectMode={resolvedProjectMode}
            onSaved={handleResearchSaved}
            pollWhileRunning={isRunActive}
            revalidateKey={revalidateKey}
          />
        );
      case 'literature':
        return <LiteratureTab projectId={id} />;
      case 'datasets':
        return <DatasetPage projectId={id} projectMode={resolvedProjectMode} researchQuestion={resolvedResearchQuestion} />;
      case 'workflow':
        return (
          <WorkflowTab
            projectId={id}
            researchQuestion={resolvedResearchQuestion}
            questionSource={questionSource}
            onPipelineCompleted={handlePipelineCompleted}
            onPipelineStarted={handlePipelineStarted}
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
        status={headerDisplayStatus}
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

      {dataUploadGate.awaiting && !dataGateDismissed && !onRequiredDatasetsTab && dataUploadGate.runId && (
        <DataUploadGateFloating
          pendingCount={dataUploadGate.pendingCount}
          uploadedCount={dataUploadGate.uploadedCount}
          onGoToDatasets={() => {
            setDataGateDismissed(true);
            navigate(buildProjectTabUrl(id, 'datasets', {
              subtab: 'required-datasets',
              run_id: dataUploadGate.runId ?? undefined,
            }));
          }}
          onDismiss={() => setDataGateDismissed(true)}
        />
      )}
    </div>
  );
}