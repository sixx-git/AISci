import { useEffect, useState } from 'react';
import { ChevronDown, ChevronRight, Download } from 'lucide-react';
import { SideDrawer } from '@/components/overview/SideDrawer';
import { Button } from '@/components/Button';
import { LoadingState } from '@/components/workspace/LoadingState';
import { mapStageExecutionStatus } from '@/lib/pipelineProgressNodes';
import { isExperimentStageKey, type SnapshotItem, type StageOutputSnapshot } from '@/lib/overviewSubmission';
import type { EvidenceChain } from '@/types';

export interface HypothesisChainPreview {
  hypothesisId: string;
  title: string;
  supportCount: number;
  counterCount: number;
  supporting: string[];
  opposing: string[];
}

interface StageOutputsDrawerProps {
  open: boolean;
  loading?: boolean;
  stages: StageOutputSnapshot[];
  focusKey?: string | null;
  evidenceChains?: HypothesisChainPreview[];
  onClose: () => void;
  onDownloadStage?: (stage: StageOutputSnapshot) => void;
}

function statusText(status: string): string {
  const mapped = mapStageExecutionStatus(status);
  if (mapped === 'completed') return '已完成';
  if (mapped === 'running') return '运行中';
  if (mapped === 'error') return '失败';
  return '未开始';
}

function HighlightList({ items }: { items: SnapshotItem[] }) {
  if (items.length === 0) {
    return <p className="text-xs text-bp-muted">该阶段暂无结构化要点（仍可下载原始 JSON）</p>;
  }
  return (
    <ul className="space-y-2">
      {items.map((item, idx) => (
        <li key={`${item.title}-${idx}`} className="text-sm text-bp-text leading-relaxed">
          {item.title}
          {(item.source || item.detail) && (
            <span className="block text-xs text-bp-muted mt-0.5">
              {[item.source, item.detail].filter(Boolean).join(' · ')}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

function StageBlock({
  stage,
  defaultOpen,
  onDownload,
}: {
  stage: StageOutputSnapshot;
  defaultOpen: boolean;
  onDownload?: (stage: StageOutputSnapshot) => void;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const [showJson, setShowJson] = useState(false);

  useEffect(() => {
    setOpen(defaultOpen);
  }, [defaultOpen]);

  const emptyOutput = Object.keys(stage.output).length === 0;

  return (
    <div className="rounded-bp border border-bp-border bg-bp-panel/40">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-2.5 text-left"
      >
        {open ? <ChevronDown className="w-4 h-4 text-bp-muted shrink-0" /> : <ChevronRight className="w-4 h-4 text-bp-muted shrink-0" />}
        <span className="text-sm font-medium text-bp-text flex-1 min-w-0">{stage.label}</span>
        <span className="text-xs text-bp-muted shrink-0">{statusText(stage.status)}</span>
        <span className="text-xs text-bp-muted shrink-0">{stage.highlights.length} 条要点</span>
      </button>
      {open && (
        <div className="px-3 pb-3 space-y-3 border-t border-bp-border">
          <div className="flex flex-wrap items-center gap-2 pt-3 text-xs text-bp-muted">
            {stage.model && <span>模型 {stage.model}</span>}
            {stage.token_count != null && <span>{stage.token_count} tokens</span>}
            {stage.duration_ms != null && <span>{Math.round(stage.duration_ms / 1000)}s</span>}
            {onDownload && (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                icon={<Download className="w-3.5 h-3.5" />}
                disabled={emptyOutput}
                onClick={() => onDownload(stage)}
              >
                下载本阶段 JSON
              </Button>
            )}
          </div>
          <HighlightList items={stage.highlights} />
          <button
            type="button"
            className="text-xs text-bp-cyan hover:underline"
            onClick={() => setShowJson((v) => !v)}
          >
            {showJson ? '收起原始输出' : '查看原始 JSON'}
          </button>
          {showJson && (
            <pre className="text-xs text-bp-muted font-mono whitespace-pre-wrap bg-bp-base/60 border border-bp-border rounded-bp p-3 max-h-64 overflow-y-auto">
              {emptyOutput ? '（无输出）' : JSON.stringify(stage.output, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

export function StageOutputsDrawer({
  open,
  loading = false,
  stages,
  focusKey,
  evidenceChains = [],
  onClose,
  onDownloadStage,
}: StageOutputsDrawerProps) {
  const visible = stages.filter((s) => !isExperimentStageKey(s.key));
  return (
    <SideDrawer
      open={open}
      wide
      title="各阶段智能体产出"
      subtitle="问题理解到报告生成的结构化结果与证据链摘要；迭代实验请在概览页下载历史"
      onClose={onClose}
    >
      {loading && <LoadingState compact message="正在加载各阶段输出…" />}
      {!loading && visible.length === 0 && (
        <p className="text-sm text-bp-muted">暂无阶段输出。</p>
      )}
      {!loading && visible.length > 0 && (
        <div className="space-y-4">
          {evidenceChains.length > 0 && (
            <section className="rounded-bp border border-bp-border bg-bp-panel/40 p-3 space-y-3">
              <h3 className="text-sm font-semibold text-bp-text">证据链（候选假设）</h3>
              {evidenceChains.map((chain) => (
                <div key={chain.hypothesisId} className="text-sm">
                  <p className="text-bp-text leading-relaxed">{chain.title}</p>
                  <p className="text-xs text-bp-muted mt-1">
                    支持 {chain.supportCount} · 反对 {chain.counterCount}
                  </p>
                  {chain.supporting.slice(0, 3).map((text) => (
                    <p key={text} className="text-xs text-bp-muted mt-1">支持：{text}</p>
                  ))}
                  {chain.opposing.slice(0, 3).map((text) => (
                    <p key={text} className="text-xs text-bp-muted mt-1">反对：{text}</p>
                  ))}
                </div>
              ))}
            </section>
          )}
          {visible.map((stage) => (
            <StageBlock
              key={stage.key}
              stage={stage}
              defaultOpen={focusKey ? stage.key === focusKey : stage.key === visible[0]?.key}
              onDownload={onDownloadStage}
            />
          ))}
        </div>
      )}
    </SideDrawer>
  );
}

export function chainToPreview(
  hypothesisId: string,
  title: string,
  chain: EvidenceChain | null,
): HypothesisChainPreview {
  const supporting = chain?.supporting_evidence || [];
  const opposing = chain?.counter_evidence || [];
  return {
    hypothesisId,
    title,
    supportCount: chain?.support_count ?? supporting.length,
    counterCount: chain?.counter_count ?? opposing.length,
    supporting: supporting.map((e) => e.claim || e.quote_or_summary || '').filter(Boolean).slice(0, 4),
    opposing: opposing.map((e) => e.claim || e.quote_or_summary || '').filter(Boolean).slice(0, 4),
  };
}
