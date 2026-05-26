import { useState, useCallback, useRef, useEffect } from 'react';
import { Card } from '@/components/Card';
import { AgentNode } from '@/components/AgentNode';
import { AgentDetailPanel } from '@/components/AgentDetailPanel';
import { WorkflowActionBar } from '@/components/WorkflowActionBar';
import { HumanInLoopCard } from '@/components/HumanInLoopCard';
import { MOCK_AGENT_NODES } from '@/data/mockData';
import { pipelineService } from '@/services/pipelineService';
import env from '@/config/env';
import type { AgentNodeData, AgentStatus, PipelineRunResult } from '@/types';

interface WorkflowPageProps {
  projectId?: string;
  researchQuestion?: string;
  compact?: boolean;
}

// 阶段名称 → 节点 ID 映射
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

// 后端状态 → 前端 AgentStatus
function mapStatus(status: string): AgentStatus {
  switch (status) {
    case 'running': return 'running';
    case 'completed': return 'completed';
    case 'failed': return 'failed';
    default: return 'pending';
  }
}

export function WorkflowPage({ projectId, researchQuestion, compact: _compact = false }: WorkflowPageProps) {
  const [nodes, setNodes] = useState<AgentNodeData[]>(MOCK_AGENT_NODES);
  const [selectedId, setSelectedId] = useState<string>(MOCK_AGENT_NODES[0].id);
  const [isRunning, setIsRunning] = useState(false);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const selectedNode = nodes.find((n) => n.id === selectedId) ?? null;

  // 清理轮询
  useEffect(() => {
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  const handleSelect = useCallback((id: string) => {
    setSelectedId(id);
  }, []);

  // ────── 真实 API 模式：运行 Pipeline ──────
  const handleRunAll = useCallback(async () => {
    if (!projectId || !researchQuestion) {
      // 无 projectId 时走本地 mock 模拟（纯前端演示）
      runMockPipeline();
      return;
    }

    setIsRunning(true);
    // 重置所有节点为 pending
    setNodes((prev) => prev.map((n) => ({ ...n, status: 'pending' as const, duration: null, logs: [] })));

    try {
      const response = await pipelineService.run(projectId, researchQuestion);
      const result: PipelineRunResult = response.data;

      if (!result) {
        throw new Error('Empty response from pipeline');
      }

      setCurrentRunId(result.run_id);

      // 如果是同步返回（已完成或已失败），直接更新节点
      if (result.status === 'completed' || result.status === 'failed') {
        applyStageResults(result);
        setIsRunning(false);
      } else {
        // 异步轮询状态
        startPolling(result.run_id);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      console.error('Pipeline 执行失败:', message);
      setNodes((prev) =>
        prev.map((n, i) => ({
          ...n,
          status: i === 0 ? 'failed' as const : n.status,
          logs: [...n.logs, `[Error] ${message}`],
        }))
      );
      setIsRunning(false);
    }
  }, [projectId, researchQuestion]);

  // 轮询 Pipeline 状态
  const startPolling = useCallback((runId: string) => {
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
        }
      } catch (err) {
        console.error('轮询状态失败:', err);
      }
    }, 1500); // 每 1.5 秒轮询一次
  }, []);

  // 将 API 阶段结果映射到前端节点
  const applyStageResults = useCallback((result: PipelineRunResult) => {
    setNodes((prev) =>
      prev.map((node) => {
        // 按 node.id 映射到 stage key
        const matchedStage = result.stages?.find(
          (s) => STAGE_TO_NODE_ID[s.stage] === node.id
        );
        if (!matchedStage) return node;

        const newStatus = mapStatus(matchedStage.status);
        return {
          ...node,
          status: newStatus,
          duration: matchedStage.duration ? Math.round(matchedStage.duration * 1000) : node.duration,
          logs: matchedStage.error_message
            ? [...node.logs, `[${new Date().toLocaleTimeString()}] ${newStatus}: ${matchedStage.error_message}`]
            : newStatus !== node.status
              ? [...node.logs, `[${new Date().toLocaleTimeString()}] 状态: ${newStatus}`]
              : node.logs,
          outputSummary: matchedStage.output_data
            ? JSON.stringify(matchedStage.output_data).slice(0, 120) + '...'
            : node.outputSummary,
        };
      })
    );
  }, []);

  // ────── Mock 模式（纯前端模拟） ──────
  const runMockPipeline = useCallback(() => {
    setIsRunning(true);
    let idx = 0;
    const runNext = () => {
      setNodes((prev) => {
        const next = [...prev];
        if (idx < next.length) {
          next[idx] = { ...next[idx], status: 'running' as const, duration: null };
        }
        return next;
      });
      // 确保 nodes 在当前闭包中是最新的
      setNodes((prev) => {
        if (idx < prev.length) {
          setSelectedId(prev[idx].id);
        }
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
        if (idx < nodes.length) {
          runNext();
        } else {
          setIsRunning(false);
        }
      }, 1500 + Math.random() * 2000);
    };
    runNext();
  }, [nodes]);

  const handlePause = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    setIsRunning(false);
  }, []);

  const handleReset = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    setIsRunning(false);
    setCurrentRunId(null);
    setNodes(MOCK_AGENT_NODES);
    setSelectedId(MOCK_AGENT_NODES[0].id);
  }, []);

  const handleRerun = useCallback(async (id: string) => {
    if (!projectId || !researchQuestion) {
      // Mock re-run
      setNodes((prev) =>
        prev.map((n) =>
          n.id === id
            ? { ...n, status: 'running' as const, duration: null, logs: [...n.logs, `[${new Date().toLocaleTimeString()}] 重新运行…`] }
            : n,
        ),
      );
      setTimeout(() => {
        setNodes((prev) =>
          prev.map((n) =>
            n.id === id
              ? { ...n, status: 'completed' as const, duration: Math.round(2000 + Math.random() * 3000), logs: [...n.logs, `[${new Date().toLocaleTimeString()}] 运行完成 (mock)`] }
              : n,
          ),
        );
      }, 1500 + Math.random() * 2000);
      return;
    }
    // 真实模式：重新运行整个 Pipeline
    await handleRunAll();
  }, [projectId, researchQuestion, handleRunAll]);

  return (
    <div className="max-w-7xl mx-auto">
      {/* ========== 头部 ========== */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-white mb-2">智能体工作流</h1>
        <p className="text-gray-400">
          从文献/数据输入到可验证科学假设输出的多智能体闭环
          {!env.USE_MOCK && projectId && researchQuestion && (
            <span className="ml-2 text-xs bg-blue-500/20 text-blue-300 px-2 py-0.5 rounded">
              Live API Mode
            </span>
          )}
          {env.USE_MOCK && (
            <span className="ml-2 text-xs bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded">
              Mock Mode
            </span>
          )}
        </p>
        {researchQuestion && (
          <p className="text-sm text-gray-500 mt-1 truncate">
            研究问题：{researchQuestion}
          </p>
        )}
        {currentRunId && (
          <p className="text-sm text-gray-500 mt-1 truncate">
            运行 ID：{currentRunId}
          </p>
        )}
      </div>

      {/* ========== 操作栏 ========== */}
      <div className="mb-6">
        <WorkflowActionBar
          nodes={nodes}
          isRunning={isRunning}
          onRunAll={handleRunAll}
          onPause={handlePause}
          onReset={handleReset}
        />
      </div>

      {/* ========== 主布局 ========== */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：节点列表 */}
        <div className="lg:col-span-1">
          <Card title="Pipeline 节点" subtitle={`共 ${nodes.length} 个智能体`} className="max-h-[calc(100vh-300px)] overflow-y-auto">
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
          <AgentDetailPanel
            node={selectedNode}
            onRerun={handleRerun}
          />

          {selectedNode && selectedNode.status !== 'pending' && (
            <HumanInLoopCard />
          )}
        </div>
      </div>
    </div>
  );
}