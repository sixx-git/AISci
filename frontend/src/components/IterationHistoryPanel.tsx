import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { History, GitBranch, TrendingUp, Layers, Network } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ClosedLoopTimeline } from '@/components/ClosedLoopTimeline';
import { LoopDependencyGraph } from '@/components/LoopDependencyGraph';
import { IterationRoundPanel } from '@/components/IterationRoundPanel';
import { EvidenceDiffPanel } from '@/components/EvidenceDiffPanel';
import { VersionComparePanel } from '@/components/VersionComparePanel';
import { FederatedCampaignPanel } from '@/components/FederatedCampaignPanel';
import {
  DiscoveryHistorySection,
  QualityAcceptanceSection,
  TeachingAutoRefinementSection,
} from '@/components/DiscoveryLoopPanel';
import scienceIterationService from '@/services/scienceIterationService';
import type {
  ClosedLoopDecision,
  ClosedLoopEvent,
  DiscoveryLoopData,
  IterationSnapshot,
  PipelineRunExtraMetadata,
  QualityAcceptance,
  QualityTrendEntry,
  ScienceIterationSession,
  TeachingAutoRefinementData,
} from '@/types';

type HistoryTab = 'milestones' | 'timeline' | 'versions' | 'topology';

export interface IterationHistoryPanelProps {
  runId?: string | null;
  extraMetadata?: PipelineRunExtraMetadata | null;
  federatedPilot?: Record<string, unknown> | null;
  className?: string;
}

const ITERATION_MODE_LABEL: Record<string, string> = {
  human: '人工主导',
  teaching_auto: '轻量自动',
  discovery_auto: 'Discovery 自动',
};

function SectionTitle({ icon: Icon, children }: { icon: typeof History; children: ReactNode }) {
  return (
    <h3 className="text-sm font-semibold text-bp-text flex items-center gap-2 mb-3">
      <Icon className="w-4 h-4 text-bp-cyan" />
      {children}
    </h3>
  );
}

export function IterationHistoryPanel({
  runId,
  extraMetadata,
  federatedPilot,
  className,
}: IterationHistoryPanelProps) {
  const [activeTab, setActiveTab] = useState<HistoryTab>('milestones');
  const [iterationSession, setIterationSession] = useState<ScienceIterationSession | null>(null);
  const [iterationLoading, setIterationLoading] = useState(false);
  const [iterationError, setIterationError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) {
      setIterationSession(null);
      return;
    }
    let cancelled = false;
    setIterationLoading(true);
    setIterationError(null);
    scienceIterationService.getIterationSession(runId)
      .then((res) => {
        if (cancelled) return;
        setIterationSession(res.code === 200 && res.data ? res.data : null);
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setIterationError(e instanceof Error ? e.message : '加载迭代会话失败');
          setIterationSession(null);
        }
      })
      .finally(() => {
        if (!cancelled) setIterationLoading(false);
      });
    return () => { cancelled = true; };
  }, [runId]);

  const iterationMode =
    (extraMetadata?.run_options?.iteration_mode as string | undefined)
    || (extraMetadata?.iteration_mode as string | undefined)
    || 'human';

  const discoveryLoopData = useMemo((): DiscoveryLoopData | null => {
    const aux = extraMetadata?.auxiliary_results?.discovery_loop as DiscoveryLoopData | undefined;
    return aux?.history?.length || aux?.version_snapshots?.length ? aux : null;
  }, [extraMetadata]);

  const teachingRefinementData = useMemo((): TeachingAutoRefinementData | null => {
    const aux = extraMetadata?.auxiliary_results?.teaching_auto_refinement as TeachingAutoRefinementData | undefined;
    return aux?.reran ? aux : null;
  }, [extraMetadata]);

  const qualityAcceptance = useMemo((): QualityAcceptance | null => {
    return extraMetadata?.quality_acceptance ?? null;
  }, [extraMetadata]);

  const versionSnapshots = useMemo((): IterationSnapshot[] => {
    const fromSession = iterationSession?.version_snapshots;
    if (fromSession && fromSession.length >= 2) return fromSession;
    const fromExtra = extraMetadata?.version_snapshots ?? [];
    const fromDiscovery = discoveryLoopData?.version_snapshots ?? [];
    const fromTeaching = teachingRefinementData?.version_snapshots ?? [];
    const merged = [...fromExtra, ...fromDiscovery, ...fromTeaching];
    if (merged.length >= 2) return merged;
    return fromExtra.length ? fromExtra : merged;
  }, [extraMetadata, iterationSession, discoveryLoopData, teachingRefinementData]);

  const events = extraMetadata?.closed_loop_events as ClosedLoopEvent[] | undefined;
  const decisions = extraMetadata?.closed_loop_decisions as ClosedLoopDecision[] | undefined;
  const qualityTrend = extraMetadata?.quality_trend as QualityTrendEntry[] | undefined;

  const hasMilestones =
    Boolean(iterationSession?.rounds?.length)
    || Boolean(qualityAcceptance)
    || Boolean(teachingRefinementData?.reran)
    || Boolean(discoveryLoopData?.history?.length);

  const hasTimeline =
    Boolean(events?.length)
    || Boolean(qualityTrend?.length)
    || Boolean(decisions?.length);

  const hasVersions = versionSnapshots.length >= 2;

  const hasTopology = hasTimeline;

  const federatedCampaignRefinement = useMemo(() => {
    const fromAux = extraMetadata?.auxiliary_results?.federated_campaign_refinement as Record<string, unknown> | undefined;
    if (fromAux && Object.keys(fromAux).length > 0) return fromAux;
    const fromHistory = discoveryLoopData?.history?.find((h) => h.federated_campaign)?.federated_campaign;
    return fromHistory ?? null;
  }, [extraMetadata, discoveryLoopData]);

  const hasFederated =
    Boolean(federatedPilot && Object.keys(federatedPilot).length > 0)
    || Boolean(events?.some((e) => e.type === 'federated_campaign'))
    || Boolean(discoveryLoopData?.history?.some((h) => h.federated_campaign || h.federated_acceptance))
    || Boolean(federatedCampaignRefinement);

  const hasAnyData = hasMilestones || hasTimeline || hasVersions || hasTopology || hasFederated;

  const tabs: Array<{ id: HistoryTab; label: string; icon: typeof History; show: boolean }> = [
    { id: 'milestones', label: '里程碑', icon: Layers, show: true },
    { id: 'timeline', label: '时间线', icon: TrendingUp, show: hasTimeline },
    { id: 'versions', label: '版本对比', icon: GitBranch, show: hasVersions },
    { id: 'topology', label: '拓扑', icon: Network, show: hasTopology || hasFederated },
  ];

  const visibleTabs = tabs.filter((t) => t.show);

  useEffect(() => {
    if (!visibleTabs.some((t) => t.id === activeTab)) {
      setActiveTab(visibleTabs[0]?.id ?? 'milestones');
    }
  }, [activeTab, visibleTabs]);

  if (!hasAnyData && !iterationLoading && !iterationError) {
    return (
      <div className={cn('p-6 rounded-bp border border-dashed border-bp-border text-center', className)}>
        <History className="w-8 h-8 text-bp-muted mx-auto mb-2" />
        <p className="text-sm text-bp-muted">
          暂无迭代历史。运行 Pipeline 后将记录假设、评审、验证与各轮精化里程碑。
        </p>
        <p className="text-xs text-bp-muted mt-2">
          当前模式：{ITERATION_MODE_LABEL[iterationMode] || iterationMode}
        </p>
      </div>
    );
  }

  return (
    <div className={cn('rounded-bp border border-bp-border bg-bp-panel/20', className)}>
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 pt-4 pb-2 border-b border-bp-border/60">
        <div className="flex items-center gap-2">
          <History className="w-4 h-4 text-bp-cyan" />
          <span className="text-sm font-semibold text-bp-text">迭代历史</span>
          <span className="text-xs px-2 py-0.5 rounded-bp border border-bp-cyan/30 bg-bp-cyan-tint text-bp-cyan">
            {ITERATION_MODE_LABEL[iterationMode] || iterationMode}
          </span>
        </div>
        <div className="flex rounded-bp border border-bp-border overflow-hidden text-xs">
          {visibleTabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'inline-flex items-center gap-1 px-2.5 py-1.5 transition-colors',
                activeTab === tab.id
                  ? 'bg-bp-cyan-tint text-bp-cyan'
                  : 'text-bp-muted hover:text-bp-text',
                tab.id !== visibleTabs[0].id && 'border-l border-bp-border',
              )}
            >
              <tab.icon className="w-3.5 h-3.5" />
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="p-4 space-y-4">
        {activeTab === 'milestones' && (
          <>
            <IterationRoundPanel
              session={iterationSession}
              loading={iterationLoading}
              error={iterationError}
            />
            {qualityAcceptance && (
              <div>
                <SectionTitle icon={Layers}>质量验收</SectionTitle>
                <QualityAcceptanceSection qualityAcceptance={qualityAcceptance} />
              </div>
            )}
            {teachingRefinementData?.reran && (
              <div>
                <SectionTitle icon={Layers}>轻量自动精化</SectionTitle>
                <TeachingAutoRefinementSection teachingRefinement={teachingRefinementData} />
              </div>
            )}
            {discoveryLoopData && (discoveryLoopData.history?.length ?? 0) > 0 && (
              <div>
                <SectionTitle icon={Layers}>Discovery 多轮</SectionTitle>
                <DiscoveryHistorySection discoveryLoop={discoveryLoopData} />
              </div>
            )}
          </>
        )}

        {activeTab === 'timeline' && hasTimeline && (
          <ClosedLoopTimeline
            embedded
            events={events}
            qualityTrend={qualityTrend}
            decisions={decisions}
            runId={runId}
          />
        )}

        {activeTab === 'versions' && hasVersions && (
          <div className="space-y-4">
            <VersionComparePanel snapshots={versionSnapshots} />
            <EvidenceDiffPanel snapshots={versionSnapshots} />
          </div>
        )}

        {activeTab === 'topology' && (
          <div className="space-y-4">
            {hasTimeline && (
              <div>
                <SectionTitle icon={Network}>跨环依赖拓扑</SectionTitle>
                <LoopDependencyGraph events={events} decisions={decisions} />
              </div>
            )}
            {hasFederated && (
              <div>
                <SectionTitle icon={Network}>联邦 Campaign</SectionTitle>
                <FederatedCampaignPanel
                  federatedPilot={federatedPilot}
                  events={events}
                  snapshots={versionSnapshots}
                  campaignRefinement={federatedCampaignRefinement}
                />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
