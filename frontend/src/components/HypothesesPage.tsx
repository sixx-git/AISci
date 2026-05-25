import { useState, useCallback } from 'react';
import { Lightbulb, Info } from 'lucide-react';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { HypothesisCard } from '@/components/HypothesisCard';
import { ScoreBar } from '@/components/ScoreBar';
import { MOCK_DETAILED_HYPOTHESES } from '@/data/mockData';
import type { DetailedHypothesis } from '@/data/mockData';

interface HypothesesPageProps {
  projectId?: string;
  compact?: boolean;
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

export function HypothesesPage({ projectId: _projectId, compact: _compact = false }: HypothesesPageProps) {
  const [hypotheses, setHypotheses] = useState<DetailedHypothesis[]>(MOCK_DETAILED_HYPOTHESES);
  const [alertMsg, setAlertMsg] = useState<string | null>(null);

  const showAlert = useCallback((msg: string) => {
    setAlertMsg(msg);
    setTimeout(() => setAlertMsg(null), 2500);
  }, []);

  const handleViewEvidence = useCallback((_id: string) => {
    showAlert('证据链视图将在后续版本中实现');
  }, [showAlert]);

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
    showAlert('重新生成请求已提交（模拟）');
  }, [showAlert]);

  return (
    <div className="max-w-7xl mx-auto">
      {/* ========== 头部 ========== */}
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
            onClick={() => showAlert('生成新假设中…（模拟 3s）')}
          >
            生成新假设
          </Button>
        </div>
      </div>

      {/* 短暂提示 */}
      {alertMsg && (
        <div className="mb-4 px-4 py-2.5 rounded-lg bg-primary-500/10 border border-primary-500/20 text-sm text-primary-300 animate-pulse">
          {alertMsg}
        </div>
      )}

      {/* ========== 主布局 ========== */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* 左侧/中间：假设卡片 */}
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

        {/* 右侧：评分维度说明 */}
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

            {/* 统计摘要 */}
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
                    {Math.round(hypotheses.reduce((s, h) => s + h.overallScore, 0) / hypotheses.length)}
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
    </div>
  );
}