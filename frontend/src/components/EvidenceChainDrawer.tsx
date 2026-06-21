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
      ? 'bg-green-500/15 text-green-400 border-green-500/30'
      : stance === 'refute'
        ? 'bg-red-500/15 text-red-400 border-red-500/30'
        : 'bg-gray-500/15 text-gray-400 border-gray-500/30';
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded border ${cls}`}>
      {stance || 'neutral'}
    </span>
  );
}

function ChainEvidenceBlock({ title, items, emptyHint }: { title: string; items: EvidenceChain['supporting_evidence']; emptyHint?: string }) {
  return (
    <div>
      <h4 className="text-sm font-semibold text-white mb-2">{title}</h4>
      {items.length === 0 ? (
        <p className="text-xs text-gray-500">{emptyHint || '暂无条目'}</p>
      ) : (
        <div className="space-y-3">
          {items.map((ev) => (
            <div key={ev.evidence_id} className="p-3 rounded-lg border border-gray-800 bg-gray-850">
              <div className="flex items-center justify-between mb-2">
                <StanceBadge stance={ev.stance} />
                <span className="text-xs font-mono text-blue-400">
                  {Math.round((ev.relevance_score || 0) * 100)}%
                </span>
              </div>
              <p className="text-sm text-gray-200 mb-2">{ev.claim}</p>
              {ev.quote_or_summary && ev.quote_or_summary !== ev.claim && (
                <p className="text-xs text-gray-500 italic mb-2">"{ev.quote_or_summary}"</p>
              )}
              <div className="text-xs text-gray-500 flex flex-wrap gap-2">
                {ev.source_title && <span>{ev.source_title}</span>}
                {ev.reliability_score != null && (
                  <span>可信度 {(ev.reliability_score * 100).toFixed(0)}%</span>
                )}
              </div>
              {ev.stance_reason && (
                <p className="text-[11px] text-gray-600 mt-1">立场理由: {ev.stance_reason}</p>
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
    <div className="fixed inset-0 z-50 flex">
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      <div className="relative ml-auto w-full max-w-2xl h-full bg-gray-900 border-l border-gray-800 shadow-2xl overflow-y-auto animate-slide-in">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-lg hover:bg-gray-800 text-gray-400 hover:text-white transition-colors z-10"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="p-6">
          <div className="mb-6 pt-2">
            <div className="flex items-center gap-2 text-xs text-gray-500 mb-2">
              <Link2 className="w-3.5 h-3.5" />
              证据链 · 机制推理与迭代验证
            </div>
            <h2 className="text-xl font-bold text-white mb-2">{hypothesisTitle}</h2>
            {(evidenceChain?.final_version || hypothesisContent) && (
              <p className="text-sm text-gray-400 leading-relaxed">
                {evidenceChain?.final_version || hypothesisContent}
              </p>
            )}
            <div className="flex flex-wrap items-center gap-3 mt-3 text-xs text-gray-500">
              <span className="flex items-center gap-1">
                <FileText className="w-3.5 h-3.5" />
                证据项 {evidenceCount}
              </span>
              {evidenceChain?.chain_completeness != null && (
                <span className="flex items-center gap-1 text-primary-300">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  完整度 {(evidenceChain.chain_completeness * 100).toFixed(0)}%
                </span>
              )}
              {evidenceChain?.citation_reliability != null && (
                <span className="flex items-center gap-1 text-blue-300">
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
                  <h4 className="text-sm font-semibold text-white mb-2 flex items-center gap-1.5">
                    <History className="w-4 h-4" />
                    修正历史
                  </h4>
                  <div className="space-y-2">
                    {evidenceChain.revision_history.map((rev, idx) => (
                      <div key={idx} className="p-3 rounded-lg border border-gray-800 bg-gray-850 text-xs text-gray-300">
                        <div className="text-gray-500 mb-1">第 {rev.round || idx + 1} 轮</div>
                        <div>{rev.revision_reason}</div>
                        {rev.what_changed && rev.what_changed.length > 0 && (
                          <div className="text-gray-500 mt-1">变更: {rev.what_changed.join('；')}</div>
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
                <div className="text-center py-16 text-gray-500">
                  <BookOpen className="w-12 h-12 mx-auto mb-4 opacity-20" />
                  <p className="text-sm text-gray-400 mb-2">当前假设尚无可追踪证据</p>
                  <p className="text-xs text-gray-500">请补充文献或运行 Pipeline 建立证据链</p>
                </div>
              ) : (
                evidenceList.map((ev, idx) => (
                  <div key={ev.id || idx} className="p-4 rounded-lg border border-gray-800 bg-gray-850">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-xs font-mono text-gray-600">#{idx + 1}</span>
                      <div className="flex items-center gap-1.5">
                        {ev.stance && <StanceBadge stance={ev.stance} />}
                        <Gauge className="w-3.5 h-3.5 text-blue-400" />
                        <span className="text-xs font-mono text-blue-400">
                          {Math.round(ev.relevance_score * 100)}%
                        </span>
                      </div>
                    </div>
                    <p className="text-sm text-gray-200 leading-relaxed mb-3">{ev.fact_text}</p>
                    {ev.quote_text && (
                      <div className="mb-3 p-3 rounded bg-gray-800/50 border border-gray-700/50">
                        <p className="text-xs text-gray-400 italic leading-relaxed">"{ev.quote_text}"</p>
                      </div>
                    )}
                    <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500">
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
            <div className="mt-6 p-3 rounded-lg border border-amber-500/20 bg-amber-500/5 text-xs text-amber-300 flex items-start gap-2">
              <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
              {evidenceChain.counter_evidence_empty_reason}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
