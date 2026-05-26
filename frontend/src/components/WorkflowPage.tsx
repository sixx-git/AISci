import { useState, useCallback } from 'react';
import { Card } from '@/components/Card';
import { AgentNode } from '@/components/AgentNode';
import { AgentDetailPanel } from '@/components/AgentDetailPanel';
import { WorkflowActionBar } from '@/components/WorkflowActionBar';
import { HumanInLoopCard } from '@/components/HumanInLoopCard';
import { MOCK_AGENT_NODES } from '@/data/mockData';
import type { AgentNodeData } from '@/types';

interface WorkflowPageProps {
  projectId?: string;
  compact?: boolean;
}

export function WorkflowPage({ projectId: _projectId, compact: _compact = false }: WorkflowPageProps) {
  const [nodes, setNodes] = useState<AgentNodeData[]>(MOCK_AGENT_NODES);
  const [selectedId, setSelectedId] = useState<string>(MOCK_AGENT_NODES[0].id);
  const [isRunning, setIsRunning] = useState(false);

  const selectedNode = nodes.find((n) => n.id === selectedId) ?? null;

  const handleSelect = useCallback((id: string) => {
    setSelectedId(id);
  }, []);

  const handleRunAll = useCallback(() => {
    setIsRunning(true);
    let idx = 0;
    const runNext = () => {
      setNodes((prev) => {
        const next = [...prev];
        // 将当前节点设为 running
        if (idx < next.length) {
          next[idx] = { ...next[idx], status: 'running' as const, duration: null };
        }
        return next;
      });
      setSelectedId(nodes[idx].id);

      setTimeout(() => {
        setNodes((prev) => {
          const next = [...prev];
          if (idx < next.length) {
            const dur = 1500 + Math.random() * 3500;
            next[idx] = {
              ...next[idx],
              status: 'completed' as const,
              duration: Math.round(dur),
              logs: [...next[idx].logs, `[${new Date().toLocaleTimeString()}] 执行完成`],
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
    setIsRunning(false);
  }, []);

  const handleReset = useCallback(() => {
    setIsRunning(false);
    setNodes(MOCK_AGENT_NODES);
    setSelectedId(MOCK_AGENT_NODES[0].id);
  }, []);

  const handleRerun = useCallback((id: string) => {
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
            ? { ...n, status: 'completed' as const, duration: Math.round(2000 + Math.random() * 3000), logs: [...n.logs, `[${new Date().toLocaleTimeString()}] 运行完成`] }
            : n,
        ),
      );
    }, 1500 + Math.random() * 2000);
  }, []);

  return (
    <div className="max-w-7xl mx-auto">
      {/* ========== 头部 ========== */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-white mb-2">智能体工作流</h1>
        <p className="text-gray-400">
          从文献/数据输入到可验证科学假设输出的多智能体闭环
        </p>
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