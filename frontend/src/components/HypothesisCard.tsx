import { Card } from '@/components/Card';
import { cn } from '@/lib/utils';
import { Sparkles, Target, CheckCircle2, Award } from 'lucide-react';
import type { Hypothesis } from '@/types';

interface HypothesisCardProps {
  hypothesis: Hypothesis;
  isSelected?: boolean;
  onSelect?: () => void;
  index: number;
}

export const HypothesisCard = ({ 
  hypothesis, 
  isSelected, 
  onSelect,
  index 
}: HypothesisCardProps) => {
  const getScoreColor = (score: number) => {
    if (score >= 85) return 'text-green-400';
    if (score >= 70) return 'text-yellow-400';
    return 'text-orange-400';
  };

  const getScoreBg = (score: number) => {
    if (score >= 85) return 'bg-green-500/20';
    if (score >= 70) return 'bg-yellow-500/20';
    return 'bg-orange-500/20';
  };

  return (
    <Card
      className={cn(
        'cursor-pointer transition-all duration-200 hover:border-blue-500/50',
        isSelected && 'border-blue-500 bg-blue-500/5'
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
          getScoreColor(hypothesis.score)
        )}>
          {hypothesis.score}/100
        </div>
      </div>

      <p className="text-gray-300 text-sm mb-4 line-clamp-3">
        {hypothesis.description}
      </p>

      <div className="grid grid-cols-2 gap-2">
        <div className="flex items-center gap-2">
          <Target className="w-4 h-4 text-blue-400" />
          <div className="flex-1">
            <div className="flex justify-between text-xs mb-1">
              <span className="text-gray-400">新颖性</span>
              <span className={getScoreColor(hypothesis.scores.novelty)}>
                {hypothesis.scores.novelty}
              </span>
            </div>
            <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
              <div
                className={cn('h-full rounded-full transition-all duration-500',
                  getScoreBg(hypothesis.scores.novelty)
                )}
                style={{ width: `${hypothesis.scores.novelty}%` }}
              />
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-green-400" />
          <div className="flex-1">
            <div className="flex justify-between text-xs mb-1">
              <span className="text-gray-400">可行性</span>
              <span className={getScoreColor(hypothesis.scores.feasibility)}>
                {hypothesis.scores.feasibility}
              </span>
            </div>
            <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
              <div
                className={cn('h-full rounded-full transition-all duration-500',
                  getScoreBg(hypothesis.scores.feasibility)
                )}
                style={{ width: `${hypothesis.scores.feasibility}%` }}
              />
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Award className="w-4 h-4 text-yellow-400" />
          <div className="flex-1">
            <div className="flex justify-between text-xs mb-1">
              <span className="text-gray-400">科学价值</span>
              <span className={getScoreColor(hypothesis.scores.scientific_value)}>
                {hypothesis.scores.scientific_value}
              </span>
            </div>
            <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
              <div
                className={cn('h-full rounded-full transition-all duration-500',
                  getScoreBg(hypothesis.scores.scientific_value)
                )}
                style={{ width: `${hypothesis.scores.scientific_value}%` }}
              />
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-purple-400" />
          <div className="flex-1">
            <div className="flex justify-between text-xs mb-1">
              <span className="text-gray-400">可验证性</span>
              <span className={getScoreColor(hypothesis.scores.testability)}>
                {hypothesis.scores.testability}
              </span>
            </div>
            <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
              <div
                className={cn('h-full rounded-full transition-all duration-500',
                  getScoreBg(hypothesis.scores.testability)
                )}
                style={{ width: `${hypothesis.scores.testability}%` }}
              />
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
};
