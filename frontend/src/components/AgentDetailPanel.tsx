import { useState } from 'react';
import { cn } from '@/lib/utils';
import {
  Cpu, FileCode, RotateCcw, AlertTriangle,
  ChevronDown, ChevronRight, Clock, Hash,
} from 'lucide-react';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import type { AgentNodeData } from '@/types';

interface AgentDetailPanelProps {
  node: AgentNodeData | null;
  onRerun?: (id: string) => void;
}

/** 可折叠区域 */
function CollapsibleSection({
  title,
  defaultOpen = false,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-300 mb-2"
      >
        {open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        {title}
      </button>
      {open && children}
    </div>
  );
}

/** 格式化 JSON 展示 */
function JsonBlock({ data }: { data: unknown }) {
  if (data === null || data === undefined) {
    return <span className="text-sm text-gray-600 italic">无数据</span>;
  }
  const text = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
  return (
    <pre className="text-xs text-gray-400 font-mono whitespace-pre-wrap bg-gray-900/60 border border-gray-800 rounded-lg p-3 max-h-48 overflow-y-auto">
      {text}
    </pre>
  );
}

/** 格式化耗时（毫秒 → 可读） */
function formatDuration(ms: number | null): string {
  if (ms === null || ms === undefined) return '—';
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}min`;
}

export function AgentDetailPanel({ node, onRerun }: AgentDetailPanelProps) {
  const hasRealData = !!(node?.input_data || node?.output_data || node?.model_parameters || node?.prompt_used);

  if (!node) {
    return (
      <Card className="h-full flex flex-col items-center justify-center text-center py-16">
        <Cpu className="w-16 h-16 text-gray-700 mx-auto mb-4" />
        <p className="text-gray-500">点击左侧智能体节点查看详情</p>
      </Card>
    );
  }

  const isFailed = node.status === 'failed';
  const showHumanReview = node.status === 'human_review_required' || node.status === 'human_review';

  return (
    <div className="space-y-4">
      {/* ────── 智能体头部 ────── */}
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
          <div className="flex items-center gap-2">
            {node.duration !== null && node.status !== 'pending' && node.status !== 'running' && (
              <span className="text-xs text-gray-500 flex items-center gap-1">
                <Clock className="w-3.5 h-3.5" />
                {formatDuration(node.duration)}
              </span>
            )}
            <Button
              variant="secondary"
              size="sm"
              icon={<RotateCcw className="w-3.5 h-3.5" />}
              onClick={() => onRerun?.(node.id)}
              disabled={node.status === 'running'}
            >
              重新运行
            </Button>
          </div>
        </div>

        {/* 失败 / 需人工审查 提示 */}
        {isFailed && node.error_message && (
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            <p className="text-xs text-red-300 whitespace-pre-wrap">{node.error_message}</p>
          </div>
        )}
        {showHumanReview && (
          <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <p className="text-xs text-amber-300">此阶段需要人工审查确认后方可继续。</p>
          </div>
        )}
      </Card>

      {/* ────── 输入数据 ────── */}
      <Card title="输入数据" subtitle="上游节点传递的上下文信息">
        {hasRealData && node.input_data ? (
          <JsonBlock data={node.input_data} />
        ) : (
          <div className="p-3 bg-gray-900/70 border border-gray-800 rounded-lg">
            <p className="text-sm text-gray-300 whitespace-pre-wrap">{node.inputSummary}</p>
          </div>
        )}
      </Card>

      {/* ────── 输出结果 ────── */}
      <Card title="输出结果" subtitle="智能体处理后的结构化输出">
        <div className={cn(
          'p-3 rounded-lg border',
          isFailed ? 'bg-red-500/5 border-red-500/20' :
          node.status === 'completed' ? 'bg-green-500/5 border-green-500/20' :
          node.status === 'running' ? 'bg-blue-500/5 border-blue-500/20' :
          'bg-gray-900/70 border-gray-800',
        )}>
          {hasRealData && node.output_data ? (
            <JsonBlock data={node.output_data} />
          ) : (
            <p className={cn(
              'text-sm whitespace-pre-wrap',
              node.status === 'completed' ? 'text-gray-200' :
              node.status === 'running' ? 'text-blue-300' :
              'text-gray-500 italic',
            )}>
              {node.outputSummary}
            </p>
          )}
        </div>
      </Card>

      {/* ────── 运行日志 ────── */}
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

      {/* ────── 技术信息 ────── */}
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
          {node.token_count != null && (
            <div className="flex items-center gap-2">
              <Hash className="w-4 h-4 text-gray-500" />
              <div>
                <div className="text-[11px] text-gray-500">Token 消耗</div>
                <div className="text-xs text-gray-300 font-mono">{node.token_count.toLocaleString()}</div>
              </div>
            </div>
          )}
        </div>

        {/* 真实 API 数据：Prompt & Model Parameters */}
        {hasRealData && (
          <div className="mt-4 pt-4 border-t border-gray-800 space-y-3">
            {node.prompt_used && (
              <CollapsibleSection title="Prompt 内容" defaultOpen={false}>
                <pre className="text-xs text-gray-400 font-mono whitespace-pre-wrap bg-gray-900/60 border border-gray-800 rounded-lg p-3 max-h-64 overflow-y-auto">
                  {node.prompt_used}
                </pre>
              </CollapsibleSection>
            )}
            {node.model_parameters && (
              <CollapsibleSection title="模型参数" defaultOpen={false}>
                <div className="p-3 bg-gray-900/60 border border-gray-800 rounded-lg space-y-1.5">
                  {Object.entries(node.model_parameters).map(([k, v]) => (
                    <div key={k} className="flex items-baseline gap-2 text-xs">
                      <span className="text-gray-500 shrink-0">{k}:</span>
                      <span className="text-gray-300 font-mono">{String(v)}</span>
                    </div>
                  ))}
                </div>
              </CollapsibleSection>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}