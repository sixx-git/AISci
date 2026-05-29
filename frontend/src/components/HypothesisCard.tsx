import { useState } from 'react';
import { cn } from '@/lib/utils';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import {
  Star, Eye, FlaskConical, AlertTriangle, ChevronDown, ChevronUp,
  Award, CheckCircle2, Target,
} from 'lucide-react';
import type { DetailedHypothesis } from '@/types';

interface HypothesisCardProps {
  hypothesis: DetailedHypothesis;
  onViewEvidence?: (id: string) => void;
  onSetPrimary?: (id: string) => void;
  onEnterExperiment?: (id: string) => void;
}

function overallColor(score: number) {
  if (score >= 85) return { bar: 'bg-green-500', text: 'text-green-400', bg: 'bg-green-500/10' };
  if (score >= 75) return { bar: 'bg-blue-500', text: 'text-blue-400', bg: 'bg-blue-500/10' };
  return { bar: 'bg-amber-500', text: 'text-amber-400', bg: 'bg-amber-500/10' };
}

export function HypothesisCard({
  hypothesis,
  onViewEvidence,
  onSetPrimary,
  onEnterExperiment,
}: HypothesisCardProps) {
  const [expanded, setExpanded] = useState(false);
  const oc = overallColor(hypothesis.overallScore);
  const hasDatasetFields = (hypothesis.dataset_field_refs?.length ?? 0) > 0;
  const hasDataEvidence = (hypothesis.data_evidence_ids?.length ?? 0) > 0;
  const isLowEvidence = hypothesis.evidenceLevel === 'low' || (!hasDatasetFields && !hasDataEvidence);
  const canEnterExperiment = !hypothesis.off_topic;

  return (
    <Card className={cn(
      'hover:border-gray-600 transition-colors',
      hypothesis.off_topic && 'border-red-500/30 bg-red-500/5',
      isLowEvidence && !hypothesis.off_topic && 'border-amber-500/20 bg-amber-500/5',
    )}>
      {/* ===== 头部：主假设标记 + 标题 + 评分 ===== */}
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
              {hypothesis.off_topic && (
                <span className="text-[11px] px-1.5 py-0.5 rounded bg-red-500/15 text-red-400 border border-red-500/30 shrink-0 flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" />
                  偏题
                </span>
              )}
            </div>
            <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
              <span className={`text-[11px] px-1.5 py-0.5 rounded border ${evidenceLevelBadgeCls(hypothesis.evidenceLevel)}`}>
                {evidenceLevelLabel(hypothesis.evidenceLevel)}
              </span>
              {hypothesis.alignment_score != null && (
                <span className={`text-[11px] px-1.5 py-0.5 rounded border font-mono ${
                  hypothesis.alignment_score >= 70 ? 'bg-green-500/10 text-green-400 border-green-500/25' :
                  hypothesis.alignment_score >= 40 ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/25' :
                  'bg-red-500/10 text-red-400 border-red-500/25'
                }`}>
                  对齐 {hypothesis.alignment_score}
                </span>
              )}
            </div>
          </div>
        </div>
        <div className={cn('flex items-center gap-1 px-3 py-1.5 rounded-lg shrink-0', oc.bg)}>
          <CheckCircle2 className={cn('w-4 h-4', oc.text)} />
          <span className={cn('text-lg font-bold font-mono', oc.text)}>{hypothesis.overallScore}</span>
          <span className="text-xs text-gray-500">/100</span>
        </div>
      </div>

      {/* ===== 假设内容 ===== */}
      <p className="text-sm text-gray-300 leading-relaxed mb-2">{hypothesis.content}</p>

      {/* ===== 关键信息标签行 ===== */}
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
        {hypothesis.expected_measurable_effect && (
          <span className="text-[11px] text-blue-300/80 bg-blue-500/5 border border-blue-500/15 rounded px-1.5 py-0.5 max-w-[260px] truncate"
            title={hypothesis.expected_measurable_effect}>
            {hypothesis.expected_measurable_effect}
          </span>
        )}
        <span className="text-[11px] text-gray-500">{hypothesis.evidenceCount} 条证据</span>
        {hasDatasetFields && (
          <span className="text-[11px] text-gray-500">{hypothesis.dataset_field_refs!.length} 个数据字段</span>
        )}
      </div>

      {/* ===== 风险一行 ===== */}
      {hypothesis.riskWarning && (
        <p className={cn(
          'text-xs leading-relaxed mb-2',
          hypothesis.off_topic ? 'text-red-300/70' : 'text-amber-300/70',
        )}>
          {hypothesis.riskWarning}
        </p>
      )}

      {/* ===== 低证据提示 ===== */}
      {isLowEvidence && !hypothesis.off_topic && (
        <div className="mb-2 p-2 rounded border border-amber-500/20 bg-amber-500/5 text-[11px] text-amber-300/80 flex items-start gap-1.5">
          <AlertTriangle className="w-3 h-3 shrink-0 mt-0.5" />
          <span>当前假设证据不足，建议先补充文献或数据集。</span>
        </div>
      )}

      {/* ===== 展开详情 ===== */}
      {expanded && (
        <div className="mt-3 pt-3 border-t border-gray-800 space-y-3 animate-fade-in">
          {/* 偏题警告 */}
          {hypothesis.off_topic && hypothesis.off_topic_reason && (
            <div className="p-2.5 rounded-lg border border-red-500/20 bg-red-500/5">
              <div className="flex items-center gap-1.5 mb-1">
                <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
                <span className="text-xs font-semibold text-red-400">偏题警告</span>
              </div>
              <p className="text-xs text-red-300/80 leading-relaxed">{hypothesis.off_topic_reason}</p>
              {hypothesis.domain_conflict_keywords && hypothesis.domain_conflict_keywords.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {hypothesis.domain_conflict_keywords.map((kw) => (
                    <span key={kw} className="text-[10px] text-red-400/70 bg-red-500/10 px-1.5 py-0.5 rounded">
                      {kw}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 推理依据 */}
          {hypothesis.reasoning && (
            <div>
              <div className="flex items-center gap-2 text-xs text-gray-500 mb-1.5">
                <Eye className="w-3.5 h-3.5" />
                推理依据
              </div>
              <p className="text-xs text-gray-400 leading-relaxed">{hypothesis.reasoning}</p>
            </div>
          )}

          {/* 验证目标与数据 */}
          {(hypothesis.validation_target || hypothesis.expected_measurable_effect || hasDatasetFields) && (
            <div className="p-2.5 rounded-lg border border-green-500/15 bg-green-500/5">
              <div className="flex items-center gap-1.5 mb-1.5">
                <Target className="w-3.5 h-3.5 text-green-400" />
                <span className="text-xs font-medium text-green-400">验证目标与数据</span>
              </div>
              {hypothesis.expected_measurable_effect && (
                <p className="text-xs text-green-300/80 mb-1">{hypothesis.expected_measurable_effect}</p>
              )}
              {hasDatasetFields && hypothesis.dataset_field_refs && (
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

          {/* 关键词信息 */}
          {(hypothesis.matched_keywords || hypothesis.missing_keywords) && (
            <div className="p-2.5 rounded-lg border border-primary-500/15 bg-primary-500/5">
              <div className="flex items-center gap-1.5 mb-1.5">
                <Target className="w-3.5 h-3.5 text-primary-400" />
                <span className="text-xs font-medium text-primary-400">关键词分析</span>
              </div>
              {hypothesis.matched_keywords && hypothesis.matched_keywords.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-1">
                  <span className="text-[10px] text-gray-500">匹配:</span>
                  {hypothesis.matched_keywords.map((kw) => (
                    <span key={kw} className="text-[10px] text-green-300/70 bg-green-500/10 px-1.5 py-0.5 rounded">{kw}</span>
                  ))}
                </div>
              )}
              {hypothesis.missing_keywords && hypothesis.missing_keywords.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  <span className="text-[10px] text-gray-500">缺失:</span>
                  {hypothesis.missing_keywords.map((kw) => (
                    <span key={kw} className="text-[10px] text-amber-300/70 bg-amber-500/10 px-1.5 py-0.5 rounded">{kw}</span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 评分维度（仅展开时显示） */}
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

      {/* ===== 操作按钮（精简为 3 个） ===== */}
      <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-gray-800">
        <Button variant="secondary" size="sm" icon={<Eye className="w-3.5 h-3.5" />}
          onClick={() => onViewEvidence?.(hypothesis.id)}>
          查看证据链
        </Button>
        {!hypothesis.isPrimary && (
          <Button variant="secondary" size="sm" icon={<Star className="w-3.5 h-3.5" />}
            disabled={hypothesis.off_topic}
            onClick={() => onSetPrimary?.(hypothesis.id)}>
            设为主假设
          </Button>
        )}
        <Button variant="secondary" size="sm" icon={<FlaskConical className="w-3.5 h-3.5" />}
          disabled={!canEnterExperiment}
          onClick={canEnterExperiment ? () => onEnterExperiment?.(hypothesis.id) : undefined}
          title={!canEnterExperiment ? '偏题假设无法进入实验设计' : '进入实验设计'}>
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

function evidenceLevelLabel(level: string | undefined): string {
  switch (level) {
    case 'high': return '高证据';
    case 'medium': return '中证据';
    default: return '低证据';
  }
}

function evidenceLevelBadgeCls(level: string | undefined): string {
  switch (level) {
    case 'high': return 'bg-green-500/15 text-green-400 border-green-500/30';
    case 'medium': return 'bg-blue-500/15 text-blue-400 border-blue-500/30';
    default: return 'bg-gray-500/15 text-gray-400 border-gray-500/30';
  }
}

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