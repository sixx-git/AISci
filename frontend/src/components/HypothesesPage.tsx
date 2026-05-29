import { useState, useCallback, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Lightbulb, Loader2, AlertCircle, AlertTriangle,
  GitBranch, ChevronDown, ChevronUp,
  Star, Database, Target, BarChart3, ShieldAlert,
} from 'lucide-react';
import { Button } from '@/components/Button';
import { HypothesisCard } from '@/components/HypothesisCard';
import { EvidenceChainDrawer } from '@/components/EvidenceChainDrawer';
import hypothesisService, { type BackendHypothesis, type BackendEvidence } from '@/services/hypothesisService';
import type { DetailedHypothesis, EvidenceItem } from '@/types';

interface HypothesesPageProps {
  projectId?: string;
  compact?: boolean;
  revalidateKey?: number;
  latestRunId?: string | null;
}

function mapBackendToDetailed(h: BackendHypothesis): DetailedHypothesis {
  return {
    id: h.id,
    title: h.hypothesis || '未命名假设',
    content: h.hypothesis || '',
    reasoning: h.rationale || '',
    evidenceCount: (h.supporting_fact_ids || []).length,
    novelty: 80,
    verifiability: h.testability === 'high' ? 88 : h.testability === 'low' ? 55 : 75,
    dataAvailability: h.required_data === 'high' ? 85 : h.required_data === 'low' ? 55 : 70,
    overallScore: Math.round((h.confidence || 0.5) * 100),
    riskWarning: h.risk || '',
    isPrimary: h.priority === 1,
    status: (h.status === 'testing' || h.status === 'accepted' || h.status === 'confirmed')
      ? 'confirmed' : 'draft',
    alignment_score: h.alignment_score ?? undefined,
    off_topic: h.off_topic ?? undefined,
    off_topic_reason: h.off_topic_reason ?? undefined,
    matched_keywords: h.matched_keywords ?? undefined,
    missing_keywords: h.missing_keywords ?? undefined,
    evidenceLevel: h.evidence_level || 'medium',
    question_alignment: h.question_alignment ?? undefined,
    dataset_field_refs: h.dataset_field_refs ?? undefined,
    data_evidence_ids: h.data_evidence_ids ?? undefined,
    validation_target: h.validation_target ?? undefined,
    expected_measurable_effect: h.expected_measurable_effect ?? undefined,
  };
}

function mapBackendEvidence(e: BackendEvidence): EvidenceItem {
  return {
    id: e.id,
    project_id: e.project_id,
    hypothesis_id: e.hypothesis_id,
    document_id: e.document_id,
    chunk_id: e.chunk_id,
    fact_text: e.fact_text,
    quote_text: e.quote_text,
    page_number: e.page_number,
    relevance_score: e.relevance_score,
    source_title: e.source_title,
    created_at: e.created_at,
  };
}

const STAT_CARDS = [
  { key: 'total', label: '假设总数', icon: Lightbulb, color: 'text-primary-400' },
  { key: 'primary', label: '主假设', icon: Star, color: 'text-amber-400' },
  { key: 'withEvidence', label: '有证据支撑', icon: Database, color: 'text-blue-400' },
  { key: 'avgVerifiability', label: '平均可验证性', icon: Target, color: 'text-green-400' },
  { key: 'atRisk', label: '偏题/低证据', icon: ShieldAlert, color: 'text-red-400' },
];

export function HypothesesPage({
  projectId: _projectId,
  compact: _compact = false,
  revalidateKey: _revalidateKey,
  latestRunId: _latestRunId,
}: HypothesesPageProps) {
  const navigate = useNavigate();
  const [hypotheses, setHypotheses] = useState<DetailedHypothesis[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [alertMsg, setAlertMsg] = useState<string | null>(null);
  const [hideOffTopic, setHideOffTopic] = useState(true);
  const [scoringExpanded, setScoringExpanded] = useState(false);

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedHypothesis, setSelectedHypothesis] = useState<DetailedHypothesis | null>(null);
  const [currentEvidence, setCurrentEvidence] = useState<EvidenceItem[]>([]);
  const [evidenceLoading, setEvidenceLoading] = useState(false);

  const showAlert = useCallback((msg: string) => {
    setAlertMsg(msg);
    setTimeout(() => setAlertMsg(null), 3000);
  }, []);

  useEffect(() => {
    if (!_projectId) {
      setLoading(false);
      setError('未提供项目 ID');
      return;
    }

    setLoading(true);
    setError(null);

    hypothesisService.getProjectHypotheses(_projectId)
      .then((res) => {
        if (res.code === 200 && Array.isArray(res.data)) {
          const mapped = res.data.map(mapBackendToDetailed);
          setHypotheses(mapped);
        } else {
          setError(res.message || '获取假设列表失败');
        }
      })
      .catch((err) => {
        setError(err?.message || '获取假设列表失败，请检查后端服务是否启动');
      })
      .finally(() => setLoading(false));
  }, [_projectId, _revalidateKey, _latestRunId]);

  const handleViewEvidence = useCallback((id: string) => {
    const hypo = hypotheses.find(h => h.id === id);
    if (!hypo) return;
    setSelectedHypothesis(hypo);

    setEvidenceLoading(true);
    setDrawerOpen(true);

    hypothesisService.getHypothesisEvidence(id)
      .then((res) => {
        if (res.code === 200 && Array.isArray(res.data)) {
          setCurrentEvidence(res.data.map(mapBackendEvidence));
        } else {
          setCurrentEvidence([]);
        }
      })
      .catch(() => setCurrentEvidence([]))
      .finally(() => setEvidenceLoading(false));
  }, [hypotheses]);

  const handleCloseDrawer = useCallback(() => {
    setDrawerOpen(false);
    setSelectedHypothesis(null);
    setCurrentEvidence([]);
    setEvidenceLoading(false);
  }, []);

  const offTopicCount = useMemo(
    () => hypotheses.filter((h) => h.off_topic).length,
    [hypotheses]
  );

  const displayedHypotheses = useMemo(
    () => hideOffTopic ? hypotheses.filter((h) => !h.off_topic) : hypotheses,
    [hypotheses, hideOffTopic]
  );

  const handleSetPrimary = useCallback(async (id: string) => {
    if (!_projectId) return;
    try {
      const res = await hypothesisService.setPrimaryHypothesis(_projectId, id);
      if (res.code === 200) {
        setHypotheses((prev) =>
          prev.map((h) => ({ ...h, isPrimary: h.id === id })),
        );
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
    localStorage.setItem(`selected_hypothesis_${_projectId}`, id);
    navigate(`/projects/${_projectId}?tab=experiments`);
  }, [_projectId, navigate]);

  const handleGoWorkflow = useCallback(() => {
    navigate(`/projects/${_projectId}?tab=workflow`);
  }, [_projectId, navigate]);

  const primaryHypothesis = useMemo(
    () => hypotheses.find((h) => h.isPrimary),
    [hypotheses]
  );

  const withEvidenceCount = useMemo(
    () => hypotheses.filter((h) => h.evidenceCount > 0).length,
    [hypotheses]
  );

  const avgVerifiability = useMemo(() => {
    if (hypotheses.length === 0) return 0;
    return Math.round(hypotheses.reduce((s, h) => s + h.verifiability, 0) / hypotheses.length);
  }, [hypotheses]);

  const atRiskCount = useMemo(
    () => hypotheses.filter((h) => h.off_topic || h.evidenceLevel === 'low').length,
    [hypotheses]
  );

  const statValues = useMemo(() => ({
    total: hypotheses.length,
    primary: primaryHypothesis ? 1 : 0,
    withEvidence: withEvidenceCount,
    avgVerifiability,
    atRisk: atRiskCount,
  }), [hypotheses, primaryHypothesis, withEvidenceCount, avgVerifiability, atRiskCount]);

  return (
    <div className="max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">候选假设</h1>
          <p className="text-gray-400">
            基于文献事实、知识缺口和数据上下文生成的科学假设
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
        <div className="mb-4 px-4 py-2.5 rounded-lg bg-primary-500/10 border border-primary-500/20 text-sm text-primary-300 animate-pulse">
          {alertMsg}
        </div>
      )}

      {loading && (
        <div className="flex flex-col items-center justify-center py-20 text-gray-400">
          <Loader2 className="w-8 h-8 animate-spin mb-3 text-primary-400" />
          <p className="text-sm">正在加载假设列表...</p>
        </div>
      )}

      {!loading && error && (
        <div className="flex flex-col items-center justify-center py-20 text-gray-400">
          <AlertCircle className="w-8 h-8 mb-3 text-red-400" />
          <p className="text-sm text-red-400 mb-2">加载假设失败</p>
          <p className="text-xs text-gray-500">{error}</p>
        </div>
      )}

      {!loading && !error && hypotheses.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-gray-400">
          <AlertTriangle className="w-8 h-8 mb-3 text-amber-400" />
          <p className="text-sm text-gray-400 mb-1">暂无候选假设</p>
          <p className="text-xs text-gray-500 mb-4">
            请先完成工作流中的假设生成阶段
          </p>
          <Button
            variant="secondary"
            size="sm"
            icon={<GitBranch className="w-4 h-4" />}
            onClick={handleGoWorkflow}
          >
            前往工作流
          </Button>
        </div>
      )}

      {!loading && !error && hypotheses.length > 0 && (
        <>
          {/* 摘要卡片 */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-5">
            {STAT_CARDS.map((sc) => {
              const Icon = sc.icon;
              const val = statValues[sc.key as keyof typeof statValues];
              return (
                <div
                  key={sc.key}
                  className="p-3 rounded-lg border border-dark-700 bg-dark-800/50"
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <Icon className={sc.color} size={16} />
                    <span className="text-xs text-gray-500">{sc.label}</span>
                  </div>
                  <span className="text-xl font-bold font-mono text-white">
                    {sc.key === 'avgVerifiability' ? `${val}` : val}
                    {sc.key === 'avgVerifiability' && <span className="text-xs text-gray-500">/100</span>}
                  </span>
                </div>
              );
            })}
          </div>

          {/* 主假设高亮 */}
          {primaryHypothesis && (
            <div className="mb-5">
              <div className="text-xs text-amber-400/70 mb-1.5 flex items-center gap-1">
                <Star className="w-3 h-3" /> 当前主假设
              </div>
              <HypothesisCard
                hypothesis={primaryHypothesis}
                onViewEvidence={handleViewEvidence}
                onSetPrimary={handleSetPrimary}
                onEnterExperiment={handleEnterExperiment}
              />
            </div>
          )}

          {/* 筛选栏 */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <h3 className="text-sm font-semibold text-white">
                候选列表 · {displayedHypotheses.length} 条
              </h3>
              {offTopicCount > 0 && (
                <span className="text-xs text-amber-400">
                  {hideOffTopic
                    ? `已隐藏 ${offTopicCount} 条偏题假设`
                    : `显示中 ${offTopicCount} 条偏题假设`}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              {offTopicCount > 0 && (
                <button
                  onClick={() => setHideOffTopic(!hideOffTopic)}
                  className="text-xs text-primary-400 hover:text-primary-300 transition-colors"
                >
                  {hideOffTopic ? '显示全部' : '隐藏偏题'}
                </button>
              )}
              <button
                onClick={() => setScoringExpanded(!scoringExpanded)}
                className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300 transition-colors"
              >
                <BarChart3 className="w-3.5 h-3.5" />
                评分说明
                {scoringExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              </button>
            </div>
          </div>

          {/* 可展开的评分说明 */}
          {scoringExpanded && (
            <div className="mb-4 p-4 rounded-lg border border-dark-700 bg-dark-800/30 animate-fade-in">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                {[
                  { label: '创新性', desc: '假设是否提出了新的方法、视角或理论框架，与现有工作的差异化程度。', color: 'purple', icon: '💡' },
                  { label: '可验证性', desc: '假设是否可以通过实验或观测进行检验，验证条件是否明确可操作。', color: 'green', icon: '✅' },
                  { label: '数据可得性', desc: '验证假设所需的数据是否可获取，数据质量和数量是否满足实验要求。', color: 'blue', icon: '📊' },
                  { label: '成本风险', desc: '实施验证的算力成本、时间成本及潜在的失败风险评估。', color: 'amber', icon: '⚠️' },
                ].map((dim) => (
                  <div key={dim.label} className="flex items-start gap-2">
                    <span className="text-sm shrink-0">{dim.icon}</span>
                    <div>
                      <span className="text-xs font-medium text-gray-300">{dim.label}</span>
                      <p className="text-[11px] text-gray-500 leading-relaxed mt-0.5">{dim.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 假设卡片列表 */}
          <div className="space-y-4">
            {displayedHypotheses
              .filter((h) => !h.isPrimary || hypotheses.length <= 1)
              .map((h) => (
                <HypothesisCard
                  key={h.id}
                  hypothesis={h}
                  onViewEvidence={handleViewEvidence}
                  onSetPrimary={handleSetPrimary}
                  onEnterExperiment={handleEnterExperiment}
                />
              ))}
          </div>
        </>
      )}

      {selectedHypothesis && (
        <EvidenceChainDrawer
          open={drawerOpen}
          onClose={handleCloseDrawer}
          hypothesisTitle={`${selectedHypothesis.title} (${selectedHypothesis.id})`}
          hypothesisContent={selectedHypothesis.content}
          evidenceCount={evidenceLoading ? 0 : currentEvidence.length}
          evidenceList={currentEvidence}
        />
      )}
    </div>
  );
}