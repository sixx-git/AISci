import { CheckCircle, AlertTriangle, XCircle } from 'lucide-react';
import { Card } from './Card';
import { cn } from '@/lib/utils';
import type { ReportSection } from '@/types';

interface ReportChecklistProps {
  sections: ReportSection[];
  className?: string;
}

const statusConfig: Record<ReportSection['status'], { icon: typeof CheckCircle; label: string; className: string }> = {
  completed:  { icon: CheckCircle,  label: '已完成',  className: 'text-green-400 bg-green-500/10 border-green-500/20' },
  missing:    { icon: XCircle,      label: '缺失',    className: 'text-red-400 bg-red-500/10 border-red-500/20' },
  human_review: { icon: AlertTriangle, label: '需人工确认', className: 'text-amber-400 bg-amber-500/10 border-amber-500/20' },
};

export function ReportChecklist({ sections, className }: ReportChecklistProps) {
  const completedCount = sections.filter(s => s.status === 'completed').length;
  const total = sections.length;

  return (
    <Card className={cn(className)}>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-white">报告完整性检查</h3>
          <p className="text-xs text-gray-500 mt-0.5">
            {completedCount}/{total} 项完成
          </p>
        </div>
        {/* 进度环 */}
        <div className="relative w-12 h-12">
          <svg className="w-12 h-12 -rotate-90" viewBox="0 0 48 48">
            <circle cx="24" cy="24" r="20" fill="none" stroke="currentColor"
              className="text-gray-800" strokeWidth="5" />
            <circle cx="24" cy="24" r="20" fill="none" stroke="currentColor"
              className={cn(
                completedCount === total ? 'text-green-400' :
                completedCount > total / 2 ? 'text-amber-400' : 'text-red-400',
              )}
              strokeWidth="5"
              strokeLinecap="round"
              strokeDasharray={`${(completedCount / total) * 125.66} 125.66`}
            />
          </svg>
          <span className="absolute inset-0 flex items-center justify-center text-xs font-mono font-bold text-white">
            {Math.round((completedCount / total) * 100)}%
          </span>
        </div>
      </div>

      <div className="space-y-1.5">
        {sections.map((s) => {
          const cfg = statusConfig[s.status];
          const Icon = cfg.icon;
          return (
            <div
              key={s.key}
              className="flex flex-col gap-1 py-2 border-b border-gray-800/50 last:border-0"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-300">{s.label}</span>
                <span className={cn(
                  'text-[10px] px-2 py-0.5 rounded-full border font-medium flex items-center gap-1',
                  cfg.className,
                )}>
                  <Icon className="w-3 h-3" />
                  {cfg.label}
                </span>
              </div>
              {s.note && (
                <p className="text-[11px] text-gray-500 leading-relaxed ml-0">{s.note}</p>
              )}
            </div>
          );
        })}
      </div>

      {/* References 特别标注 */}
      <div className="mt-4 p-2.5 rounded-lg bg-amber-500/5 border border-amber-500/10">
        <div className="flex items-start gap-2">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-400 mt-0.5 shrink-0" />
          <p className="text-[11px] text-amber-300/80 leading-relaxed">
            <strong>References 合规声明：</strong>仅允许来自已上传文献库，禁止虚构引用。
          </p>
        </div>
      </div>
    </Card>
  );
}