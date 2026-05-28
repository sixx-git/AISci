import { useState, useCallback, useEffect } from 'react';
import { Lightbulb, Info, Loader2, AlertCircle, AlertTriangle, FlaskConical } from 'lucide-react';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { HypothesisCard } from '@/components/HypothesisCard';
import { ScoreBar } from '@/components/ScoreBar';
import { EvidenceChainDrawer } from '@/components/EvidenceChainDrawer';
import hypothesisService, { type BackendHypothesis, type BackendEvidence } from '@/services/hypothesisService';
import type { DetailedHypothesis, EvidenceItem } from '@/types';

interface HypothesesPageProps {
  projectId?: string;
  compact?: boolean;
  revalidateKey?: number;
  latestRunId?: string | null;
}

const SCORE_DIMENSIONS = [
  {
    label: '创新性',
    desc: '假设是否提出了新的方法、视角或理论框架，与现有工作的差异化程度。',
    color: 'purple' as const,
    icon: '💡',
  },
  {
    label: '自洽性',
    desc: '假设内部的逻辑一致性，推理链条是否严密，无自相矛盾之处。',
    color: 'blue' as const,
    icon: '🔗',
  },
  {
    label: '可验证性',
    desc: '假设是否可以通过实验或观测进行检验，验证条件是否明确可操作。',
    color: 'green' as const,
    icon: '✅',
  },
  {
    label: '数据可得性',
    desc: '验证假设所需的数据是否可获取，数据质量和数量是否满足实验要求。',
    color: 'blue' as const,
    icon: '📊',
  },
  {
    label: '成本风险',
    desc: '实施验证的算力成本、时间成本及潜在的失败风险评估。',
    color: 'amber' as const,
    icon: '⚠️',
  },
];

function evidenceLevelToScore(level: string): number {
  switch (level) {
    case 'high': return 88;
    case 'medium': return 70;
    case 'low': return 50;
    default: return 65;
  }
}

function mapBackendToDetailed(h: BackendHypothesis): DetailedHypothesis {
  const evidenceScore = evidenceLevelToScore(h.evidence_level);
  return {
    id: h.id,
    title: h.hypothesis || '未命名假设',
    content: h.hypothesis || '',
    reasoning: h.rationale || '',
    evidenceCount: (h.supporting_fact_ids || []).length,
    novelty: evidenceScore,
    verifiability: h.testability === 'high' ? 88 : h.testability === 'low' ? 55 : 75,
    dataAvailability: h.required_data === 'high' ? 85 : h.required_data === 'low' ? 55 : 70,
    overallScore: Math.round((h.confidence || 0.5) * 100),
    riskWarning: h.risk || '',
    isPrimary: h.priority === 1,
    status: (h.status === 'testing' || h.status === 'accepted' || h.status === 'confirmed')
      ? 'evaluated' : 'draft',
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

export function HypothesesPage({
  projectId: _projectId,
  compact: _compact = false,
  revalidateKey: _revalidateKey,
  latestRunId: _latestRunId,
}: HypothesesPageProps) {
  const [hypotheses, setHypotheses] = useState<DetailedHypothesis[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [alertMsg, setAlertMsg] = useState<string | null>(null);

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

  const handleSetPrimary = useCallback((id: string) => {
    setHypotheses((prev) =>
      prev.map((h) => ({ ...h, isPrimary: h.id === id })),
    );
    showAlert('已设为主假设');
  }, [showAlert]);

  const handleEnterExperiment = useCallback((_id: string) => {
    showAlert('跳转至实验设计页面（待对接）');
  }, [showAlert]);

  const handleRegenerate = useCallback((_id: string) => {
    showAlert('请在工作流页面运行 Pipeline 以重新生成假设');
  }, [showAlert]);

  const handleGenerateNew = useCallback(() => {
    showAlert('请先在工作流页面运行 Pipeline，完成后返回此页面查看生成的假设');
  }, [showAlert]);

  return (
    <div className="max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">候选假设</h1>
          <p className="text-gray-400">
            基于文献事实、知识缺口和逻辑推理生成可验证科学假设
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="primary"
            size="sm"
            icon={<Lightbulb className="w-4 h-4" />}
            onClick={handleGenerateNew}
          >
            生成新假设
          </Button>
        </div>
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
          <p className="text-sm text-gray-400 mb-2">暂无假设数据</p>
          <p className="text-xs text-gray-500 mb-4">
            请先在工作流页面运行 Pipeline，完成 hypothesis_generation 阶段后即可查看
          </p>
          <Button
            variant="secondary"
            size="sm"
            icon={<FlaskConical className="w-4 h-4" />}
            onClick={() => showAlert('请前往工作流页面运行 Pipeline')}
          >
            前往工作流
          </Button>
        </div>
      )}

      {!loading && !error && hypotheses.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <div className="lg:col-span-3 space-y-5">
            {hypotheses.map((h) => (
              <HypothesisCard
                key={h.id}
                hypothesis={h}
                onViewEvidence={handleViewEvidence}
                onSetPrimary={handleSetPrimary}
                onEnterExperiment={handleEnterExperiment}
                onRegenerate={handleRegenerate}
              />
            ))}
          </div>

          <div className="lg:col-span-1">
            <div className="sticky top-6 space-y-4">
              <Card>
                <div className="flex items-center gap-2 mb-4">
                  <Info className="w-4 h-4 text-primary-400" />
                  <h3 className="text-sm font-semibold text-white">评分维度说明</h3>
                </div>
                {SCORE_DIMENSIONS.map((dim) => (
                  <div key={dim.label} className="mb-4 last:mb-0">
                    <div className="flex items-center gap-1.5 mb-1">
                      <span className="text-xs">{dim.icon}</span>
                      <span className="text-xs font-medium text-gray-300">{dim.label}</span>
                    </div>
                    <p className="text-xs text-gray-500 leading-relaxed mb-2">{dim.desc}</p>
                    <ScoreBar
                      label=""
                      score={dim.label === '创新性' ? 85 : dim.label === '自洽性' ? 90 : dim.label === '可验证性' ? 88 : dim.label === '数据可得性' ? 75 : 65}
                      color={dim.color}
                    />
                  </div>
                ))}
              </Card>

              <Card>
                <h4 className="text-sm font-semibold text-white mb-3">假设统计</h4>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-gray-400">假设总数</span>
                    <span className="text-white font-mono">{hypotheses.length}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">平均综合评分</span>
                    <span className="text-green-400 font-mono">
                      {hypotheses.length > 0
                        ? Math.round(hypotheses.reduce((s, h) => s + h.overallScore, 0) / hypotheses.length)
                        : 0}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">总证据引用</span>
                    <span className="text-blue-400 font-mono">
                      {hypotheses.reduce((s, h) => s + h.evidenceCount, 0)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">已评估</span>
                    <span className="text-gray-300 font-mono">
                      {hypotheses.filter((h) => h.status === 'evaluated').length}/{hypotheses.length}
                    </span>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        </div>
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