import { X, FileText, BookOpen, Hash, Link2, Gauge, ShieldAlert, CheckCircle2, History } from 'lucide-react';
import type { EvidenceChain, EvidenceItem as EvidenceItemType } from '@/types';

interface EvidenceChainDrawerProps {
  open: boolean;
  onClose: () => void;
  hypothesisTitle: string;
  hypothesisContent?: string;
  evidenceCount: number;
  evidenceList: EvidenceItemType[];
  evidenceChain?: EvidenceChain | null;
}

function StanceBadge({ stance }: { stance?: string }) {
  const cls =
    stance === 'support'
      ? 'bg-bp-green/15 text-bp-green border-bp-green/30'
      : stance === 'refute'
        ? 'bg-danger-500/15 text-danger-400 border-danger-500/30'
        : 'bg-bp-panel text-bp-muted border-bp-border';
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded-bp border ${cls}`}>
      {stance || 'neutral'}
    </span>
  );
}

function ChainEvidenceBlock({ title, items, emptyHint }: { title: string; items: EvidenceChain['supporting_evidence']; emptyHint?: string }) {
  return (
    <div>
      <h4 className="text-sm font-semibold text-bp-text mb-2">{title}</h4>
      {items.length === 0 ? (
        <p className="text-xs text-bp-muted">{emptyHint || '暂无条目'}</p>
      ) : (
        <div className="space-y-3">
          {items.map((ev) => (
            <div key={ev.evidence_id} className="p-3 rounded-bp border border-bp-border bg-bp-panel-glass">
              <div className="flex items-center justify-between mb-2">
                <StanceBadge stance={ev.stance} />
                <span className="text-xs font-mono text-bp-cyan">
                  {Math.round((ev.relevance_score || 0) * 100)}%
                </span>
              </div>
              <p className="text-sm text-bp-text mb-2">{ev.claim}</p>
              {ev.quote_or_summary && ev.quote_or_summary !== ev.claim && (
                <p className="text-xs text-bp-muted italic mb-2">"{ev.quote_or_summary}"</p>
              )}
              <div className="text-xs text-bp-muted flex flex-wrap gap-2">
                {ev.source_title && <span>{ev.source_title}</span>}
                {ev.reliability_score != null && (
                  <span>可信度 {(ev.reliability_score * 100).toFixed(0)}%</span>
                )}
              </div>
              {ev.stance_reason && (
                <p className="text-xs text-bp-muted mt-1">立场理由: {ev.stance_reason}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function EvidenceChainDrawer({
  open,
  onClose,
  hypothesisTitle,
  hypothesisContent,
  evidenceCount,
  evidenceList,
  evidenceChain,
}: EvidenceChainDrawerProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex" role="dialog" aria-modal="true" aria-label="证据链抽屉">
      <div
        className="fixed inset-0 bg-bp-base/80 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      <div className="relative ml-auto w-full max-w-2xl h-full bg-bp-base border-l border-bp-cyan-dim shadow-bp-glow-strong overflow-hidden flex flex-col animate-slide-in-right">
        <div className="shrink-0 flex items-center justify-between px-6 py-4 border-b border-bp-cyan-dim bg-bp-panel/50">
          <div className="flex items-center gap-2 text-xs text-bp-muted min-w-0">
            <Link2 className="w-3.5 h-3.5 shrink-0" />
            <span className="truncate">证据链 · 机制推理与迭代验证</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-bp hover:bg-bp-surface text-bp-muted hover:text-bp-text transition-colors shrink-0"
            aria-label="关闭"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          <div className="mb-6">
            <h2 className="text-xl font-bold text-bp-text mb-2 pr-8">{hypothesisTitle}</h2>
            {(evidenceChain?.final_version || hypothesisContent) && (
              <p className="text-sm text-bp-muted leading-relaxed">
                {evidenceChain?.final_version || hypothesisContent}
              </p>
            )}
            <div className="flex flex-wrap items-center gap-3 mt-3 text-xs text-bp-muted">
              <span className="flex items-center gap-1">
                <FileText className="w-3.5 h-3.5" />
                证据项 {evidenceCount}
              </span>
              {evidenceChain?.chain_completeness != null && (
                <span className="flex items-center gap-1 text-bp-cyan">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  完整度 {(evidenceChain.chain_completeness * 100).toFixed(0)}%
                </span>
              )}
              {evidenceChain?.citation_reliability != null && (
                <span className="flex items-center gap-1 text-bp-cyan">
                  <Gauge className="w-3.5 h-3.5" />
                  引用可信度 {(evidenceChain.citation_reliability * 100).toFixed(0)}%
                </span>
              )}
            </div>
          </div>

          {evidenceChain ? (
            <div className="space-y-6">
              <ChainEvidenceBlock
                title={`支持证据 (${evidenceChain.supporting_evidence?.length || 0})`}
                items={evidenceChain.supporting_evidence || []}
              />
              <ChainEvidenceBlock
                title={`反对/限制证据 (${evidenceChain.counter_evidence?.length || 0})`}
                items={evidenceChain.counter_evidence || []}
                emptyHint={evidenceChain.counter_evidence_empty_reason || '文献不足，未检索到可验证反例（未编造）'}
              />

              {evidenceChain.revision_history && evidenceChain.revision_history.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-bp-text mb-2 flex items-center gap-1.5">
                    <History className="w-4 h-4" />
                    修正历史
                  </h4>
                  <div className="space-y-2">
                    {evidenceChain.revision_history.map((rev, idx) => (
                      <div key={idx} className="p-3 rounded-bp border border-bp-border bg-bp-panel text-xs text-bp-text">
                        <div className="text-bp-muted mb-1">第 {rev.round || idx + 1} 轮</div>
                        <div>{rev.revision_reason}</div>
                        {rev.what_changed && rev.what_changed.length > 0 && (
                          <div className="text-bp-muted mt-1">变更: {rev.what_changed.join('；')}</div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              {evidenceList.length === 0 ? (
                <div className="text-center py-16 text-bp-muted">
                  <BookOpen className="w-12 h-12 mx-auto mb-4 opacity-20" />
                  <p className="text-sm text-bp-muted mb-2">当前假设尚无可追踪证据</p>
                  <p className="text-xs text-bp-muted">请补充文献或运行 Pipeline 建立证据链</p>
                </div>
              ) : (
                evidenceList.map((ev, idx) => (
                  <div key={ev.id || idx} className="p-4 rounded-bp border border-bp-border bg-bp-panel-glass">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-xs font-mono text-bp-muted">#{idx + 1}</span>
                      <div className="flex items-center gap-1.5">
                        {ev.stance && <StanceBadge stance={ev.stance} />}
                        <Gauge className="w-3.5 h-3.5 text-bp-cyan" />
                        <span className="text-xs font-mono text-bp-cyan">
                          {Math.round(ev.relevance_score * 100)}%
                        </span>
                      </div>
                    </div>
                    <p className="text-sm text-bp-text leading-relaxed mb-3">{ev.fact_text}</p>
                    {ev.quote_text && (
                      <div className="mb-3 p-3 rounded-bp bg-bp-panel/50 border border-bp-border/50">
                        <p className="text-xs text-bp-muted italic leading-relaxed">"{ev.quote_text}"</p>
                      </div>
                    )}
                    <div className="flex flex-wrap items-center gap-3 text-xs text-bp-muted">
                      {ev.source_title && (
                        <span className="flex items-center gap-1">
                          <FileText className="w-3 h-3" />
                          {ev.source_title}
                        </span>
                      )}
                      {ev.page_number != null && (
                        <span className="flex items-center gap-1">
                          <Hash className="w-3 h-3" />
                          第 {ev.page_number} 页
                        </span>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {evidenceChain?.counter_evidence_empty_reason && (
            <div className="mt-6 p-3 rounded-bp border border-bp-yellow/20 bg-bp-yellow/5 text-xs text-bp-yellow flex items-start gap-2">
              <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
              {evidenceChain.counter_evidence_empty_reason}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
