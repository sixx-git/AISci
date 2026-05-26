import { cn } from '@/lib/utils';
import { Card } from '@/components/Card';
import { ScoreBar } from '@/components/ScoreBar';
import { Button } from '@/components/Button';
import {
  Star, Eye, FlaskConical, RefreshCw, AlertTriangle,
  Award, CheckCircle2, Sparkles, Target,
} from 'lucide-react';
import type { Hypothesis, DetailedHypothesis } from '@/types';

// ---- 旧接口（ResearchResults 使用） ----
interface HypothesisCardPropsOld {
  hypothesis: Hypothesis;
  isSelected?: boolean;
  onSelect?: () => void;
  index: number;
}

// ---- 新接口（HypothesesPage 使用） ----
interface HypothesisCardPropsDetailed {
  hypothesis: DetailedHypothesis;
  onViewEvidence?: (id: string) => void;
  onSetPrimary?: (id: string) => void;
  onEnterExperiment?: (id: string) => void;
  onRegenerate?: (id: string) => void;
}

type HypothesisCardProps =
  | (HypothesisCardPropsOld & { variant: 'compact' })
  | (HypothesisCardPropsDetailed & { variant?: 'detailed' });

// ============ 旧版评分辅助函数 ============
function getScoreColor(score: number) {
  if (score >= 85) return 'text-green-400';
  if (score >= 70) return 'text-yellow-400';
  return 'text-orange-400';
}
function getScoreBg(score: number) {
  if (score >= 85) return 'bg-green-500/20';
  if (score >= 70) return 'bg-yellow-500/20';
  return 'bg-orange-500/20';
}

// ============ 新版辅助函数 ============
function statusBadge(status: DetailedHypothesis['status']) {
  switch (status) {
    case 'confirmed':
      return { label: '已确认', cls: 'bg-green-500/15 text-green-400 border-green-500/30' };
    case 'evaluated':
      return { label: '已评估', cls: 'bg-blue-500/15 text-blue-400 border-blue-500/30' };
    case 'draft':
      return { label: '草稿', cls: 'bg-gray-500/15 text-gray-400 border-gray-500/30' };
  }
}

function overallColor(score: number) {
  if (score >= 85) return { bar: 'bg-green-500', text: 'text-green-400', bg: 'bg-green-500/10' };
  if (score >= 75) return { bar: 'bg-blue-500', text: 'text-blue-400', bg: 'bg-blue-500/10' };
  return { bar: 'bg-amber-500', text: 'text-amber-400', bg: 'bg-amber-500/10' };
}

export function HypothesisCard(props: HypothesisCardProps) {
  // 路由：variant === 'compact' → 旧版 compact 卡片
  if (props.variant === 'compact') {
    return <HypothesisCardCompact {...props} />;
  }
  // 否则 → 新版详细卡片
  return <HypothesisCardDetailed {...props} />;
}

// ===================== 旧版 compact 卡片 =====================
function HypothesisCardCompact({ hypothesis, isSelected, onSelect, index }: HypothesisCardPropsOld) {
  return (
    <Card
      className={cn(
        'cursor-pointer transition-all duration-200 hover:border-blue-500/50',
        isSelected && 'border-blue-500 bg-blue-500/5',
      )}
      onClick={onSelect}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500">
            <span className="text-white font-bold text-sm">{index + 1}</span>
          </div>
          <div>
            <div className="flex items-center gap-1">
              <Sparkles className="w-4 h-4 text-yellow-400" />
              <h4 className="font-semibold text-white">{hypothesis.title}</h4>
            </div>
          </div>
        </div>
        <div className={cn(
          'px-3 py-1 rounded-full text-sm font-bold',
          getScoreBg(hypothesis.score),
          getScoreColor(hypothesis.score),
        )}>
          {hypothesis.score}/100
        </div>
      </div>
      <p className="text-gray-300 text-sm mb-4 line-clamp-3">{hypothesis.description}</p>
      <div className="grid grid-cols-2 gap-2">
        {([
          ['新颖性', hypothesis.scores.novelty, Target, 'text-blue-400'],
          ['可行性', hypothesis.scores.feasibility, CheckCircle2, 'text-green-400'],
          ['科学价值', hypothesis.scores.scientific_value, Award, 'text-yellow-400'],
          ['可验证性', hypothesis.scores.testability, CheckCircle2, 'text-purple-400'],
        ] as const).map(([label, score, Icon, iconColor]) => (
          <div key={label} className="flex items-center gap-2">
            <Icon className={cn('w-4 h-4', iconColor)} />
            <div className="flex-1">
              <div className="flex justify-between text-xs mb-1">
                <span className="text-gray-400">{label}</span>
                <span className={getScoreColor(score)}>{score}</span>
              </div>
              <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
                <div className={cn('h-full rounded-full transition-all duration-500', getScoreBg(score))}
                  style={{ width: `${score}%` }} />
              </div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ===================== 新版详细卡片 =====================
function HypothesisCardDetailed({
  hypothesis,
  onViewEvidence,
  onSetPrimary,
  onEnterExperiment,
  onRegenerate,
}: HypothesisCardPropsDetailed) {
  const oc = overallColor(hypothesis.overallScore);
  const sb = statusBadge(hypothesis.status);

  return (
    <Card className="hover:border-gray-600 transition-colors">
      {/* 头部 */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className={cn(
            'w-10 h-10 rounded-lg flex items-center justify-center shrink-0',
            hypothesis.isPrimary ? 'bg-amber-500/20 border border-amber-500/30' : 'bg-gray-800',
          )}>
            {hypothesis.isPrimary ? (
              <Star className="w-5 h-5 text-amber-400" />
            ) : (
              <Award className="w-5 h-5 text-gray-500" />
            )}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="text-base font-semibold text-white truncate">{hypothesis.title}</h3>
              {hypothesis.isPrimary && (
                <span className="text-[11px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-500/30 shrink-0">
                  主假设
                </span>
              )}
            </div>
            <span className={cn('text-[11px] px-1.5 py-0.5 rounded border inline-block mt-1', sb.cls)}>
              {sb.label}
            </span>
          </div>
        </div>
        <div className={cn('flex items-center gap-1 px-3 py-1.5 rounded-lg shrink-0', oc.bg)}>
          <CheckCircle2 className={cn('w-4 h-4', oc.text)} />
          <span className={cn('text-lg font-bold font-mono', oc.text)}>{hypothesis.overallScore}</span>
          <span className="text-xs text-gray-500">/100</span>
        </div>
      </div>

      {/* 假设内容 */}
      <div className="mb-4 p-3 bg-gray-900/70 rounded-lg border border-gray-800">
        <p className="text-sm text-gray-300 leading-relaxed">{hypothesis.content}</p>
      </div>

      {/* 推理依据 */}
      <div className="mb-4">
        <div className="flex items-center gap-2 text-xs text-gray-500 mb-2">
          <Eye className="w-3.5 h-3.5" />
          推理依据 · {hypothesis.evidenceCount} 条证据支撑
        </div>
        <p className="text-xs text-gray-400 leading-relaxed line-clamp-3">{hypothesis.reasoning}</p>
      </div>

      {/* 评分维度 */}
      <div className="space-y-2 mb-4">
        <ScoreBar label="创新性" score={hypothesis.novelty} color="purple" />
        <ScoreBar label="可验证性" score={hypothesis.verifiability} color="green" />
        <ScoreBar label="数据可得性" score={hypothesis.dataAvailability} color="blue" />
      </div>

      {/* 风险提示 */}
      <div className="mb-4 p-3 rounded-lg border border-amber-500/15 bg-amber-500/5">
        <div className="flex items-center gap-1.5 mb-1">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
          <span className="text-xs font-medium text-amber-400">风险提示</span>
        </div>
        <p className="text-xs text-amber-300/80 leading-relaxed">{hypothesis.riskWarning}</p>
      </div>

      {/* 操作按钮 */}
      <div className="flex flex-wrap gap-2 pt-2 border-t border-gray-800">
        <Button variant="secondary" size="sm" icon={<Eye className="w-3.5 h-3.5" />}
          onClick={() => onViewEvidence?.(hypothesis.id)}>
          查看证据链
        </Button>
        {!hypothesis.isPrimary && (
          <Button variant="secondary" size="sm" icon={<Star className="w-3.5 h-3.5" />}
            onClick={() => onSetPrimary?.(hypothesis.id)}>
            设为主假设
          </Button>
        )}
        <Button variant="secondary" size="sm" icon={<FlaskConical className="w-3.5 h-3.5" />}
          onClick={() => onEnterExperiment?.(hypothesis.id)}>
          进入实验设计
        </Button>
        <Button variant="secondary" size="sm" icon={<RefreshCw className="w-3.5 h-3.5" />}
          onClick={() => onRegenerate?.(hypothesis.id)}>
          重新生成
        </Button>
      </div>
    </Card>
  );
}