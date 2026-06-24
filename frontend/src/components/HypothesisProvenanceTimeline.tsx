import { useEffect, useState } from 'react';
import { BookOpen, Database, Image, Target, Link2, Loader2, ExternalLink } from 'lucide-react';
import hypothesisService, { type ProvenanceTimelineStep } from '@/services/hypothesisService';

interface HypothesisProvenanceTimelineProps {
  hypothesisId: string;
  onNavigateToLiterature?: (documentId: string, chunkId?: string) => void;
}

const STEP_ICONS: Record<string, typeof BookOpen> = {
  literature_facts: BookOpen,
  multimodal: Image,
  dataset: Database,
  verifiable_spec: Target,
};

export function HypothesisProvenanceTimeline({
  hypothesisId,
  onNavigateToLiterature,
}: HypothesisProvenanceTimelineProps) {
  const [timeline, setTimeline] = useState<ProvenanceTimelineStep[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    hypothesisService.getProvenanceTimeline(hypothesisId)
      .then((res) => {
        if (cancelled) return;
        if (res.code === 200 && res.data?.timeline) {
          setTimeline(res.data.timeline);
        } else {
          setError(res.message || '加载溯源时间线失败');
        }
      })
      .catch(() => {
        if (!cancelled) setError('加载溯源时间线失败');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [hypothesisId]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs text-bp-muted py-4">
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
        加载溯源时间线…
      </div>
    );
  }

  if (error) {
    return <p className="text-xs text-amber-400/80 py-2">{error}</p>;
  }

  if (timeline.length === 0) {
    return <p className="text-xs text-bp-muted py-2">暂无溯源记录，请先运行 Pipeline 或补充证据。</p>;
  }

  return (
    <div className="relative pl-4 border-l border-bp-border/80 space-y-4">
      {timeline.map((step, idx) => {
        const Icon = STEP_ICONS[step.step] || Link2;
        return (
          <div key={`${step.step}-${idx}`} className="relative">
            <div className="absolute -left-[1.35rem] top-1 w-2.5 h-2.5 rounded-full bg-bp-cyan/80 ring-2 ring-bp-base" />
            <div className="flex items-center gap-1.5 mb-1.5">
              <Icon className="w-3.5 h-3.5 text-bp-cyan" />
              <span className="text-xs font-medium text-bp-text">{step.label}</span>
              <span className="text-[10px] text-bp-muted">({step.count ?? step.items?.length ?? 0})</span>
            </div>
            <div className="space-y-1.5">
              {(step.items || []).map((item, i) => (
                <TimelineItem
                  key={`${step.step}-item-${i}`}
                  step={step.step}
                  item={item}
                  onNavigateToLiterature={onNavigateToLiterature}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function TimelineItem({
  step,
  item,
  onNavigateToLiterature,
}: {
  step: string;
  item: Record<string, unknown>;
  onNavigateToLiterature?: (documentId: string, chunkId?: string) => void;
}) {
  if (step === 'literature_facts') {
    const docId = String(item.document_id || '');
    const chunkId = item.chunk_id ? String(item.chunk_id) : undefined;
    return (
      <div className="p-2 rounded-bp border border-bp-cyan/15 bg-bp-cyan-tint">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-[10px] font-mono text-bp-cyan">{String(item.fact_id || '')}</p>
            {item.source_title ? (
              <p className="text-[11px] text-bp-muted truncate">{String(item.source_title)}</p>
            ) : null}
            {item.content ? (
              <p className="text-xs text-bp-text mt-0.5 line-clamp-2">{String(item.content)}</p>
            ) : null}
          </div>
          {docId && onNavigateToLiterature && (
            <button
              type="button"
              onClick={() => onNavigateToLiterature(docId, chunkId)}
              className="shrink-0 flex items-center gap-0.5 text-[10px] text-bp-cyan hover:text-bp-cyan"
            >
              <ExternalLink className="w-3 h-3" />
              文献
            </button>
          )}
        </div>
      </div>
    );
  }

  if (step === 'multimodal') {
    return (
      <div className="p-2 rounded border border-purple-500/15 bg-purple-500/5">
        <p className="text-[10px] font-mono text-purple-300">{String(item.evidence_id || item.asset_id || '')}</p>
        {item.content ? <p className="text-xs text-bp-text mt-0.5 line-clamp-2">{String(item.content)}</p> : null}
      </div>
    );
  }

  if (step === 'dataset') {
    return (
      <div className="p-2 rounded border border-green-500/15 bg-green-500/5">
        <p className="text-[10px] font-mono text-green-300">{String(item.ref || item.data_citation_id || '')}</p>
        {item.table_row_id ? (
          <p className="text-[10px] text-bp-muted mt-0.5">行 ID: {String(item.table_row_id)}</p>
        ) : null}
        {item.source_title ? (
          <p className="text-[11px] text-bp-muted truncate">{String(item.source_title)}</p>
        ) : null}
      </div>
    );
  }

  if (step === 'verifiable_spec') {
    return (
      <div className="p-2 rounded border border-emerald-500/15 bg-emerald-500/5">
        {item.claim ? <p className="text-xs text-bp-text">{String(item.claim)}</p> : null}
        {item.primary_metric ? (
          <p className="text-[10px] font-mono text-emerald-300 mt-1">指标: {String(item.primary_metric)}</p>
        ) : null}
      </div>
    );
  }

  return null;
}
