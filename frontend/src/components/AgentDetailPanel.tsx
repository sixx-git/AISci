import { cn } from '@/lib/utils';
import {
  Cpu, FileCode, RotateCcw,
} from 'lucide-react';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import type { AgentNodeData } from '@/data/mockData';

interface AgentDetailPanelProps {
  node: AgentNodeData | null;
  onRerun?: (id: string) => void;
}

export function AgentDetailPanel({ node, onRerun }: AgentDetailPanelProps) {
  if (!node) {
    return (
      <Card className="h-full flex flex-col items-center justify-center text-center py-16">
        <Cpu className="w-16 h-16 text-gray-700 mx-auto mb-4" />
        <p className="text-gray-500">点击左侧智能体节点查看详情</p>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* 智能体头部 */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary-500/20 flex items-center justify-center">
              <node.icon className="w-5 h-5 text-primary-400" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white">{node.name}</h3>
              <p className="text-xs text-gray-500">{node.shortDesc}</p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            icon={<RotateCcw className="w-3.5 h-3.5" />}
            onClick={() => onRerun?.(node.id)}
            disabled={node.status === 'running'}
          >
            重新运行
          </Button>
        </div>
      </Card>

      {/* 输入数据 */}
      <Card title="输入数据" subtitle="上游节点传递的上下文信息">
        <div className="p-3 bg-gray-900/70 border border-gray-800 rounded-lg">
          <p className="text-sm text-gray-300 whitespace-pre-wrap">{node.inputSummary}</p>
        </div>
      </Card>

      {/* 输出结果 */}
      <Card title="输出结果" subtitle="智能体处理后的结构化输出">
        <div className={cn(
          'p-3 rounded-lg border',
          node.status === 'completed' ? 'bg-green-500/5 border-green-500/20' :
          node.status === 'running' ? 'bg-blue-500/5 border-blue-500/20' :
          'bg-gray-900/70 border-gray-800',
        )}>
          <p className={cn(
            'text-sm whitespace-pre-wrap',
            node.status === 'completed' ? 'text-gray-200' :
            node.status === 'running' ? 'text-blue-300' :
            'text-gray-500 italic',
          )}>
            {node.outputSummary}
          </p>
        </div>
      </Card>

      {/* 运行日志 */}
      <Card title="运行日志" subtitle="实时执行记录">
        {node.logs.length === 0 ? (
          <p className="text-sm text-gray-600 italic">暂无日志</p>
        ) : (
          <div className="space-y-0.5 max-h-48 overflow-y-auto">
            {node.logs.map((log, idx) => (
              <div
                key={idx}
                className="flex items-start gap-2 p-1.5 rounded text-xs font-mono"
              >
                <span className="text-gray-700 shrink-0">{idx + 1}</span>
                <span className="text-gray-400">{log}</span>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* 技术信息 */}
      <Card>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="flex items-center gap-2">
            <Cpu className="w-4 h-4 text-gray-500" />
            <div>
              <div className="text-[11px] text-gray-500">使用模型</div>
              <div className="text-xs text-gray-300 font-mono">{node.model}</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <FileCode className="w-4 h-4 text-gray-500" />
            <div>
              <div className="text-[11px] text-gray-500">Prompt 版本</div>
              <div className="text-xs text-gray-300 font-mono">{node.promptVersion}</div>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}