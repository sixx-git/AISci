import { Swords, ArrowRight } from 'lucide-react';
import type { ProConAdversarialData } from '@/types';
import { cn } from '@/lib/utils';

interface AdversarialReviewSummaryProps {
  data: ProConAdversarialData;
  className?: string;
  onViewDetail?: () => void;
}

const MODE_SHORT: Record<string, string> = {
  single_group: '单研究组红蓝对抗',
  multi_group: '多研究组组间攻防',
};

export function AdversarialReviewSummary({
  data,
  className,
  onViewDetail,
}: AdversarialReviewSummaryProps) {
  const mode = data.mode || 'single_group';
  const conRounds = data.con_side?.rounds?.length ?? 0;
  const crossCount = data.cross_group_attacks?.length ?? 0;
  const evolutionPoints = data.evolution?.revision_points?.length ?? 0;
  const override = data.primary_index_override;

  const parts: string[] = [];
  if (mode === 'single_group' && conRounds > 0) {
    parts.push(`反方 ${conRounds} 轮质疑`);
  }
  if (mode === 'multi_group' && crossCount > 0) {
    parts.push(`组间攻防 ${crossCount} 次`);
  }
  if (evolutionPoints > 0) {
    parts.push(`正方修订 ${evolutionPoints} 条`);
  }
  if (override?.to != null) {
    parts.push(`主假设调整为研究组 ${override.to}`);
  }

  return (
    <div
      className={cn(
        'flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-3 rounded-bp',
        'border border-bp-cyan/25 bg-bp-cyan/5',
        className,
      )}
    >
      <div className="flex items-start gap-2 min-w-0">
        <Swords className="w-4 h-4 text-bp-cyan shrink-0 mt-0.5" />
        <div className="min-w-0">
          <p className="text-xs font-medium text-bp-text">
            红蓝对抗审查已完成
            <span className="text-bp-muted font-normal ml-1.5">
              {MODE_SHORT[mode] ?? mode}
            </span>
          </p>
          <p className="text-xs text-bp-muted mt-0.5">
            {parts.length > 0
              ? parts.join(' · ')
              : '假设评估阶段已执行正方/反方对抗包装'}
            {data.evolution?.evolved_rationale
              ? ` · ${data.evolution.evolved_rationale.slice(0, 80)}${data.evolution.evolved_rationale.length > 80 ? '…' : ''}`
              : ''}
          </p>
        </div>
      </div>
      {onViewDetail && (
        <button
          type="button"
          onClick={onViewDetail}
          className="inline-flex items-center gap-1 text-xs text-bp-cyan hover:text-bp-cyan/80 shrink-0"
        >
          查看完整对抗记录
          <ArrowRight className="w-3 h-3" />
        </button>
      )}
    </div>
  );
}
