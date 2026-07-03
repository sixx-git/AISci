import { RefreshCw, BookOpen, TrendingUp, CheckCircle2, AlertCircle, FlaskConical, Shield } from 'lucide-react';
import type { DiscoveryLoopData, TeachingAutoRefinementData, QualityAcceptance } from '@/types';
import { VersionComparePanel } from '@/components/VersionComparePanel';
import { EvidenceDiffPanel } from '@/components/EvidenceDiffPanel';

interface DiscoveryLoopPanelProps {
  discoveryLoop?: DiscoveryLoopData | null;
  teachingRefinement?: TeachingAutoRefinementData | null;
  qualityAcceptance?: QualityAcceptance | null;
  /** 仅渲染指定区块；默认全部 */
  sections?: ('quality' | 'teaching' | 'discovery' | 'versions')[];
}

function includesSection(sections: DiscoveryLoopPanelProps['sections'], key: NonNullable<DiscoveryLoopPanelProps['sections']>[number]) {
  return !sections || sections.length === 0 || sections.includes(key);
}

/** 闭环质量验收 — 对齐 spec QualityAcceptancePanel */
export function QualityAcceptanceSection({ qualityAcceptance }: { qualityAcceptance: QualityAcceptance }) {
  return (
    <div className="p-4 rounded-bp border border-bp-border bg-bp-panel/30">
      <h2 className="text-sm font-semibold text-bp-text mb-2 flex items-center gap-2">
        {qualityAcceptance.verdict === 'pass' ? (
          <CheckCircle2 className="w-4 h-4 text-bp-green" />
        ) : (
          <AlertCircle className="w-4 h-4 text-bp-yellow" />
        )}
        闭环质量验收
      </h2>
      <p className="text-xs text-bp-muted mb-2">{qualityAcceptance.summary}</p>
      <div className="flex flex-wrap gap-3 text-xs">
        <Stat label="Accept" value={qualityAcceptance.accepted ? '是' : '否'} />
        <Stat
          label="CQS 趋势"
          value={
            qualityAcceptance.cqs_delta != null
              ? `${qualityAcceptance.cqs_improved ? '↑' : '→/↓'} ${qualityAcceptance.cqs_delta >= 0 ? '+' : ''}${qualityAcceptance.cqs_delta.toFixed(1)}`
              : qualityAcceptance.score_delta != null
                ? `${qualityAcceptance.score_improved ? '↑' : '→/↓'} ${qualityAcceptance.score_delta >= 0 ? '+' : ''}${qualityAcceptance.score_delta.toFixed(1)}`
                : '—'
          }
        />
        <Stat label="Discovery 轮次" value={String(qualityAcceptance.discovery_rounds ?? '—')} />
        <Stat label="文献刷新" value={String(qualityAcceptance.literature_refresh_count ?? 0)} />
        {qualityAcceptance.federated_discovery_accept != null && (
          <Stat
            label="联邦双门槛"
            value={qualityAcceptance.federated_discovery_accept ? '通过' : '未通过'}
          />
        )}
        {qualityAcceptance.weak_stages && qualityAcceptance.weak_stages.length > 0 && (
          <Stat label="薄弱阶段" value={qualityAcceptance.weak_stages.join(', ')} />
        )}
      </div>
    </div>
  );
}

/** Teaching 自动精化 — 对齐 spec TeachingAutoRefinement */
export function TeachingAutoRefinementSection({ teachingRefinement }: { teachingRefinement: TeachingAutoRefinementData }) {
  if (!teachingRefinement.reran) return null;
  return (
    <div className="p-4 rounded-bp border border-bp-cyan/20 bg-bp-cyan/5">
      <h3 className="text-sm font-semibold text-bp-cyan mb-2 flex items-center gap-2">
        <RefreshCw className="w-4 h-4" />
        Teaching 自动闭环 · 第 {teachingRefinement.round} 轮
      </h3>
      <ul className="text-xs text-bp-muted list-disc list-inside">
        {(teachingRefinement.reasons || []).map((r) => (
          <li key={r}>{r}</li>
        ))}
      </ul>
    </div>
  );
}

/** Discovery 迭代历史 */
export function DiscoveryHistorySection({ discoveryLoop }: { discoveryLoop: DiscoveryLoopData }) {
  const history = discoveryLoop.history ?? [];
  if (history.length === 0) return null;

  return (
    <div className="p-4 rounded-bp border border-bp-border bg-bp-panel/30">
      <h2 className="text-sm font-semibold text-bp-text mb-3 flex items-center gap-2">
        <TrendingUp className="w-4 h-4 text-bp-cyan" />
        Discovery 迭代历史 · {discoveryLoop.rounds_executed ?? history.length + 1} 轮
      </h2>

      <div className="space-y-2">
        {history.map((entry) => {
          const rollback = entry.rollback as Record<string, unknown> | undefined;
          const litRefresh = rollback?.literature_refresh as Record<string, unknown> | undefined;
          const fedAccept = entry.federated_acceptance;
          const fedCampaign = entry.federated_campaign;
          return (
            <div
              key={`discovery-r${entry.round}`}
              className="p-3 rounded-bp border border-bp-border/80 bg-bp-base/40 text-xs"
            >
              <div className="flex flex-wrap items-center gap-2 mb-1.5">
                <span className="font-medium text-bp-text">R{entry.round}</span>
                <span className="text-bp-muted">{entry.status}</span>
                {entry.overall != null && (
                  <span className="font-mono text-bp-yellow">{Number(entry.overall).toFixed(1)}</span>
                )}
                {entry.decision && (
                  <span className="text-bp-muted">· {entry.decision}</span>
                )}
                {fedAccept && (
                  <span
                    className={`flex items-center gap-1 px-1.5 py-0.5 rounded-bp ${
                      fedAccept.accepted
                        ? 'bg-bp-green/10 text-bp-green'
                        : 'bg-bp-yellow/10 text-bp-yellow'
                    }`}
                  >
                    {fedAccept.accepted ? (
                      <CheckCircle2 className="w-3 h-3" />
                    ) : (
                      <Shield className="w-3 h-3" />
                    )}
                    联邦{fedAccept.accepted ? 'Accept' : '待改进'}
                  </span>
                )}
              </div>

              {fedAccept && !fedAccept.accepted && (fedAccept.blockers || []).length > 0 && (
                <ul className="text-xs text-bp-yellow/90 list-disc list-inside mb-1">
                  {(fedAccept.blockers || []).slice(0, 3).map((b) => (
                    <li key={b}>{b}</li>
                  ))}
                </ul>
              )}

              {fedCampaign && (
                <p className="text-xs text-bp-purple/90 flex items-center gap-1 mb-1">
                  <FlaskConical className="w-3 h-3" />
                  Campaign R{fedCampaign.round ?? '—'}
                  {fedCampaign.reran ? ' · 已自动 R2' : ''}
                  {fedCampaign.improved ? ' · 指标改善' : ''}
                  {fedCampaign.pilot_before_mode && fedCampaign.pilot_after_mode
                    ? ` · ${fedCampaign.pilot_before_mode}→${fedCampaign.pilot_after_mode}`
                    : ''}
                </p>
              )}

              {litRefresh && (
                <p className="text-xs text-bp-muted flex items-center gap-1 mb-1">
                  <BookOpen className="w-3 h-3" />
                  文献刷新 new_facts={String(litRefresh.new_facts ?? '—')}
                  {litRefresh.data_finder_rerun ? ' · Data Finder 已重跑' : ''}
                </p>
              )}

              {entry.driven_by && (
                <p className="text-xs text-bp-cyan/90 mb-1">
                  驱动: {entry.driven_by}
                </p>
              )}
              {(entry.data_changes || []).length > 0 && (
                <p className="text-xs text-bp-green/90 mb-1">
                  数据变更: {(entry.data_changes || []).join(' · ')}
                </p>
              )}
              {(entry.plan_changes || []).length > 0 && (
                <p className="text-xs text-bp-cyan/90 mb-1">
                  计划变更: {(entry.plan_changes || []).join(' · ')}
                </p>
              )}
              {entry.status === 'stagnant' && entry.stagnation && (
                <p className="text-xs text-bp-yellow mb-1">
                  CQS 停滞: {String((entry.stagnation as { reason?: string }).reason || '建议人工介入')}
                </p>
              )}

              {(entry.refinement_notes || []).slice(0, 2).map((note) => (
                <p key={note} className="text-xs text-bp-muted line-clamp-1">• {note}</p>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function DiscoveryLoopPanel({
  discoveryLoop,
  teachingRefinement,
  qualityAcceptance,
  sections,
}: DiscoveryLoopPanelProps) {
  const snapshots =
    discoveryLoop?.version_snapshots ??
    teachingRefinement?.version_snapshots ??
    [];

  const hasQuality = qualityAcceptance && includesSection(sections, 'quality');
  const hasTeaching = teachingRefinement?.reran && includesSection(sections, 'teaching');
  const hasDiscovery = discoveryLoop && (discoveryLoop.history?.length ?? 0) > 0 && includesSection(sections, 'discovery');
  const hasVersions = snapshots.length > 0 && includesSection(sections, 'versions');

  if (!hasQuality && !hasTeaching && !hasDiscovery && !hasVersions) return null;

  return (
    <div className="space-y-4">
      {hasQuality && qualityAcceptance && (
        <QualityAcceptanceSection qualityAcceptance={qualityAcceptance} />
      )}
      {hasTeaching && teachingRefinement && (
        <TeachingAutoRefinementSection teachingRefinement={teachingRefinement} />
      )}
      {hasDiscovery && discoveryLoop && (
        <DiscoveryHistorySection discoveryLoop={discoveryLoop} />
      )}
      {hasVersions && (
        <>
          <VersionComparePanel snapshots={snapshots} />
          <EvidenceDiffPanel snapshots={snapshots} />
        </>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <span className="px-2 py-1 rounded-bp bg-bp-base border border-bp-border text-bp-muted">
      {label}: <span className="text-bp-text">{value}</span>
    </span>
  );
}
