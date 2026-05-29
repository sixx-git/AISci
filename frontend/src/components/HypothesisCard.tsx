import { useState } from 'react';
import { cn } from '@/lib/utils';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import {
  Star, Eye, FlaskConical, AlertTriangle, ChevronDown, ChevronUp,
  Award, CheckCircle2, Sparkles, Target,
} from 'lucide-react';
import type { Hypothesis, DetailedHypothesis } from '@/types';

interface HypothesisCardPropsOld {
  hypothesis: Hypothesis;
  isSelected?: boolean;
  onSelect?: () => void;
  index: number;
}

interface HypothesisCardPropsDetailed {
  hypothesis: DetailedHypothesis;
  onViewEvidence?: (id: string) => void;
  onSetPrimary?: (id: string) => void;
  onEnterExperiment?: (id: string) => void;
}

type HypothesisCardProps =
  | (HypothesisCardPropsOld & { variant: 'compact' })
  | (HypothesisCardPropsDetailed & { variant?: 'detailed' });

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

function evidenceLevelBadge(level: string) {
  switch (level) {
    case 'high':
      return { label: '高证据', cls: 'bg-green-500/15 text-green-400 border-green-500/30' };
    case 'medium':
      return { label: '中证据', cls: 'bg-blue-500/15 text-blue-400 border-blue-500/30' };
    default:
      return { label: '低证据', cls: 'bg-gray-500/15 text-gray-400 border-gray-500/30' };
  }
}

function overallColor(score: number) {
  if (score >= 85) return { bar: 'bg-green-500', text: 'text-green-400', bg: 'bg-green-500/10' };
  if (score >= 75) return { bar: 'bg-blue-500', text: 'text-blue-400', bg: 'bg-blue-500/10' };
  return { bar: 'bg-amber-500', text: 'text-amber-400', bg: 'bg-amber-500/10' };
}

export function HypothesisCard(props: HypothesisCardProps) {
  if (props.variant === 'compact') {
    return <HypothesisCardCompact {...props} />;
  }
  return <HypothesisCardDetailed {...props} />;
}

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

function HypothesisCardDetailed({
  hypothesis,
  onViewEvidence,
  onSetPrimary,
  onEnterExperiment,
}: HypothesisCardPropsDetailed) {
  const [expanded, setExpanded] = useState(false);
  const oc = overallColor(hypothesis.overallScore);
  const sb = statusBadge(hypothesis.status);
  const el = evidenceLevelBadge(hypothesis.evidenceLevel || 'medium');

  return (
    <Card className="hover:border-gray-600 transition-colors">
      <div className="flex items-start justify-between mb-2">
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
              <h3 className="text-sm font-semibold text-white truncate">{hypothesis.title}</h3>
              {hypothesis.isPrimary && (
                <span className="text-[11px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-500/30 shrink-0">
                  主假设
                </span>
              )}
            </div>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className={cn('text-[11px] px-1.5 py-0.5 rounded border', sb.cls)}>
                {sb.label}
              </span>
              <span className={cn('text-[11px] px-1.5 py-0.5 rounded border', el.cls)}>
                {el.label}
              </span>
            </div>
          </div>
        </div>
        <div className={cn('flex items-center gap-1 px-3 py-1.5 rounded-lg shrink-0', oc.bg)}>
          <CheckCircle2 className={cn('w-4 h-4', oc.text)} />
          <span className={cn('text-lg font-bold font-mono', oc.text)}>{hypothesis.overallScore}</span>
          <span className="text-xs text-gray-500">/100</span>
        </div>
      </div>

      <p className="text-sm text-gray-300 leading-relaxed mb-2">{hypothesis.content}</p>

      {/* 关键信息行 */}
      <div className="flex flex-wrap items-center gap-2 mb-2">
        {hypothesis.question_alignment && (
          <span className="text-[11px] text-primary-300/80 bg-primary-500/5 border border-primary-500/15 rounded px-2 py-0.5 max-w-[320px] truncate"
            title={hypothesis.question_alignment}>
            {hypothesis.question_alignment}
          </span>
        )}
        {hypothesis.validation_target && (
          <span className="text-[11px] font-mono text-green-300 bg-green-500/10 border border-green-500/20 rounded px-1.5 py-0.5">
            {hypothesis.validation_target}
          </span>
        )}
        <span className="text-[11px] text-gray-500">{hypothesis.evidenceCount} 条证据</span>
        {hypothesis.off_topic && (
          <span className="text-[11px] text-red-400 bg-red-500/10 border border-red-500/20 rounded px-1.5 py-0.5 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" />
            偏题
          </span>
        )}
      </div>

      {/* 风险一行 */}
      {hypothesis.riskWarning && (
        <p className={cn(
          'text-xs leading-relaxed mb-2',
          expanded ? '' : 'truncate',
          hypothesis.off_topic ? 'text-red-300/70' : 'text-amber-300/70',
        )}>
          {hypothesis.riskWarning}
        </p>
      )}

      {/* 展开详情 */}
      {expanded && (
        <div className="mt-2 pt-3 border-t border-gray-800 space-y-3 animate-fade-in">
          {/* 偏题警告 */}
          {hypothesis.off_topic && hypothesis.off_topic_reason && (
            <div className="p-2.5 rounded-lg border border-red-500/20 bg-red-500/5">
              <div className="flex items-center gap-1.5 mb-1">
                <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
                <span className="text-xs font-semibold text-red-400">偏题警告</span>
              </div>
              <p className="text-xs text-red-300/80 leading-relaxed">{hypothesis.off_topic_reason}</p>
              {hypothesis.alignment_score !== undefined && (
                <p className="text-xs text-red-400/70 mt-1">
                  对齐分数: {hypothesis.alignment_score}/100
                </p>
              )}
            </div>
          )}

          {/* 推理依据 */}
          <div>
            <div className="flex items-center gap-2 text-xs text-gray-500 mb-1.5">
              <Eye className="w-3.5 h-3.5" />
              推理依据
            </div>
            <p className="text-xs text-gray-400 leading-relaxed">{hypothesis.reasoning}</p>
          </div>

          {/* 验证信息 */}
          {(hypothesis.validation_target || hypothesis.expected_measurable_effect || (hypothesis.dataset_field_refs && hypothesis.dataset_field_refs.length > 0)) && (
            <div className="p-2.5 rounded-lg border border-green-500/15 bg-green-500/5">
              <div className="flex items-center gap-1.5 mb-1.5">
                <Target className="w-3.5 h-3.5 text-green-400" />
                <span className="text-xs font-medium text-green-400">验证目标与数据</span>
              </div>
              {hypothesis.expected_measurable_effect && (
                <p className="text-xs text-green-300/80 mb-1">{hypothesis.expected_measurable_effect}</p>
              )}
              {hypothesis.dataset_field_refs && hypothesis.dataset_field_refs.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {hypothesis.dataset_field_refs.map((ref) => (
                    <span key={ref} className="text-[10px] font-mono text-green-300/70 bg-green-500/10 px-1.5 py-0.5 rounded">
                      {ref}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 评分维度 */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs text-gray-500">
              <span>评分维度</span>
            </div>
            <ScoreBarSimple label="创新性" score={hypothesis.novelty} color="purple" />
            <ScoreBarSimple label="可验证性" score={hypothesis.verifiability} color="green" />
            <ScoreBarSimple label="数据可得性" score={hypothesis.dataAvailability} color="blue" />
          </div>
        </div>
      )}

      {/* 操作按钮 */}
      <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-gray-800">
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
        <button
          onClick={() => setExpanded(!expanded)}
          className="ml-auto flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300 transition-colors"
        >
          {expanded ? (
            <>
              <ChevronUp className="w-3.5 h-3.5" />
              收起详情
            </>
          ) : (
            <>
              <ChevronDown className="w-3.5 h-3.5" />
              展开详情
            </>
          )}
        </button>
      </div>
    </Card>
  );
}

/** 精简评分条 */
function ScoreBarSimple({ label, score, color }: { label: string; score: number; color: string }) {
  const barColorMap: Record<string, string> = {
    purple: 'bg-purple-500',
    green: 'bg-green-500',
    blue: 'bg-blue-500',
    amber: 'bg-amber-500',
  };
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-500 w-16 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={cn('h-full rounded-full', barColorMap[color] || 'bg-gray-500')}
          style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
        />
      </div>
      <span className="text-xs text-gray-400 font-mono w-6 text-right">{score}</span>
    </div>
  );
}