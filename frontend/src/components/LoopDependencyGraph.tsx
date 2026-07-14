import { useMemo } from 'react';
import { ArrowRight } from 'lucide-react';
import type { ClosedLoopDecision, ClosedLoopEvent } from '@/types';
import { cn } from '@/lib/utils';

interface LoopDependencyGraphProps {
  events?: ClosedLoopEvent[];
  decisions?: ClosedLoopDecision[];
}

type GraphNode = {
  id: string;
  label: string;
  lane: 'discovery' | 'gap' | 'teaching' | 'evidence';
};

const NODES: GraphNode[] = [
  { id: 'ensemble_review', label: '集成评审', lane: 'discovery' },
  { id: 'discovery_refine', label: 'Discovery 迭代', lane: 'discovery' },
  { id: 'discovery_literature_refresh', label: '文献刷新', lane: 'discovery' },
  { id: 'hypothesis_generation', label: '假设生成', lane: 'discovery' },
  { id: 'data_gap_loop', label: 'Gap 补搜', lane: 'gap' },
  { id: 'knowledge_gap', label: '知识缺口', lane: 'gap' },
  { id: 'teaching_auto_refinement', label: 'Teaching 精化', lane: 'teaching' },
  { id: 'evidence_reasoning_loop', label: '证据链迭代', lane: 'evidence' },
];

const STATIC_EDGES: Array<{ from: string; to: string; label?: string }> = [
  { from: 'ensemble_review', to: 'discovery_refine', label: '未 Accept' },
  { from: 'discovery_refine', to: 'discovery_literature_refresh', label: '回退' },
  { from: 'discovery_literature_refresh', to: 'hypothesis_generation' },
  { from: 'hypothesis_generation', to: 'ensemble_review' },
  { from: 'data_gap_loop', to: 'knowledge_gap' },
  { from: 'knowledge_gap', to: 'hypothesis_generation' },
  { from: 'teaching_auto_refinement', to: 'hypothesis_generation' },
  { from: 'evidence_reasoning_loop', to: 'hypothesis_generation' },
];

const LANE_LABELS: Record<GraphNode['lane'], string> = {
  discovery: 'Discovery 主环',
  gap: 'Gap 数据环',
  teaching: 'Teaching 精化',
  evidence: '证据迭代',
};

const LANE_CLASS: Record<GraphNode['lane'], string> = {
  discovery: 'border-bp-cyan/30 bg-bp-cyan-tint/30',
  gap: 'border-bp-green/30 bg-bp-green/5',
  teaching: 'border-bp-yellow/30 bg-bp-yellow/5',
  evidence: 'border-bp-purple/30 bg-purple-500/5',
};

export function LoopDependencyGraph({ events, decisions }: LoopDependencyGraphProps) {
  const activeNodes = useMemo(() => {
    const set = new Set<string>();
    for (const e of events ?? []) {
      if (e.type) set.add(e.type);
    }
    for (const d of decisions ?? []) {
      if (d.action) set.add(d.action);
      if (d.next_stage) set.add(d.next_stage);
      if (d.trigger) set.add(d.trigger);
    }
    return set;
  }, [events, decisions]);

  const activeEdges = useMemo(() => {
    const set = new Set<string>();
    for (const d of decisions ?? []) {
      if (d.trigger && d.action) {
        set.add(`${d.trigger}->${d.action}`);
      }
      if (d.action && d.next_stage) {
        set.add(`${d.action}->${d.next_stage}`);
      }
    }
    for (let i = 0; i < (events?.length ?? 0) - 1; i += 1) {
      const a = events![i].type;
      const b = events![i + 1].type;
      if (a && b) set.add(`${a}->${b}`);
    }
    return set;
  }, [events, decisions]);

  const lanes: GraphNode['lane'][] = ['discovery', 'gap', 'teaching', 'evidence'];

  return (
    <div className="space-y-4 text-xs">
      <p className="text-bp-muted leading-relaxed">
        展示跨环因果拓扑。高亮节点/连线表示当前运行中实际触发的事件或决策路径（不调 LLM）。
      </p>

      {lanes.map((lane) => {
        const laneNodes = NODES.filter((n) => n.lane === lane);
        return (
          <div key={lane} className={cn('rounded-bp border p-3', LANE_CLASS[lane])}>
            <p className="text-bp-text font-medium mb-2">{LANE_LABELS[lane]}</p>
            <div className="flex flex-wrap items-center gap-2">
              {laneNodes.map((node, idx) => (
                <div key={node.id} className="flex items-center gap-2">
                  <span
                    className={cn(
                      'px-2 py-1 rounded-bp border text-xs',
                      activeNodes.has(node.id)
                        ? 'border-bp-cyan bg-bp-cyan-tint text-bp-cyan font-medium'
                        : 'border-bp-border bg-bp-panel/50 text-bp-muted',
                    )}
                  >
                    {node.label}
                  </span>
                  {idx < laneNodes.length - 1 && (
                    <ArrowRight className="w-3 h-3 text-bp-muted shrink-0" />
                  )}
                </div>
              ))}
            </div>
          </div>
        );
      })}

      <div className="rounded-bp border border-bp-border bg-bp-panel/20 p-3">
        <p className="text-bp-text font-medium mb-2">跨环依赖边</p>
        <ul className="space-y-1 text-bp-muted">
          {STATIC_EDGES.map((edge) => {
            const key = `${edge.from}->${edge.to}`;
            const active = activeEdges.has(key);
            return (
              <li
                key={key}
                className={cn(
                  'flex items-center gap-2',
                  active && 'text-bp-cyan font-medium',
                )}
              >
                <span>{NODES.find((n) => n.id === edge.from)?.label ?? edge.from}</span>
                <ArrowRight className="w-3 h-3 shrink-0" />
                <span>{NODES.find((n) => n.id === edge.to)?.label ?? edge.to}</span>
                {edge.label && (
                  <span className="text-xs text-bp-muted">({edge.label})</span>
                )}
                {active && <span className="text-xs text-bp-cyan">已触发</span>}
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
