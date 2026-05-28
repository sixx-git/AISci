import { useState, useCallback, useRef, useEffect } from 'react';
import { Send, AlertTriangle } from 'lucide-react';
import { Card } from '@/components/Card';
import { AgentNode } from '@/components/AgentNode';
import { AgentDetailPanel } from '@/components/AgentDetailPanel';
import { WorkflowActionBar } from '@/components/WorkflowActionBar';
import { HumanInLoopCard } from '@/components/HumanInLoopCard';
import { Button } from '@/components/Button';
import { MOCK_AGENT_NODES } from '@/data/mockData';
import { pipelineService } from '@/services/pipelineService';
import env from '@/config/env';
import type {
  AgentNodeData,
  AgentStatus,
  PipelineRunResult,
  PipelineStageLog,
} from '@/types';

// ============ 接口 ============

interface WorkflowPageProps {
  projectId?: string;
  researchQuestion?: string;
  compact?: boolean;
}

// ============ 常量 ============

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

/** 后端状态 → 前端 AgentStatus */
function mapStatus(status: string): AgentStatus {
  switch (status) {
    case 'running':
      return 'running';
    case 'completed':
      return 'completed';
    case 'failed':
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
}: WorkflowPageProps) {
  // ────── 节点与选中状态 ──────
  const [nodes, setNodes] = useState<AgentNodeData[]>(
    () => MOCK_AGENT_NODES.map((n) => ({ ...n })),
  );
  const [selectedId, setSelectedId] = useState<string>(MOCK_AGENT_NODES[0].id);

  // ────── 运行状态 ──────
  const [isRunning, setIsRunning] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

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

  const handleSelect = useCallback((id: string) => {
    setSelectedId(id);
  }, []);

  // ══════════════════════════════════════════════
  //  将 API stages 合并到节点
  // ══════════════════════════════════════════════
  const applyStageResults = useCallback((result: PipelineRunResult) => {
    setNodes((prev) => {
      const updated = prev.map((node) => {
        const matchedStage = result.stages?.find(
          (s) => STAGE_TO_NODE_ID[s.stage] === node.id,
        );
        return matchedStage ? mergeStageData(node, matchedStage) : node;
      });

      if (result.failed_stage) {
        const failedNodeId = STAGE_TO_NODE_ID[result.failed_stage];
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

      pollingRef.current = setInterval(async () => {
        try {
          const response = await pipelineService.getStatus(runId);
          const result: PipelineRunResult = response.data;

          if (!result) return;

          applyStageResults(result);

          if (result.status === 'completed' || result.status === 'failed') {
            if (pollingRef.current) clearInterval(pollingRef.current);
            pollingRef.current = null;
            setIsRunning(false);
            setCurrentRunId(null);

            if (result.status === 'failed') {
              setErrorMessage(
                result.error_message ||
                (result.failed_stage
                  ? `执行失败在阶段: ${result.failed_stage}`
                  : 'Pipeline 执行失败'),
              );
            } else {
              setErrorMessage(null);
            }
          }
        } catch (err: unknown) {
          // 轮询网络失败也要显示，且不中断轮询
          const msg = err instanceof Error ? err.message : String(err);
          console.error('轮询状态失败:', msg);
          setErrorMessage(`轮询状态失败: ${msg}`);
        }
      }, 1500);
    },
    [applyStageResults],
  );

  // ══════════════════════════════════════════════
  //  重置所有节点到初始状态
  // ══════════════════════════════════════════════
  const resetNodes = useCallback(() => {
    setNodes((prev) =>
      prev.map((n) => ({
        ...n,
        status: 'pending' as const,
        duration: null,
        logs: [],
        input_data: null,
        output_data: null,
        error_message: null,
        prompt_used: null,
        model_parameters: null,
        token_count: null,
      })),
    );
  }, []);

  // ══════════════════════════════════════════════
  //  Mock 模式：纯前端模拟执行
  // ══════════════════════════════════════════════
  const runMockPipeline = useCallback(() => {
    setIsRunning(true);
    setIsLoading(false);
    setErrorMessage(null);
    let idx = 0;
    const runNext = () => {
      setNodes((prev) => {
        const next = [...prev];
        if (idx < next.length) {
          next[idx] = { ...next[idx], status: 'running' as const, duration: null };
        }
        return next;
      });
      setNodes((prev) => {
        if (idx < prev.length) setSelectedId(prev[idx].id);
        return prev;
      });

      setTimeout(() => {
        setNodes((prev) => {
          const next = [...prev];
          if (idx < next.length) {
            const dur = 1500 + Math.random() * 3500;
            next[idx] = {
              ...next[idx],
              status: 'completed' as const,
              duration: Math.round(dur),
              logs: [...next[idx].logs, `[${new Date().toLocaleTimeString()}] 执行完成 (mock)`],
            };
          }
          return next;
        });
        idx++;
        if (idx < MOCK_AGENT_NODES.length) {
          runNext();
        } else {
          setIsRunning(false);
        }
      }, 1500 + Math.random() * 2000);
    };
    runNext();
  }, []);

  // ══════════════════════════════════════════════
  //  运行全部（核心入口，严格区分 mock / real）
  // ══════════════════════════════════════════════
  const handleRunAll = useCallback(async () => {
    // ── Mock 模式 ──
    if (env.USE_MOCK) {
      runMockPipeline();
      return;
    }

    // ── 真实模式：前置校验 ──
    if (!projectId) {
      setErrorMessage('缺少项目 ID，无法运行真实 Pipeline。');
      return;
    }

    if (!finalResearchQuestion) {
      setErrorMessage('缺少研究问题，请先在研究问题页面填写并保存，或在上方输入框中输入。');
      return;
    }

    // ── 真实模式：调用后端 API ──
    setIsRunning(true);
    setIsLoading(true);
    setErrorMessage(null);
    resetNodes();

    try {
      const response = await pipelineService.run(projectId, finalResearchQuestion);
      const result: PipelineRunResult = response.data;

      if (!result) {
        setErrorMessage('后端返回空数据，请检查服务状态');
        setIsLoading(false);
        setIsRunning(false);
        return;
      }

      setCurrentRunId(result.run_id);
      setIsLoading(false);

      // 同步返回（已完成 / 失败）
      if (result.status === 'completed' || result.status === 'failed') {
        applyStageResults(result);
        setIsRunning(false);
        if (result.status === 'failed') {
          setErrorMessage(
            result.error_message ||
            (result.failed_stage ? `执行失败在阶段: ${result.failed_stage}` : 'Pipeline 执行失败'),
          );
        }
      } else {
        // 异步执行 → 轮询
        startPolling(result.run_id);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      console.error('Pipeline 执行失败:', message);
      setErrorMessage(`Pipeline 请求失败: ${message}`);
      setIsLoading(false);
      setIsRunning(false);
    }
  }, [
    projectId,
    finalResearchQuestion,
    runMockPipeline,
    resetNodes,
    applyStageResults,
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
    setIsRunning(false);
  }, []);

  // ══════════════════════════════════════════════
  //  重置
  // ══════════════════════════════════════════════
  const handleReset = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    setIsRunning(false);
    setIsLoading(false);
    setErrorMessage(null);
    setCurrentRunId(null);
    setLocalResearchQuestion('');
    setNodes(MOCK_AGENT_NODES.map((n) => ({ ...n })));
    setSelectedId(MOCK_AGENT_NODES[0].id);
  }, []);

  // ══════════════════════════════════════════════
  //  重新运行（严格区分 mock / real）
  // ══════════════════════════════════════════════
  const handleRerun = useCallback(
    async (id: string) => {
      // ── Mock 模式 ──
      if (env.USE_MOCK) {
        setNodes((prev) =>
          prev.map((n) =>
            n.id === id
              ? {
                  ...n,
                  status: 'running' as const,
                  duration: null,
                  logs: [
                    ...n.logs,
                    `[${new Date().toLocaleTimeString()}] 重新运行…`,
                  ],
                }
              : n,
          ),
        );
        setTimeout(() => {
          setNodes((prev) =>
            prev.map((n) =>
              n.id === id
                ? {
                    ...n,
                    status: 'completed' as const,
                    duration: Math.round(2000 + Math.random() * 3000),
                    logs: [
                      ...n.logs,
                      `[${new Date().toLocaleTimeString()}] 运行完成 (mock)`,
                    ],
                  }
                : n,
            ),
          );
        }, 1500 + Math.random() * 2000);
        return;
      }

      // ── 真实模式：重新运行整个 Pipeline ──
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
          {env.USE_MOCK && (
            <span className="text-xs bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded font-medium">
              当前为 Mock 模式
            </span>
          )}
          {!env.USE_MOCK && projectId && (
            <span className="text-xs bg-blue-500/20 text-blue-300 px-2 py-0.5 rounded">
              Live API Mode
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

      {/* ========== 真实模式下研究问题缺失时的兜底输入 ========== */}
      {!env.USE_MOCK && !researchQuestion && (
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
      {isLoading && (
        <div className="mb-6 p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-blue-400 border-t-transparent rounded-full animate-spin shrink-0" />
          <p className="text-sm text-blue-300">正在向后台提交 Pipeline 请求…</p>
        </div>
      )}

      {/* ========== 操作栏 ========== */}
      <div className="mb-6">
        <WorkflowActionBar
          nodes={nodes}
          isRunning={isRunning || isLoading}
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