import { Trash2, Plus } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ImpactHistoryItem } from '@/services/predictService';
import { ratingBadgeClass } from './predictHelpers';

interface PredictSidebarProps {
  items: ImpactHistoryItem[];
  loading: boolean;
  selectedId: string | null;
  onSelect: (jobId: string) => void;
  onDelete: (jobId: string) => void;
  onNew: () => void;
  serviceError?: string | null;
}

export function PredictSidebar({
  items,
  loading,
  selectedId,
  onSelect,
  onDelete,
  onNew,
  serviceError,
}: PredictSidebarProps) {
  return (
    <aside className="flex flex-col h-full min-h-[640px] overflow-hidden bg-[#1a1a1a] text-white">
      <div className="px-4 pt-5 pb-3.5 border-b border-white/10">
        <h2 className="text-[0.95rem] font-semibold tracking-wide text-[#eee]">已预测文献</h2>
        <p className="text-[11px] text-[#888] mt-1">点击查看完整影响力报告</p>
      </div>

      <div className="flex-1 overflow-y-auto p-2 min-h-0">
        {serviceError && (
          <div className="m-1.5 mb-2 p-2.5 rounded-lg border border-amber-500/40 bg-amber-500/10 text-[11px] text-amber-200 leading-relaxed">
            {serviceError}
          </div>
        )}
        {loading ? (
          <p className="text-xs text-[#888] text-center py-10">加载中…</p>
        ) : items.length === 0 ? (
          <p className="text-xs text-[#666] text-center py-10 px-4 leading-relaxed">
            暂无已完成预测。
            <br />
            上传论文 PDF 开始一次影响力预测。
          </p>
        ) : (
          items.map((item) => {
            const active = item.job_id === selectedId;
            const score =
              item.total_score != null && Number.isFinite(Number(item.total_score))
                ? Number(item.total_score).toFixed(1)
                : '—';
            return (
              <div
                key={item.job_id}
                className={cn(
                  'group relative rounded-md px-3 py-2.5 mb-1 cursor-pointer transition-colors',
                  active ? 'bg-[#333]' : 'hover:bg-[#2a2a2a]',
                )}
                onClick={() => onSelect(item.job_id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') onSelect(item.job_id);
                }}
                role="button"
                tabIndex={0}
              >
                <button
                  type="button"
                  className="absolute top-1.5 right-1.5 w-[18px] h-[18px] rounded-full text-[#666] text-[11px] leading-[18px] text-center opacity-0 group-hover:opacity-100 hover:bg-[#555] hover:text-white"
                  title="删除"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (window.confirm('确认删除该预测记录？')) onDelete(item.job_id);
                  }}
                >
                  <Trash2 className="w-3 h-3 mx-auto" />
                </button>
                <div className="text-[0.8rem] text-[#ddd] truncate pr-5 mb-1 font-medium">
                  {item.title || '未知标题'}
                </div>
                <div className="flex items-center gap-2 flex-wrap text-[0.73rem] text-[#999]">
                  <span
                    className={cn(
                      'inline-block px-2 py-0.5 rounded text-[0.72rem] font-bold leading-relaxed',
                      ratingBadgeClass(item.rating || 'N'),
                    )}
                  >
                    {item.rating || 'N'}
                  </span>
                  <span className="font-semibold text-[#bbb]">{score}</span>
                  {item.year != null && item.year !== '' && <span>{item.year}</span>}
                  {item.citations != null && <span>引 {item.citations}</span>}
                </div>
                {item.venue && (
                  <div className="text-[10px] text-[#777] mt-1 truncate">{item.venue}</div>
                )}
              </div>
            );
          })
        )}
      </div>

      <div className="p-3 border-t border-white/10">
        <button
          type="button"
          onClick={onNew}
          className="w-full flex items-center justify-center gap-1.5 py-2.5 rounded-md border border-[#555] text-[0.8125rem] text-[#ccc] hover:bg-[#333] hover:border-[#888] hover:text-white transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          新建预测
        </button>
      </div>
    </aside>
  );
}
