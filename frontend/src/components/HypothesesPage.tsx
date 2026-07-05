import { useState, useCallback, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Lightbulb, AlertTriangle,
  GitBranch, ChevronDown, ChevronUp,
  Star, Database, Target, ShieldAlert, FileText, BookOpen,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { EmptyState } from '@/components/EmptyState';
import { LoadingState } from '@/components/workspace/LoadingState';
import { ErrorState } from '@/components/workspace/ErrorState';
import { HypothesisCard } from '@/components/HypothesisCard';
import { EvidenceChainDrawer } from '@/components/EvidenceChainDrawer';
import hypothesisService from '@/services/hypothesisService';
import scienceIterationService from '@/services/scienceIterationService';
import { pipelineService } from '@/services/pipelineService';
import { HypothesisTreePanel } from '@/components/HypothesisTreePanel';
import { useToast } from '@/hooks/useToast';
import { getErrorMessage } from '@/lib/errors';
import { mapBackendEvidenceToItem, mapBackendHypothesisToDetailed } from '@/lib/mappers/hypothesisMapper';
import { navigateToProjectTab } from '@/lib/projectNavigation';
import { selectedHypothesisKey } from '@/lib/storageKeys';
import type { DetailedHypothesis, EvidenceChain, EvidenceItem, HypothesisProvenance, HypothesisTreeData } from '@/types';

interface HypothesesPageProps {
  projectId?: string;
  compact?: boolean;
  revalidateKey?: number;
  latestRunId?: string | null;
}

const SCORING_DIMS = [
  { label: '对齐度', desc: '假设与研究问题的语义相关程度；分数越高越贴合研究方向。', icon: '🎯' },
  { label: '证据等级', desc: 'high 有充足文献/数据支撑, medium 有部分支撑, low 支持不足。', icon: '📚' },
  { label: '可验证性', desc: '假设是否可以通过实验或观测进行检验，验证条件是否明确可操作。', icon: '✅' },
  { label: '偏题标记', desc: '当 alignment_score < 40 或存在领域冲突关键词时标记为偏题。', icon: '⚠️' },
] as const;

function applyEvidenceChainToHypothesis(h: DetailedHypothesis, chain: EvidenceChain | null): DetailedHypothesis {
  if (!chain) return h;
  return {
    ...h,
    evidenceChain: chain,
    chainCompleteness: chain.chain_completeness,
    supportEvidenceCount: chain.support_count ?? chain.supporting_evidence?.length ?? 0,
    counterEvidenceCount: chain.counter_count ?? chain.counter_evidence?.length ?? 0,
    citationReliability: chain.citation_reliability,
    content: chain.final_version || h.content,
  };
}

export function HypothesesPage({
  projectId: _projectId,
  revalidateKey: _revalidateKey,
  latestRunId: _latestRunId,
}: HypothesesPageProps) {
  const navigate = useNavigate();
  const { message: alertMsg, showAlert } = useToast();

  const [hypotheses, setHypotheses] = useState<DetailedHypothesis[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offTopicExpanded, setOffTopicExpanded] = useState(false);
  const [scoringExpanded, setScoringExpanded] = useState(false);

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedHypothesis, setSelectedHypothesis] = useState<DetailedHypothesis | null>(null);
  const [currentEvidence, setCurrentEvidence] = useState<EvidenceItem[]>([]);
  const [currentEvidenceChain, setCurrentEvidenceChain] = useState<EvidenceChain | null>(null);
  const [provenance, setProvenance] = useState<HypothesisProvenance | null>(null);
  const [provenanceLoading, setProvenanceLoading] = useState(false);
  const [iteratingId, setIteratingId] = useState<string | null>(null);
  const [hypothesisTree, setHypothesisTree] = useState<HypothesisTreeData | null>(null);
  const [retryTick, setRetryTick] = useState(0);

  useEffect(() => {
    if (!_projectId) {
      setLoading(false);
      setError('未提供项目 ID');
      return;
    }

    setLoading(true);
    setError(null);

    hypothesisService.getProjectHypotheses(_projectId)
      .then(async (res) => {
        if (res.code === 200 && Array.isArray(res.data)) {
          const base = res.data.map(mapBackendHypothesisToDetailed);
          const withChains = await Promise.all(
            base.map(async (h) => {
              try {
                const chainRes = await hypothesisService.getEvidenceChain(h.id);
                if (chainRes.code === 200 && chainRes.data) {
                  return applyEvidenceChainToHypothesis(h, chainRes.data);
                }
              } catch {
                /* ignore per-hypothesis chain load errors */
              }
              return h;
            }),
          );
          setHypotheses(withChains);
        } else {
          setError(res.message || '获取假设列表失败');
        }
      })
      .catch((err) => {
        setError(getErrorMessage(err, '获取假设列表失败，请检查后端服务是否启动'));
      })
      .finally(() => setLoading(false));
  }, [_projectId, _revalidateKey, _latestRunId, retryTick]);

  useEffect(() => {
    if (!_projectId) {
      setHypothesisTree(null);
      return;
    }

    const loadTree = async () => {
      try {
        let runId = _latestRunId;
        if (!runId) {
          const runsRes = await pipelineService.getRuns(_projectId);
          if (runsRes.code === 200 && runsRes.data?.length) {
            runId = runsRes.data[0].run_id;
          }
        }
        if (!runId) {
          setHypothesisTree(null);
          return;
        }
        const detailRes = await pipelineService.getRunDetail(runId);
        if (detailRes.code !== 200 || !detailRes.data?.stages) {
          setHypothesisTree(null);
          return;
        }
        const hgStage = detailRes.data.stages.find(
          (s) => String(s.stage).includes('hypothesis_generation'),
        );
        const out = hgStage?.output_data as Record<string, unknown> | undefined;
        const tree = out?.hypothesis_tree as HypothesisTreeData | undefined;
        setHypothesisTree(tree?.branches?.length ? tree : null);
      } catch {
        setHypothesisTree(null);
      }
    };

    loadTree();
  }, [_projectId, _latestRunId, _revalidateKey]);

  const handleViewEvidence = useCallback((id: string) => {
    const hypo = hypotheses.find(h => h.id === id);
    if (!hypo) return;
    setSelectedHypothesis(hypo);
    setCurrentEvidenceChain(hypo.evidenceChain ?? null);
    setProvenance(null);
    setProvenanceLoading(Boolean(_projectId));
    setDrawerOpen(true);

    Promise.all([
      hypothesisService.getHypothesisEvidence(id),
      hypothesisService.getEvidenceChain(id),
      _projectId
        ? scienceIterationService.getHypothesisProvenance(_projectId, id, _latestRunId)
        : Promise.resolve({ code: 200, data: null, message: 'ok' }),
    ])
      .then(([evRes, chainRes, provRes]) => {
        if (evRes.code === 200 && Array.isArray(evRes.data)) {
          setCurrentEvidence(evRes.data.map(mapBackendEvidenceToItem));
        } else {
          setCurrentEvidence([]);
        }
        if (chainRes.code === 200 && chainRes.data) {
          setCurrentEvidenceChain(chainRes.data);
          setSelectedHypothesis((prev) =>
            prev && prev.id === id ? applyEvidenceChainToHypothesis(prev, chainRes.data) : prev,
          );
        } else {
          setCurrentEvidenceChain(hypo.evidenceChain ?? null);
        }
        if (provRes.code === 200 && provRes.data) {
          setProvenance(provRes.data);
        }
      })
      .catch(() => {
        setCurrentEvidence([]);
        setCurrentEvidenceChain(hypo.evidenceChain ?? null);
      })
      .finally(() => setProvenanceLoading(false));
  }, [hypotheses, _projectId, _latestRunId]);

  const handleIterateEvidence = useCallback(async (id: string) => {
    setIteratingId(id);
    try {
      const res = await hypothesisService.iterateEvidenceChain(id);
      if (res.code === 200 && res.data?.evidence_chain) {
        const chain = res.data.evidence_chain as EvidenceChain;
        setHypotheses((prev) =>
          prev.map((h) => (h.id === id ? applyEvidenceChainToHypothesis(h, chain) : h)),
        );
        if (selectedHypothesis?.id === id) {
          setSelectedHypothesis((prev) =>
            prev ? applyEvidenceChainToHypothesis(prev, chain) : prev,
          );
          setCurrentEvidenceChain(chain);
        }
        showAlert('证据链迭代修正完成');
      } else {
        showAlert(res.message || '迭代修正失败');
      }
    } catch {
      showAlert('迭代修正失败，请检查后端服务');
    } finally {
      setIteratingId(null);
    }
  }, [selectedHypothesis, showAlert]);

  const handleCloseDrawer = useCallback(() => {
    setDrawerOpen(false);
    setSelectedHypothesis(null);
    setCurrentEvidence([]);
    setCurrentEvidenceChain(null);
    setProvenance(null);
    setProvenanceLoading(false);
  }, []);

  const offTopicHypotheses = useMemo(
    () => hypotheses.filter((h) => h.off_topic),
    [hypotheses],
  );

  const nonOffTopicHypotheses = useMemo(
    () => hypotheses.filter((h) => !h.off_topic),
    [hypotheses],
  );

  const handleSetPrimary = useCallback(async (id: string) => {
    if (!_projectId) return;
    try {
      const res = await hypothesisService.setPrimaryHypothesis(_projectId, id);
      if (res.code === 200) {
        const updated = await hypothesisService.getProjectHypotheses(_projectId);
        if (updated.code === 200 && Array.isArray(updated.data)) {
          setHypotheses(updated.data.map(mapBackendHypothesisToDetailed));
        } else {
          setHypotheses((prev) =>
            prev.map((h) => ({ ...h, isPrimary: h.id === id })),
          );
        }
        showAlert('已设为主假设');
      } else {
        showAlert(res.message || '设置主假设失败');
      }
    } catch (err: unknown) {
      console.error('设置主假设失败', err);
      showAlert('设置主假设失败');
    }
  }, [_projectId, showAlert]);

  const handleEnterExperiment = useCallback((id: string) => {
    if (!_projectId) return;
    localStorage.setItem(selectedHypothesisKey(_projectId), id);
    navigateToProjectTab(navigate, _projectId, 'experiments', { hypothesis_id: id });
  }, [_projectId, navigate]);

  const handleGoWorkflow = useCallback(() => {
    navigateToProjectTab(navigate, _projectId, 'workflow');
  }, [_projectId, navigate]);

  const handleGoDatasets = useCallback(() => {
    navigateToProjectTab(navigate, _projectId, 'datasets');
  }, [_projectId, navigate]);

  const handleGoLiterature = useCallback(() => {
    navigateToProjectTab(navigate, _projectId, 'literature');
  }, [_projectId, navigate]);

  const handleNavigateToLiterature = useCallback((documentId: string, chunkId?: string) => {
    navigateToProjectTab(navigate, _projectId, 'literature', {
      doc_id: documentId,
      chunk_id: chunkId,
    });
  }, [_projectId, navigate]);

  const primaryHypothesis = useMemo(
    () => hypotheses.find((h) => h.isPrimary),
    [hypotheses],
  );

  const withEvidenceCount = useMemo(
    () => hypotheses.filter((h) => h.evidenceCount > 0).length,
    [hypotheses],
  );

  const avgAlignment = useMemo(() => {
    if (hypotheses.length === 0) return 0;
    const scores = hypotheses.filter((h) => h.alignment_score != null).map((h) => h.alignment_score!);
    return scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : 0;
  }, [hypotheses]);

  const atRiskCount = useMemo(
    () => hypotheses.filter((h) => h.off_topic || h.evidenceLevel === 'low').length,
    [hypotheses],
  );

  const allOffTopic = useMemo(
    () => hypotheses.length > 0 && hypotheses.every((h) => h.off_topic),
    [hypotheses],
  );

  return (
    <div className="max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-bp-text mb-2">候选假设</h1>
          <p className="text-bp-muted">
            选择一个主假设作为研究方向，查看证据链，进入实验设计
          </p>
        </div>
        <Button
          variant="primary"
          size="sm"
          icon={<GitBranch className="w-4 h-4" />}
          onClick={handleGoWorkflow}
        >
          运行 Pipeline 生成假设
        </Button>
      </div>

      {alertMsg && (
        <div className="mb-4 px-4 py-2.5 rounded-lg bg-bp-cyan-tint border border-bp-cyan/20 text-sm text-bp-cyan animate-pulse">
          {alertMsg}
        </div>
      )}

      {/* ===== 加载中 / 错误 / 空状态 ===== */}

      {loading && (
        <Card>
          <LoadingState message="正在加载假设列表..." />
        </Card>
      )}

      {!loading && error && (
        <Card>
          <ErrorState
            title="加载假设失败"
            message={error}
            onRetry={() => setRetryTick((t) => t + 1)}
          />
        </Card>
      )}

      {!loading && !error && hypotheses.length === 0 && (
        <Card>
          <EmptyState
            icon={<Lightbulb className="w-8 h-8" />}
            title="暂无候选假设"
            description="请先完成工作流中的假设生成阶段"
            action={{ label: '前往工作流', onClick: handleGoWorkflow }}
          />
        </Card>
      )}

      {!loading && !error && hypotheses.length > 0 && (
        <>
          {allOffTopic && (
            <div className="mb-5 p-4 rounded-bp border border-danger-500/30 bg-danger-500/5">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-danger-400 shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-semibold text-danger-300 mb-2">
                    当前生成结果与研究问题关联不足
                  </p>
                  <p className="text-xs text-bp-muted mb-3">
                    所有 {hypotheses.length} 条假设均被标记为偏题（平均对齐分数 {avgAlignment}/100），
                    建议补充文献/数据后重新运行假设生成。
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <Button variant="secondary" size="sm" icon={<FileText className="w-3.5 h-3.5" />} onClick={handleGoDatasets}>
                      前往数据集
                    </Button>
                    <Button variant="secondary" size="sm" icon={<BookOpen className="w-3.5 h-3.5" />} onClick={handleGoLiterature}>
                      前往文献库
                    </Button>
                    <Button variant="secondary" size="sm" icon={<GitBranch className="w-3.5 h-3.5" />} onClick={handleGoWorkflow}>
                      重新运行工作流
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 xl:grid-cols-12 gap-4 items-start">
            {/* 左栏：假设树 + 决策指标 */}
            <aside className="xl:col-span-3 space-y-4 xl:sticky xl:top-4">
              {hypothesisTree && (
                <Card>
                  <HypothesisTreePanel tree={hypothesisTree} embedded />
                </Card>
              )}
              <Card title="假设决策" subtitle="五维概览">
                <div className="space-y-2">
                  <DecisionStat label="假设总数" value={hypotheses.length} icon={Lightbulb} color="text-bp-cyan" />
                  <DecisionStat label="当前主假设" value={primaryHypothesis ? 1 : 0} icon={Star} color="text-bp-yellow" />
                  <DecisionStat label="有证据支撑" value={withEvidenceCount} icon={Database} color="text-bp-cyan" />
                  <DecisionStat label="平均对齐分" value={`${avgAlignment}%`} icon={Target} color="text-bp-green" />
                  <DecisionStat label="偏题/低证据" value={atRiskCount} icon={ShieldAlert} color="text-danger-400" />
                </div>
              </Card>
            </aside>

            {/* 中栏：主假设 + 候选列表 */}
            <div className="xl:col-span-6 space-y-4 min-w-0">
              {primaryHypothesis && (
                <div>
                  <div className="text-xs text-bp-yellow/80 mb-1.5 flex items-center gap-1">
                    <Star className="w-3 h-3" /> 当前主假设 — 实验设计的入口
                  </div>
                  <HypothesisCard
                    hypothesis={primaryHypothesis}
                    onViewEvidence={handleViewEvidence}
                    onSetPrimary={handleSetPrimary}
                    onEnterExperiment={handleEnterExperiment}
                    onIterateEvidence={handleIterateEvidence}
                    onNavigateToLiterature={handleNavigateToLiterature}
                    iterating={iteratingId === primaryHypothesis.id}
                  />
                </div>
              )}

              {nonOffTopicHypotheses.length > 0 && (
                <div>
                  <div className="flex items-center justify-between mb-3 xl:hidden">
                    <h3 className="text-sm font-semibold text-bp-text">
                      候选假设 · {nonOffTopicHypotheses.length} 条
                    </h3>
                    <button
                      type="button"
                      onClick={() => setScoringExpanded(!scoringExpanded)}
                      className="flex items-center gap-1 text-xs text-bp-muted hover:text-bp-text transition-colors"
                    >
                      {scoringExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                      评分说明
                    </button>
                  </div>
                  <h3 className="text-sm font-semibold text-bp-text mb-3 hidden xl:block">
                    候选假设 · {nonOffTopicHypotheses.filter((h) => !h.isPrimary).length} 条
                  </h3>

                  {scoringExpanded && (
                    <div className="mb-4 p-4 rounded-bp border border-bp-border bg-bp-panel/30 animate-fade-in xl:hidden">
                      <ScoringGuide />
                    </div>
                  )}

                  <div className="space-y-3">
                    {nonOffTopicHypotheses
                      .filter((h) => !h.isPrimary)
                      .map((h) => (
                        <HypothesisCard
                          key={h.id}
                          hypothesis={h}
                          onViewEvidence={handleViewEvidence}
                          onSetPrimary={handleSetPrimary}
                          onEnterExperiment={handleEnterExperiment}
                          onIterateEvidence={handleIterateEvidence}
                          onNavigateToLiterature={handleNavigateToLiterature}
                          iterating={iteratingId === h.id}
                        />
                      ))}
                  </div>
                </div>
              )}

              {offTopicHypotheses.length > 0 && (
                <div>
                  <button
                    type="button"
                    onClick={() => setOffTopicExpanded(!offTopicExpanded)}
                    className="flex items-center gap-2 text-sm font-semibold text-bp-muted hover:text-bp-text transition-colors w-full text-left mb-2"
                  >
                    <ShieldAlert className="w-4 h-4 text-danger-400" />
                    低相关/偏题假设 · {offTopicHypotheses.length} 条
                    {offTopicExpanded
                      ? <ChevronUp className="w-4 h-4" />
                      : <ChevronDown className="w-4 h-4" />
                    }
                  </button>

                  {offTopicExpanded && (
                    <div className="space-y-3 animate-fade-in pl-4 border-l-2 border-danger-500/20">
                      {offTopicHypotheses.map((h) => (
                        <HypothesisCard
                          key={h.id}
                          hypothesis={h}
                          onViewEvidence={handleViewEvidence}
                          onEnterExperiment={undefined}
                          onIterateEvidence={handleIterateEvidence}
                          onNavigateToLiterature={handleNavigateToLiterature}
                          iterating={iteratingId === h.id}
                        />
                      ))}
                    </div>
                  )}
                </div>
              )}

              {nonOffTopicHypotheses.length === 0 && !primaryHypothesis && (
                <Card>
                  <EmptyState
                    icon={<AlertTriangle className="w-8 h-8 text-bp-yellow" />}
                    title="所有假设均被标记为偏题"
                    description="请补充文献/数据后重新运行假设生成"
                    action={{ label: '重新运行工作流', onClick: handleGoWorkflow }}
                  />
                </Card>
              )}
            </div>

            {/* 右栏：评分说明 + 快捷操作 */}
            <aside className="xl:col-span-3 space-y-4 xl:sticky xl:top-4 hidden xl:block">
              <Card title="评分说明" subtitle="五维解读">
                <ScoringGuide />
              </Card>
              <Card title="快捷操作">
                <div className="flex flex-col gap-2">
                  <Button variant="secondary" size="sm" icon={<GitBranch className="w-3.5 h-3.5" />} onClick={handleGoWorkflow}>
                    运行 Pipeline
                  </Button>
                  <Button variant="secondary" size="sm" icon={<BookOpen className="w-3.5 h-3.5" />} onClick={handleGoLiterature}>
                    文献库
                  </Button>
                  <Button variant="secondary" size="sm" icon={<FileText className="w-3.5 h-3.5" />} onClick={handleGoDatasets}>
                    数据集
                  </Button>
                </div>
              </Card>
            </aside>
          </div>
        </>
      )}

      {/* ===== 证据链抽屉 ===== */}
      <EvidenceChainDrawer
        open={drawerOpen}
        onClose={handleCloseDrawer}
        hypothesisTitle={selectedHypothesis?.title || ''}
        hypothesisContent={selectedHypothesis?.content || ''}
        evidenceCount={selectedHypothesis?.evidenceCount || 0}
        evidenceList={currentEvidence}
        evidenceChain={currentEvidenceChain}
        provenance={provenance}
        provenanceLoading={provenanceLoading}
      />
    </div>
  );
}

function ScoringGuide() {
  return (
    <div className="space-y-3">
      {SCORING_DIMS.map((dim) => (
        <div key={dim.label} className="flex items-start gap-2">
          <span className="text-sm shrink-0">{dim.icon}</span>
          <div>
            <p className="text-xs font-semibold text-bp-text mb-0.5">{dim.label}</p>
            <p className="text-xs text-bp-muted leading-relaxed">{dim.desc}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

function DecisionStat({ label, value, icon: Icon, color }: {
  label: string;
  value: number | string;
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
  color: string;
}) {
  return (
    <div className="p-2.5 rounded-bp border border-bp-border bg-bp-base/50">
      <div className="flex items-center gap-2 mb-1.5">
        <Icon className={color} style={{ width: 15, height: 15 }} />
        <span className="text-xs text-bp-muted">{label}</span>
      </div>
      <span className="text-xl font-bold font-mono text-bp-text">{value}</span>
    </div>
  );
}