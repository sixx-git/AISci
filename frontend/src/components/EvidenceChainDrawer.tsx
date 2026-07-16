import { useState } from 'react';
import {
  X, FileText, BookOpen, Hash, Link2, Gauge, ShieldAlert, CheckCircle2, History,
  Compass, FlaskConical, Database,
} from 'lucide-react';
import type { EvidenceChain, EvidenceItem as EvidenceItemType, HypothesisProvenance } from '@/types';

interface EvidenceChainDrawerProps {
  open: boolean;
  onClose: () => void;
  hypothesisTitle: string;
  hypothesisContent?: string;
  evidenceCount: number;
  evidenceList: EvidenceItemType[];
  evidenceChain?: EvidenceChain | null;
  provenance?: HypothesisProvenance | null;
  provenanceLoading?: boolean;
}

type DrawerTab = 'evidence' | 'origin' | 'verification';

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
                <p className="text-xs text-bp-muted italic mb-2">&quot;{ev.quote_or_summary}&quot;</p>
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

function OriginTab({ provenance, loading }: { provenance?: HypothesisProvenance | null; loading?: boolean }) {
  if (loading) {
    return <p className="text-sm text-bp-muted py-8 text-center">加载假设溯源...</p>;
  }
  if (!provenance) {
    return (
      <p className="text-sm text-bp-muted py-8 text-center">
        暂无溯源数据。请先运行 Pipeline 或检查后端 science-iteration API。
      </p>
    );
  }

  const origin = provenance.origin || {};
  const grounding = provenance.grounding || {};

  return (
    <div className="space-y-6">
      <section>
        <h4 className="text-sm font-semibold text-bp-text mb-2 flex items-center gap-1.5">
          <Compass className="w-4 h-4 text-bp-cyan" />
          科学逻辑来源
        </h4>
        <div className="space-y-2 text-sm text-bp-text">
          {origin.main_contradiction && (
            <div className="p-3 rounded-bp border border-bp-border bg-bp-panel/40">
              <p className="text-xs text-bp-muted mb-1">主要矛盾</p>
              <p>{origin.main_contradiction}</p>
            </div>
          )}
          {origin.problem_statement && (
            <div className="p-3 rounded-bp border border-bp-border bg-bp-panel/40">
              <p className="text-xs text-bp-muted mb-1">问题陈述</p>
              <p>{origin.problem_statement}</p>
            </div>
          )}
          {origin.reasoning_chain && origin.reasoning_chain.length > 0 && (
            <ul className="list-disc list-inside text-xs text-bp-muted space-y-1 pl-1">
              {origin.reasoning_chain.map((line, i) => (
                <li key={i}>{line}</li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <section>
        <h4 className="text-sm font-semibold text-bp-text mb-2 flex items-center gap-1.5">
          <BookOpen className="w-4 h-4" />
          文献依据 ({grounding.literature?.length || 0})
        </h4>
        {(grounding.literature?.length || 0) === 0 ? (
          <p className="text-xs text-bp-muted">尚未绑定 supporting_fact_ids</p>
        ) : (
          <div className="space-y-2">
            {grounding.literature?.map((lit) => (
              <div key={lit.fact_id} className="p-3 rounded-bp border border-bp-border bg-bp-panel-glass text-xs">
                <p className="text-bp-text mb-1">{lit.content || lit.quote_text}</p>
                {lit.source_title && <p className="text-bp-muted">{lit.source_title}</p>}
                {lit.fact_id && <p className="text-bp-muted font-mono mt-1">fact: {lit.fact_id}</p>}
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h4 className="text-sm font-semibold text-bp-text mb-2 flex items-center gap-1.5">
          <Database className="w-4 h-4" />
          数据依据 ({grounding.data?.length || 0})
        </h4>
        {(grounding.data?.length || 0) === 0 ? (
          <p className="text-xs text-bp-muted">暂无抽取表格/CSV 证据</p>
        ) : (
          <div className="space-y-2">
            {grounding.data?.slice(0, 8).map((d) => (
              <div key={d.table_id || d.source_title} className="p-2 rounded border border-bp-border text-xs text-bp-muted">
                <span className="text-bp-text">{d.source_title || d.table_id}</span>
                {d.row_count != null && <span className="ml-2">· {d.row_count} 行</span>}
                {d.extraction_method && <span className="ml-2">· {d.extraction_method}</span>}
              </div>
            ))}
          </div>
        )}
      </section>

      {(grounding.knowledge_gaps?.length || 0) > 0 && (
        <section>
          <h4 className="text-sm font-semibold text-bp-text mb-2">关联知识缺口</h4>
          <ul className="text-xs text-bp-muted space-y-1">
            {grounding.knowledge_gaps?.map((g, i) => (
              <li key={i} className="border-l-2 border-bp-yellow/40 pl-2">{g}</li>
            ))}
          </ul>
        </section>
      )}

      <div className="flex flex-wrap gap-2 text-xs">
        {provenance.evidence_sufficiency && (
          <span className="px-2 py-0.5 rounded border border-bp-border text-bp-muted">
            证据充分性: {provenance.evidence_sufficiency}
          </span>
        )}
        {provenance.evidence_level && (
          <span className="px-2 py-0.5 rounded border border-bp-border text-bp-muted">
            等级: {provenance.evidence_level}
          </span>
        )}
      </div>
    </div>
  );
}

function VerificationTab({ provenance, loading }: { provenance?: HypothesisProvenance | null; loading?: boolean }) {
  if (loading) {
    return <p className="text-sm text-bp-muted py-8 text-center">加载验证规格...</p>;
  }
  if (!provenance?.verification) {
    return <p className="text-sm text-bp-muted py-8 text-center">暂无 verifiable_spec / 迭代实验结果</p>;
  }

  const v = provenance.verification;
  const spec = v.verifiable_spec || {};
  const scores = provenance.scores || {};

  return (
    <div className="space-y-6">
      <section>
        <h4 className="text-sm font-semibold text-bp-text mb-2 flex items-center gap-1.5">
          <FlaskConical className="w-4 h-4 text-bp-purple" />
          可验证规格
        </h4>
        {!!spec.claim && (
          <p className="text-sm text-bp-text p-3 rounded-bp border border-bp-border bg-bp-panel/40 mb-2">
            {String(spec.claim)}
          </p>
        )}
        <div className="text-xs text-bp-muted space-y-1">
          {v.validation_target && <p>验证目标: {v.validation_target}</p>}
          {v.expected_measurable_effect && <p>预期效应: {v.expected_measurable_effect}</p>}
          {!!spec.primary_metric && (
            <p className="font-mono text-bp-green">主指标: {String(spec.primary_metric)}</p>
          )}
        </div>
      </section>

      {v.verification_checks && v.verification_checks.length > 0 && (
        <section>
          <h4 className="text-sm font-semibold text-bp-text mb-2">验证检查项</h4>
          <div className="space-y-2">
            {v.verification_checks.map((chk, i) => (
              <div key={i} className="p-2 rounded border border-bp-border text-xs flex items-start gap-2">
                {chk.passed === true && <CheckCircle2 className="w-3.5 h-3.5 text-bp-green shrink-0 mt-0.5" />}
                {chk.passed === false && <ShieldAlert className="w-3.5 h-3.5 text-danger-400 shrink-0 mt-0.5" />}
                <div>
                  <p className="text-bp-text">{String(chk.check || chk.name || `检查 ${i + 1}`)}</p>
                  {!!chk.detail && <p className="text-bp-muted mt-0.5">{String(chk.detail)}</p>}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="text-xs text-bp-muted">
        <p>
          沙箱验证:{' '}
          {v.sandbox_success === true && <span className="text-bp-green">成功</span>}
          {v.sandbox_success === false && <span className="text-danger-400">失败</span>}
          {v.sandbox_success == null && '—'}
        </p>
        {scores.ensemble_overall != null && (
          <p className="mt-1">评审分: {String(scores.ensemble_overall)}</p>
        )}
        {scores.logic_score != null && (
          <p className="mt-1">开题逻辑分: {String(scores.logic_score)}</p>
        )}
      </section>
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
  provenance,
  provenanceLoading,
}: EvidenceChainDrawerProps) {
  const [tab, setTab] = useState<DrawerTab>('evidence');

  if (!open) return null;

  const tabs: { key: DrawerTab; label: string }[] = [
    { key: 'evidence', label: '证据链' },
    { key: 'origin', label: '来源' },
    { key: 'verification', label: '验证' },
  ];

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
            <span className="truncate">证据链 · 溯源与验证</span>
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

        <div className="shrink-0 flex border-b border-bp-border px-4">
          {tabs.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              className={`px-4 py-2.5 text-xs font-medium border-b-2 transition-colors ${
                tab === t.key
                  ? 'border-bp-cyan text-bp-cyan'
                  : 'border-transparent text-bp-muted hover:text-bp-text'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          <div className="mb-6">
            <h2 className="text-xl font-bold text-bp-text mb-2 pr-8">{hypothesisTitle}</h2>
            {(evidenceChain?.final_version || hypothesisContent) && tab === 'evidence' && (
              <p className="text-sm text-bp-muted leading-relaxed">
                {evidenceChain?.final_version || hypothesisContent}
              </p>
            )}
            {tab === 'evidence' && (
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
            )}
          </div>

          {tab === 'origin' && (
            <OriginTab provenance={provenance} loading={provenanceLoading} />
          )}

          {tab === 'verification' && (
            <VerificationTab provenance={provenance} loading={provenanceLoading} />
          )}

          {tab === 'evidence' && (
            <>
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
                            <p className="text-xs text-bp-muted italic leading-relaxed">&quot;{ev.quote_text}&quot;</p>
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
            </>
          )}
        </div>
      </div>
    </div>
  );
}
