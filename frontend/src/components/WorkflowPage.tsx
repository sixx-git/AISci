import { useState, useCallback, useRef, useEffect } from 'react';
import { Send, AlertTriangle, Brain, BookOpen, GitBranch, Lightbulb, ShieldCheck, FlaskConical, ClipboardCheck, FileText } from 'lucide-react';
import { Card } from '@/components/Card';
import { AgentNode } from '@/components/AgentNode';
import { AgentDetailPanel } from '@/components/AgentDetailPanel';
import { WorkflowActionBar } from '@/components/WorkflowActionBar';
import { HumanInLoopCard } from '@/components/HumanInLoopCard';
import { Button } from '@/components/Button';
import { pipelineService } from '@/services/pipelineService';
import type {
  AgentNodeData,
  AgentStatus,
  PipelineRunResult,
  PipelineStageLog,
} from '@/types';

// // ============ 接口 ============

interface WorkflowPageProps {
  projectId?: string;
  researchQuestion?: string;
  compact?: boolean;
  onPipelineCompleted?: (result: PipelineRunResult) => void;
}

type RunState = 'idle' | 'submitting' | 'running' | 'polling';

/** 轮询连续失败上限 */
const MAX_CONSECUTIVE_POLL_FAILURES = 3;
/** 轮询间隔 ms */
const POLL_INTERVAL_MS = 2000;

/** 阶段名称 → 节点 ID 映射 */
const STAGE_TO_NODE_ID: Record<string, string> = {
  problem_understanding: 'problem',
  literature_mining: 'literature',
  knowledge_gap: 'gaps',
  hypothesis_generation: 'hypothesis',
  hypothesis_review: 'evaluation',
  experiment_design: 'experiment',
  small_validation: 'validation',
  report_generation: 'report',
};

// ============ 工具函数 ============

/** 固定的 Pipeline 节点拓扑定义 —— 系统的8个真实智能体 */
const BASE_AGENT_NODES: AgentNodeData[] = [
  {
    id: 'problem', name: '问题理解智能体',
    shortDesc: '解析研究问题的核心要素与上下文',
    status: 'pending', duration: null,
    inputSummary: '', outputSummary: '', logs: [],
    model: '', promptVersion: '', icon: Brain,
  },
  {
    id: 'literature', name: '文献挖掘智能体',
    shortDesc: '从 arXiv / OpenAlex 等源检索与挖掘相关文献',
    status: 'pending', duration: null,
    inputSummary: '', outputSummary: '', logs: [],
    model: '', promptVersion: '', icon: BookOpen,
  },
  {
    id: 'gaps', name: '知识缺口发现智能体',
    shortDesc: '分析现有文献，识别知识空白与研究机会',
    status: 'pending', duration: null,
    inputSummary: '', outputSummary: '', logs: [],
    model: '', promptVersion: '', icon: GitBranch,
  },
  {
    id: 'hypothesis', name: '假设生成智能体',
    shortDesc: '基于知识缺口生成可验证的科学假设',
    status: 'pending', duration: null,
    inputSummary: '', outputSummary: '', logs: [],
    model: '', promptVersion: '', icon: Lightbulb,
  },
  {
    id: 'evaluation', name: '可行性评估智能体',
    shortDesc: '评审假设的科学性与实验可行性',
    status: 'pending', duration: null,
    inputSummary: '', outputSummary: '', logs: [],
    model: '', promptVersion: '', icon: ShieldCheck,
  },
  {
    id: 'experiment', name: '实验设计智能体',
    shortDesc: '规划验证假设所需的实验方案',
    status: 'pending', duration: null,
    inputSummary: '', outputSummary: '', logs: [],
    model: '', promptVersion: '', icon: FlaskConical,
  },
  {
    id: 'validation', name: '小样验证智能体',
    shortDesc: '在受限数据集上执行快速验证实验',
    status: 'pending', duration: null,
    inputSummary: '', outputSummary: '', logs: [],
    model: '', promptVersion: '', icon: ClipboardCheck,
  },
  {
    id: 'report', name: '报告生成智能体',
    shortDesc: '汇总所有阶段结果，生成可导出报告',
    status: 'pending', duration: null,
    inputSummary: '', outputSummary: '', logs: [],
    model: '', promptVersion: '', icon: FileText,
  },
];

function createInitialNodes(): AgentNodeData[] {
  return BASE_AGENT_NODES.map((n) => ({ ...n, logs: [] }));
}

function normalizeStageName(stage?: string): string {
  if (!stage) return '';
  return stage
    .toLowerCase()
    .replace(/[\s-]+/g, '_')
    .trim();
}

/** 归一化状态名：统一处理大写、小写、短横线、空格等变体 */
function normalizeStatus(status?: string): string {
  if (!status) return 'pending';
  return status
    .toLowerCase()
    .replace(/[\s-]+/g, '_')
    .trim();
}

/** 后端状态 → 前端 AgentStatus */
function mapStatus(status: string): AgentStatus {
  const normalized = normalizeStatus(status);
  switch (normalized) {
    case 'running':
    case 'processing':
      return 'running';
    case 'completed':
    case 'success':
    case 'done':
    case 'finished':
      return 'completed';
    case 'failed':
    case 'error':
    case 'fault':
      return 'failed';
    case 'human_review_required':
    case 'review':
    case 'needs_review':
    case 'human_review':
      return 'human_review_required';
    default:
      return 'pending';
  }
}

/** 将 API 阶段数据合并到前端节点上 */
function mergeStageData(node: AgentNodeData, stage: PipelineStageLog): AgentNodeData {
  const newStatus = mapStatus(stage.status);
  const durationMs =
    stage.duration_ms ?? (stage.duration ? Math.round(stage.duration * 1000) : null);

  const logEntry = stage.error_message
    ? `[${new Date().toLocaleTimeString()}] ${newStatus}: ${stage.error_message}`
    : newStatus !== node.status
      ? `[${new Date().toLocaleTimeString()}] 状态: ${newStatus}`
      : null;

  return {
    ...node,
    status: newStatus,
    duration: durationMs,
    logs: logEntry ? [...node.logs, logEntry] : node.logs,
    input_data: stage.input_data ?? node.input_data,
    output_data: stage.output_data ?? node.output_data,
    error_message: stage.error_message ?? node.error_message,
    prompt_used: stage.prompt_used ?? node.prompt_used,
    model_used: stage.model_used ?? node.model_used,
    model_parameters: stage.model_parameters ?? node.model_parameters,
    token_count: stage.token_count ?? node.token_count,
    model: stage.model_used || node.model,
    inputSummary: stage.input_data
      ? JSON.stringify(stage.input_data).slice(0, 200)
      : node.inputSummary,
    outputSummary: stage.output_data
      ? JSON.stringify(stage.output_data).slice(0, 200)
      : node.outputSummary,
  };
}

// ============ 组件 ============

export function WorkflowPage({
  projectId,
  researchQuestion,
  compact: _compact = false,
  onPipelineCompleted,
}: WorkflowPageProps) {
  // ────── 节点与选中状态 ──────
  const [nodes, setNodes] = useState<AgentNodeData[]>(() => createInitialNodes());
  const [selectedId, setSelectedId] = useState<string>('');

  // ────── 运行状态 ──────
  const [runState, setRunState] = useState<RunState>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [hasExistingRuns, setHasExistingRuns] = useState<boolean | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const consecutiveFailuresRef = useRef(0);

  // ────── 研究问题兜底输入（当 props 为空时显示） ──────
  const [localResearchQuestion, setLocalResearchQuestion] = useState('');
  const finalResearchQuestion = (researchQuestion ?? '').trim() || localResearchQuestion.trim();

  const selectedNode = nodes.find((n) => n.id === selectedId) ?? null;

  // ══════════════════════════════════════════════
  //  生命周期：清理轮询
  // ══════════════════════════════════════════════
  useEffect(() => {
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  const loadLatestRun = useCallback(async () => {
    if (!projectId) {
      setHasExistingRuns(null);
      return;
    }
    try {
      const runsRes = await pipelineService.getRuns(projectId);
      if (runsRes.code !== 200 || !runsRes.data || runsRes.data.length === 0) {
        setHasExistingRuns(false);
        return;
      }
      const latestRun = runsRes.data[0];
      const detailRes = await pipelineService.getRunDetail(latestRun.run_id);
      if (detailRes.code !== 200 || !detailRes.data) {
        setHasExistingRuns(false);
        return;
      }
      const runDetail = detailRes.data;
      setHasExistingRuns(true);
      setNodes(() => {
        const base = createInitialNodes();
        return base.map((node) => {
          const matchedStage = runDetail.stages?.find(
            (s) => normalizeStageName(s.stage) === node.id ||
              STAGE_TO_NODE_ID[normalizeStageName(s.stage)] === node.id,
          );
          return matchedStage ? mergeStageData(node, matchedStage as PipelineStageLog) : node;
        });
      });
    } catch (err: unknown) {
      console.error('加载最新运行记录失败:', err);
      setHasExistingRuns(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadLatestRun();
  }, [loadLatestRun]);

  const handleSelect = useCallback((id: string) => {
    setSelectedId(id);
  }, []);

  // ══════════════════════════════════════════════
  //  用数据库中的真实 stages 刷新节点
  // ══════════════════════════════════════════════
  const refreshFromRunDetail = useCallback(async (runId: string) => {
    try {
      const detailRes = await pipelineService.getRunDetail(runId);
      if (detailRes.code !== 200 || !detailRes.data) return;
      const runDetail = detailRes.data;
      setNodes(createInitialNodes().map((node) => {
        const matchedStage = runDetail.stages?.find(
          (s) => normalizeStageName(s.stage) === node.id ||
            STAGE_TO_NODE_ID[normalizeStageName(s.stage)] === node.id,
        );
        return matchedStage ? mergeStageData(node, matchedStage as PipelineStageLog) : node;
      }));
    } catch (err: unknown) {
      console.error('刷新运行详情失败:', err);
    }
  }, []);

  // ══════════════════════════════════════════════
  //  将 API stages 合并到节点
  // ══════════════════════════════════════════════
  const applyStageResults = useCallback((result: PipelineRunResult) => {
    setNodes((prev) => {
      const base = prev.length > 0 ? prev : createInitialNodes();

      const updated = base.map((node) => {
        const matchedStage = result.stages?.find(
          (s) => normalizeStageName(s.stage) === node.id ||
            STAGE_TO_NODE_ID[normalizeStageName(s.stage)] === node.id,
        );
        return matchedStage ? mergeStageData(node, matchedStage) : node;
      });

      if (import.meta.env.DEV) {
        result.stages?.forEach((s) => {
          const ns = normalizeStageName(s.stage);
          const nodeId = STAGE_TO_NODE_ID[ns] ?? ns;
          if (!BASE_AGENT_NODES.some((n) => n.id === nodeId)) {
            console.warn(`[WorkflowPage] 未知阶段: "${s.stage}"，不在8个节点定义中`);
          }
        });
      }

      if (result.failed_stage) {
        const normalized = normalizeStageName(result.failed_stage);
        const failedNodeId = STAGE_TO_NODE_ID[normalized] ?? normalized;
        if (failedNodeId) setSelectedId(failedNodeId);
      }

      return updated;
    });
  }, []);

  // ══════════════════════════════════════════════
  //  轮询 Pipeline 状态
  // ══════════════════════════════════════════════
  const startPolling = useCallback(
    (runId: string) => {
      if (pollingRef.current) clearInterval(pollingRef.current);
      consecutiveFailuresRef.current = 0;
      setRunState('polling');

      pollingRef.current = setInterval(async () => {
        try {
          const response = await pipelineService.getStatus(runId);
          const result: PipelineRunResult = response.data;

          if (!result) return;

          consecutiveFailuresRef.current = 0;
          applyStageResults(result);

          if (result.status === 'completed' || result.status === 'failed') {
            if (pollingRef.current) clearInterval(pollingRef.current);
            pollingRef.current = null;
            setRunState('idle');
            setCurrentRunId(null);

            await refreshFromRunDetail(runId);
            setHasExistingRuns(true);

            if (result.status === 'completed') {
              setErrorMessage(null);
              onPipelineCompleted?.(result);
            }

            if (result.status === 'failed') {
              setErrorMessage(
                result.error_message ||
                (result.failed_stage
                  ? `执行失败在阶段: ${result.failed_stage}`
                  : 'Pipeline 执行失败'),
              );
            }
          }
        } catch (err: unknown) {
          consecutiveFailuresRef.current += 1;
          const msg = err instanceof Error ? err.message : String(err);
          console.error(`轮询状态失败 (${consecutiveFailuresRef.current}/${MAX_CONSECUTIVE_POLL_FAILURES}):`, msg);

          if (consecutiveFailuresRef.current >= MAX_CONSECUTIVE_POLL_FAILURES) {
            if (pollingRef.current) clearInterval(pollingRef.current);
            pollingRef.current = null;
            setRunState('idle');
            setCurrentRunId(null);
            setErrorMessage('无法获取 Pipeline 状态，请检查后端服务是否仍在运行。');
          }
        }
      }, POLL_INTERVAL_MS);
    },
    [applyStageResults, refreshFromRunDetail, onPipelineCompleted],
  );

  // ══════════════════════════════════════════════
  //  重置所有节点到初始状态
  // ══════════════════════════════════════════════
  const resetNodes = useCallback(() => {
    setNodes(createInitialNodes());
  }, []);

  // ══════════════════════════════════════════════
  //  运行全部
  // ══════════════════════════════════════════════
  const handleRunAll = useCallback(async () => {
    if (!projectId) {
      setErrorMessage('缺少项目 ID，无法运行真实 Pipeline。');
      return;
    }

    if (!finalResearchQuestion) {
      setErrorMessage('缺少研究问题，请先在研究问题页面填写并保存，或在上方输入框中输入。');
      return;
    }

    setRunState('submitting');
    setErrorMessage(null);
    resetNodes();

    try {
      const response = await pipelineService.run(projectId, finalResearchQuestion);
      const result: PipelineRunResult = response.data;

      if (!result || !result.run_id) {
        setErrorMessage('后端返回数据无效，请检查服务状态');
        setRunState('idle');
        return;
      }

      setCurrentRunId(result.run_id);
      setRunState('running');

      startPolling(result.run_id);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      console.error('Pipeline 提交失败:', message);
      setErrorMessage(`Pipeline 提交失败: ${message}`);
      setRunState('idle');
    }
  }, [
    projectId,
    finalResearchQuestion,
    resetNodes,
    startPolling,
  ]);

  // ══════════════════════════════════════════════
  //  暂停
  // ══════════════════════════════════════════════
  const handlePause = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    setRunState('idle');
  }, []);

  // ══════════════════════════════════════════════
  //  重置
  // ══════════════════════════════════════════════
  const handleReset = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    setRunState('idle');
    setErrorMessage(null);
    setCurrentRunId(null);
    setLocalResearchQuestion('');
    setNodes(createInitialNodes());
    setSelectedId('');
    setHasExistingRuns(null);
    loadLatestRun();
  }, [loadLatestRun]);

  // ══════════════════════════════════════════════
  //  重新运行
  // ══════════════════════════════════════════════
  const handleRerun = useCallback(
    async (_id: string) => {
      if (!projectId) {
        setErrorMessage('缺少项目 ID，无法重新运行。');
        return;
      }
      if (!finalResearchQuestion) {
        setErrorMessage('缺少研究问题，无法重新运行。');
        return;
      }
      await handleRunAll();
    },
    [projectId, finalResearchQuestion, handleRunAll],
  );

  // ══════════════════════════════════════════════
  //  JSX
  // ══════════════════════════════════════════════
  return (
    <div className="max-w-7xl mx-auto">
      {/* ========== 头部 ========== */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-white mb-2">智能体工作流</h1>
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-gray-400 text-sm">从文献/数据输入到可验证科学假设输出的多智能体闭环</p>
          {projectId && (
            <span className="text-xs bg-blue-500/20 text-blue-300 px-2 py-0.5 rounded">
              API Connected
            </span>
          )}
        </div>

        {/* 研究问题展示 */}
        {(researchQuestion || localResearchQuestion) && (
          <p className="text-sm text-gray-500 mt-1 truncate">
            研究问题：{finalResearchQuestion}
          </p>
        )}

        {/* 运行 ID */}
        {currentRunId && (
          <p className="text-sm text-gray-500 mt-1 truncate font-mono text-xs">
            run_id: {currentRunId}
          </p>
        )}
      </div>

      {/* ========== 研究问题缺失时的兜底输入 ========== */}
      {!researchQuestion && (
        <div className="mb-5 p-4 bg-gray-800/50 border border-gray-700 rounded-lg">
          <p className="text-sm text-yellow-300 font-medium mb-2 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            缺少研究问题，请先在研究问题页面填写并保存，或在下方的输入框中直接输入
          </p>
          <div className="flex gap-2">
            <input
              type="text"
              value={localResearchQuestion}
              onChange={(e) => setLocalResearchQuestion(e.target.value)}
              placeholder="请输入研究问题后运行 Pipeline"
              className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500/50 transition-all"
            />
            <Button
              icon={<Send className="w-4 h-4" />}
              variant="primary"
              size="sm"
              disabled={!localResearchQuestion.trim()}
              onClick={() => {
                if (!finalResearchQuestion) {
                  setErrorMessage('请输入研究问题后再运行 Pipeline');
                } else {
                  handleRunAll();
                }
              }}
            >
              提交运行
            </Button>
          </div>
        </div>
      )}

      {/* ========== 错误提示 ========== */}
      {errorMessage && (
        <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-lg flex items-start gap-3">
          <div className="w-5 h-5 rounded-full bg-red-500/30 flex items-center justify-center shrink-0 mt-0.5">
            <span className="text-red-400 text-xs font-bold">!</span>
          </div>
          <div className="flex-1">
            <p className="text-sm text-red-300 font-medium">执行错误</p>
            <p className="text-sm text-red-400/80 mt-0.5 whitespace-pre-wrap">{errorMessage}</p>
          </div>
          <button
            onClick={() => setErrorMessage(null)}
            className="text-gray-500 hover:text-gray-300 shrink-0"
          >
            <span className="text-xs">✕</span>
          </button>
        </div>
      )}

      {/* ========== Loading 提示 ========== */}
      {runState === 'submitting' && (
        <div className="mb-6 p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-blue-400 border-t-transparent rounded-full animate-spin shrink-0" />
          <p className="text-sm text-blue-300">正在提交 Pipeline 任务…</p>
        </div>
      )}

      {runState === 'running' && !pollingRef.current && (
        <div className="mb-6 p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-blue-400 border-t-transparent rounded-full animate-spin shrink-0" />
          <p className="text-sm text-blue-300">Pipeline 后台运行中…</p>
        </div>
      )}

      {runState === 'polling' && (
        <div className="mb-6 p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-blue-400 border-t-transparent rounded-full animate-spin shrink-0" />
          <p className="text-sm text-blue-300">正在同步阶段状态…</p>
        </div>
      )}

      {/* ========== 无运行记录提示 ========== */}
      {hasExistingRuns === false && projectId && runState === 'idle' && (
        <div className="mb-6 p-4 bg-gray-800/50 border border-gray-700 rounded-lg flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center shrink-0">
            <span className="text-gray-400 text-sm">—</span>
          </div>
          <div>
            <p className="text-sm text-gray-300 font-medium">暂无真实运行记录</p>
            <p className="text-xs text-gray-500 mt-0.5">请点击运行 Pipeline 以启动智能体工作流</p>
          </div>
        </div>
      )}

      {/* ========== 操作栏 ========== */}
      <div className="mb-6">
        <WorkflowActionBar
          nodes={nodes}
          isRunning={runState !== 'idle'}
          onRunAll={handleRunAll}
          onPause={handlePause}
          onReset={handleReset}
        />
      </div>

      {/* ========== 主布局 ========== */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：节点列表 */}
        <div className="lg:col-span-1">
          <Card
            title="Pipeline 节点"
            subtitle={`共 ${nodes.length} 个智能体`}
            className="max-h-[calc(100vh-300px)] overflow-y-auto"
          >
            <div className="space-y-0">
              {nodes.map((node, idx) => (
                <AgentNode
                  key={node.id}
                  node={node}
                  isSelected={node.id === selectedId}
                  isLast={idx === nodes.length - 1}
                  stepNumber={idx + 1}
                  onClick={() => handleSelect(node.id)}
                />
              ))}
            </div>
          </Card>
        </div>

        {/* 右侧：详情 + 人在回路 */}
        <div className="lg:col-span-2 space-y-4">
          <AgentDetailPanel node={selectedNode} onRerun={handleRerun} />

          {selectedNode && selectedNode.status === 'human_review_required' && (
            <HumanInLoopCard />)}
        </div>
      </div>
    </div>
  );
}