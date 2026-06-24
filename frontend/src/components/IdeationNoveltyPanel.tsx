import { Sparkles, BookOpen, AlertTriangle } from 'lucide-react';
import type { IdeationNoveltyData } from '@/types';

interface IdeationNoveltyPanelProps {
  ideation: IdeationNoveltyData;
}

export function IdeationNoveltyPanel({ ideation }: IdeationNoveltyPanelProps) {
  const angles = ideation.suggested_angles ?? [];
  const similar = ideation.top_similar_works ?? [];

  return (
    <div className="p-4 rounded-lg border border-bp-border bg-bp-panel/30">
      <h3 className="text-sm font-semibold text-bp-text mb-3 flex items-center gap-2">
        <Sparkles className="w-4 h-4 text-purple-400" />
        Ideation 新颖性预检（OpenAlex / Semantic Scholar）
      </h3>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3">
        <MiniStat label="外部文献" value={String(ideation.external_papers_count ?? 0)} />
        <MiniStat
          label="新颖性分"
          value={ideation.novelty_score != null ? Number(ideation.novelty_score).toFixed(1) : '—'}
        />
        <MiniStat label="风险" value={ideation.novelty_risk || '—'} />
        <MiniStat label="num_ideas" value={String(ideation.num_ideas_requested ?? '—')} />
      </div>

      {ideation.assessment && (
        <p className="text-xs text-bp-muted mb-3">{ideation.assessment}</p>
      )}

      {angles.length > 0 && (
        <div className="mb-3">
          <p className="text-[11px] text-bp-muted mb-1.5">建议探索方向（供假设树选择）</p>
          <ul className="space-y-1">
            {angles.map((a, i) => (
              <li key={i} className="text-xs text-bp-text flex gap-1.5">
                <span className="text-purple-400 font-mono shrink-0">{i + 1}.</span>
                {a}
              </li>
            ))}
          </ul>
        </div>
      )}

      {similar.length > 0 && (
        <div>
          <p className="text-[11px] text-bp-muted mb-1.5 flex items-center gap-1">
            <BookOpen className="w-3 h-3" /> 相近外部工作
          </p>
          <ul className="space-y-1 max-h-32 overflow-y-auto">
            {similar.slice(0, 5).map((w, i) => (
              <li key={i} className="text-[11px] text-bp-muted line-clamp-1">
                [{w.year ?? '?'}] {w.title}
                {w.overlap_ratio != null ? ` · overlap ${(Number(w.overlap_ratio) * 100).toFixed(0)}%` : ''}
              </li>
            ))}
          </ul>
        </div>
      )}

      {ideation.novelty_risk === 'high' && (
        <p className="mt-2 text-[11px] text-yellow-400 flex items-center gap-1">
          <AlertTriangle className="w-3 h-3" /> 外部文献重叠较高，建议在 ideation 阶段调整方向
        </p>
      )}
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="p-2 rounded border border-bp-border bg-bp-base/50">
      <p className="text-[10px] text-bp-muted">{label}</p>
      <p className="text-sm font-mono font-semibold text-bp-text">{value}</p>
    </div>
  );
}
